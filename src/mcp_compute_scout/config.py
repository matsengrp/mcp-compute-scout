"""Configuration loader for MCP Compute Scout"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml


class ServerConfig:
    """Configuration for a single server"""
    
    def __init__(self, name: str, host: str, has_gpu: bool = False):
        self.name = name
        self.host = host
        self.has_gpu = has_gpu
    
    def __repr__(self):
        return f"ServerConfig(name={self.name}, host={self.host}, has_gpu={self.has_gpu})"


class Config:
    """Main configuration class"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Load configuration from YAML file
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            # Look for config in these locations (in order)
            search_paths = [
                Path.cwd() / "config" / "servers.yml",
                Path.home() / ".config" / "mcp-compute-scout" / "servers.yml",
                Path(__file__).parent.parent.parent / "config" / "servers.yml",
            ]
            
            for path in search_paths:
                if path.exists():
                    config_path = path
                    break
            else:
                raise FileNotFoundError(
                    f"No configuration file found. Searched: {search_paths}"
                )
        
        self.config_path = config_path
        self._raw_config = self._load_yaml()
        self.servers = self._parse_servers()
        self.ssh = self._parse_ssh()
        self.commands = self._raw_config.get("commands", {})
        self.cache = self._raw_config.get("cache", {"ttl": 30})
        self.display = self._raw_config.get("display", {})
    
    def _load_yaml(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        with open(self.config_path, 'r') as f:
            # Expand environment variables
            content = os.path.expandvars(f.read())
            return yaml.safe_load(content)
    
    def _parse_servers(self) -> List[ServerConfig]:
        """Parse server configurations, expanding patterns"""
        servers = []
        
        for server_def in self._raw_config.get("servers", []):
            if "name" in server_def:
                # Individual server
                servers.append(
                    ServerConfig(
                        name=server_def["name"],
                        host=server_def.get("host", server_def["name"]),
                        has_gpu=server_def.get("has_gpu", False)
                    )
                )
            elif "pattern" in server_def:
                # Pattern-based servers
                pattern = server_def["pattern"]
                has_gpu = server_def.get("has_gpu", False)
                
                # Extract pattern like "orca{01..99}"
                match = re.match(r'(.+)\{(\d+)\.\.(\d+)\}', pattern)
                if match:
                    prefix = match.group(1)
                    start = int(match.group(2))
                    end = int(match.group(3))
                    num_digits = len(match.group(2))
                    
                    for i in range(start, end + 1):
                        name = f"{prefix}{str(i).zfill(num_digits)}"
                        servers.append(
                            ServerConfig(
                                name=name,
                                host=name,
                                has_gpu=has_gpu
                            )
                        )
                else:
                    # Simple glob pattern - just use as-is
                    servers.append(
                        ServerConfig(
                            name=pattern,
                            host=pattern,
                            has_gpu=has_gpu
                        )
                    )
        
        return servers
    
    def _parse_ssh(self) -> Dict[str, Any]:
        """Parse SSH configuration"""
        ssh_config = self._raw_config.get("ssh", {})
        
        # Expand home directory in key_file
        if "key_file" in ssh_config:
            ssh_config["key_file"] = os.path.expanduser(ssh_config["key_file"])
        
        # Set defaults
        ssh_config.setdefault("timeout", 10)
        ssh_config.setdefault("username", os.environ.get("USER", ""))
        ssh_config.setdefault("options", [])
        
        return ssh_config
    
    def get_server(self, name: str) -> Optional[ServerConfig]:
        """Get a specific server by name"""
        for server in self.servers:
            if server.name == name:
                return server
        return None
    
    def get_gpu_servers(self) -> List[ServerConfig]:
        """Get all servers with GPUs"""
        return [s for s in self.servers if s.has_gpu]
    
    def get_ssh_command(self, host: str, command: str) -> List[str]:
        """Build SSH command array for subprocess"""
        ssh_cmd = ["ssh"]
        
        # Add SSH options
        ssh_cmd.extend(self.ssh.get("options", []))
        
        # Add timeout
        ssh_cmd.extend(["-o", f"ConnectTimeout={self.ssh['timeout']}"])
        
        # Add username@host
        if self.ssh.get("username"):
            ssh_cmd.append(f"{self.ssh['username']}@{host}")
        else:
            ssh_cmd.append(host)
        
        # Add the actual command
        ssh_cmd.append(command)
        
        return ssh_cmd