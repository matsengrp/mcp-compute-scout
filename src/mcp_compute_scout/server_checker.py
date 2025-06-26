"""Server checking logic with SSH subprocess calls"""

import asyncio
import subprocess
import time
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from .config import Config, ServerConfig
from .parsers import (
    parse_cpu_usage, parse_memory_usage, parse_load_average,
    parse_gpu_usage, parse_gpu_memory, parse_gpu_processes
)


class ServerChecker:
    """Check server resources via SSH"""
    
    def __init__(self, config: Config):
        self.config = config
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=10)
    
    def _run_ssh_command(self, server: ServerConfig, command: str) -> str:
        """Run SSH command and return output"""
        ssh_cmd = self.config.get_ssh_command(server.host, command)
        
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=self.config.ssh['timeout']
            )
            
            if result.returncode != 0:
                # Check for specific SSH errors
                if "Could not resolve hostname" in result.stderr:
                    raise Exception(f"Unknown host: {server.host}")
                elif "Connection refused" in result.stderr:
                    raise Exception(f"Connection refused to {server.host}")
                elif "Permission denied" in result.stderr:
                    raise Exception(f"Permission denied for {server.host}")
                else:
                    raise Exception(f"SSH error: {result.stderr.strip()}")
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise Exception(f"Connection timeout to {server.host}")
        except Exception as e:
            raise Exception(f"SSH failed: {str(e)}")
    
    def _check_server_sync(self, server: ServerConfig) -> Dict[str, Any]:
        """Synchronously check a single server"""
        data = {
            "name": server.name,
            "host": server.host,
            "has_gpu": server.has_gpu,
            "checked_at": time.time()
        }
        
        try:
            # Get CPU usage
            cpu_output = self._run_ssh_command(server, self.config.commands['cpu_usage'])
            data['cpu_usage'] = parse_cpu_usage(cpu_output)
            
            # Get memory usage
            mem_output = self._run_ssh_command(server, self.config.commands['memory_usage'])
            data['memory_usage'] = parse_memory_usage(mem_output)
            
            # Get load average
            load_output = self._run_ssh_command(server, self.config.commands['load_average'])
            data['load_average'] = parse_load_average(load_output)
            
            # Get GPU info if server has GPU
            if server.has_gpu:
                try:
                    gpu_usage_output = self._run_ssh_command(server, self.config.commands['gpu_usage'])
                    data['gpu_usage'] = parse_gpu_usage(gpu_usage_output)
                    
                    gpu_mem_output = self._run_ssh_command(server, self.config.commands['gpu_memory'])
                    data['gpu_memory'] = parse_gpu_memory(gpu_mem_output)
                    
                    if 'gpu_processes' in self.config.commands:
                        gpu_proc_output = self._run_ssh_command(server, self.config.commands['gpu_processes'])
                        data['gpu_processes'] = parse_gpu_processes(gpu_proc_output)
                except Exception as e:
                    # GPU commands failed, but server is still online
                    data['gpu_error'] = str(e)
            
        except Exception as e:
            data['error'] = str(e)
            data['online'] = False
        else:
            data['online'] = True
        
        return data
    
    async def check_server(self, server: ServerConfig, use_cache: bool = True) -> Dict[str, Any]:
        """Check a single server asynchronously"""
        # Check cache
        if use_cache and server.name in self._cache:
            cached = self._cache[server.name]
            if time.time() - cached['checked_at'] < self.config.cache['ttl']:
                return cached
        
        # Run check in thread pool
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(self._executor, self._check_server_sync, server)
        
        # Update cache
        self._cache[server.name] = data
        
        return data
    
    async def check_servers(self, servers: List[ServerConfig], use_cache: bool = True) -> List[Dict[str, Any]]:
        """Check multiple servers in parallel"""
        tasks = [self.check_server(server, use_cache) for server in servers]
        return await asyncio.gather(*tasks)
    
    async def check_all(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Check all configured servers"""
        return await self.check_servers(self.config.servers, use_cache)
    
    async def check_gpu_servers(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Check only GPU servers"""
        gpu_servers = self.config.get_gpu_servers()
        return await self.check_servers(gpu_servers, use_cache)
    
    async def find_best_server(
        self, 
        need_gpu: bool = False,
        max_cpu: Optional[float] = None,
        min_memory_gb: Optional[int] = None,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Find the best available server matching criteria"""
        # Get servers to check
        if need_gpu:
            servers = self.config.get_gpu_servers()
        else:
            servers = self.config.servers
        
        # Check all servers
        results = await self.check_servers(servers, use_cache)
        
        # Filter online servers
        online_servers = [r for r in results if r.get('online', False)]
        
        # Apply filters
        filtered = []
        for server in online_servers:
            # CPU filter
            if max_cpu is not None:
                cpu = server.get('cpu_usage')
                if cpu is None or cpu > max_cpu:
                    continue
            
            # Memory filter (rough estimate - would need to get total memory)
            if min_memory_gb is not None:
                # For now, just check memory usage percentage
                mem_usage = server.get('memory_usage')
                if mem_usage is None or mem_usage > 80:  # Skip if >80% used
                    continue
            
            # GPU filter
            if need_gpu:
                if not server.get('gpu_usage'):
                    continue
            
            filtered.append(server)
        
        if not filtered:
            return None
        
        # Sort by combined score (lower is better)
        def score_server(server):
            cpu = server.get('cpu_usage', 100)
            mem = server.get('memory_usage', 100)
            
            # Add GPU usage to score if available
            gpu_score = 0
            if server.get('gpu_usage'):
                gpu_score = sum(server['gpu_usage']) / len(server['gpu_usage'])
            
            return cpu + mem + gpu_score
        
        filtered.sort(key=score_server)
        
        return filtered[0]
    
    def clear_cache(self):
        """Clear the cache"""
        self._cache.clear()
    
    def __del__(self):
        """Cleanup thread pool"""
        self._executor.shutdown(wait=False)