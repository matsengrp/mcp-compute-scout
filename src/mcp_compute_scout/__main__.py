"""MCP server for compute resource scouting"""

import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from tabulate import tabulate

from .config import Config
from .server_checker import ServerChecker
from .parsers import format_server_status


# Initialize FastMCP server
app = FastMCP("mcp-compute-scout")

# Global instances  
config: Optional[Config] = None
checker: Optional[ServerChecker] = None


def get_config_and_checker():
    """Get or initialize config and checker instances"""
    global config, checker
    if config is None or checker is None:
        config = Config()
        checker = ServerChecker(config)
    return config, checker


def format_output(data: Any, for_human: bool = True) -> str:
    """Format output for human or machine consumption"""
    if not for_human:
        return json.dumps(data, indent=2)
    
    if isinstance(data, list) and data and isinstance(data[0], dict):
        # Format as table
        formatted = [format_server_status(d['name'], d) for d in data]
        
        # Determine which columns to show
        headers = ["Server", "Status", "CPU", "Memory", "Load Avg"]
        keys = ["server", "status", "cpu_usage", "memory_usage", "load_avg"]
        
        # Add GPU columns if any server has GPU
        if any(d.get('has_gpu') for d in data):
            headers.extend(["GPU Usage", "GPU Memory"])
            keys.extend(["gpu_usage", "gpu_memory"])
        
        # Extract data for table
        table_data = []
        for item in formatted:
            row = [item.get(k, "N/A") for k in keys]
            table_data.append(row)
        
        return tabulate(table_data, headers=headers, tablefmt="simple")
    
    return str(data)


@app.tool()
async def scout_all(format: str = "human") -> str:
    """Check all configured servers for CPU, memory, and GPU availability"""
    config, checker = get_config_and_checker()
    results = await checker.check_all()
    return format_output(results, format == "human")


@app.tool()
async def scout_gpu(format: str = "human") -> str:
    """Check GPU servers showing utilization and memory usage"""
    config, checker = get_config_and_checker()
    results = await checker.check_gpu_servers()
    if not results:
        return "No GPU servers configured"
    return format_output(results, format == "human")


@app.tool()
async def scout_server(server_name: str, format: str = "human") -> str:
    """Get detailed stats for a specific server (e.g., 'ermine', 'orca42')"""
    config, checker = get_config_and_checker()
    
    server_config = config.get_server(server_name)
    if not server_config:
        return f"Server '{server_name}' not found in configuration"
    
    result = await checker.check_server(server_config)
    
    if format == "human":
        # Format single server result
        status = format_server_status(result['name'], result)
        output = []
        for key, value in status.items():
            output.append(f"{key.replace('_', ' ').title()}: {value}")
        
        # Add GPU processes if available
        if result.get('gpu_processes'):
            output.append("\nGPU Processes:")
            for proc in result['gpu_processes']:
                output.append(f"  - {proc['name']} (PID: {proc['pid']}, Memory: {proc['memory_mb']} MB)")
        
        return "\n".join(output)
    else:
        return json.dumps(result, indent=2)


@app.tool()
async def scout_find(need_gpu: bool = False, max_cpu: Optional[float] = None, 
                    min_memory_gb: Optional[int] = None, format: str = "human") -> str:
    """Find the best available server matching criteria"""
    config, checker = get_config_and_checker()
    
    result = await checker.find_best_server(
        need_gpu=need_gpu,
        max_cpu=max_cpu,
        min_memory_gb=min_memory_gb
    )
    
    if not result:
        return "No servers found matching criteria"
    
    if format == "human":
        status = format_server_status(result['name'], result)
        output = [f"Best available server: {result['name']}\n"]
        for key, value in status.items():
            if key != "server":  # Skip redundant server name
                output.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(output)
    else:
        return json.dumps(result, indent=2)


@app.tool()
async def scout_free(format: str = "human") -> str:
    """Show servers with low load (CPU < 20%, Memory < 50%)"""
    config, checker = get_config_and_checker()
    results = await checker.check_all()
    
    # Filter for low-load servers
    free_servers = [
        r for r in results
        if r.get('online', False) 
        and r.get('cpu_usage', 100) < 20
        and r.get('memory_usage', 100) < 50
    ]
    
    if not free_servers:
        return "No servers currently have low load"
    
    return format_output(free_servers, format == "human")


def main():
    """Main entry point"""
    app.run()


if __name__ == "__main__":
    main()