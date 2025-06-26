"""Output parsers for various system commands"""

import re
from typing import Dict, List, Optional, Tuple


def parse_cpu_usage(output: str) -> Optional[float]:
    """Parse CPU usage from top command output
    
    Expected format: "0.0%us" or just "0.0"
    """
    if not output:
        return None
    
    try:
        # Remove any trailing % and whitespace
        cpu_str = output.strip().rstrip('%')
        return float(cpu_str)
    except ValueError:
        return None


def parse_memory_usage(output: str) -> Optional[float]:
    """Parse memory usage percentage from free command output
    
    Output should already be formatted as percentage
    """
    if not output:
        return None
    
    try:
        return float(output.strip())
    except ValueError:
        return None


def parse_load_average(output: str) -> Optional[Tuple[float, float, float]]:
    """Parse load average from uptime output
    
    Expected format: "0.00, 0.01, 0.05" or "0.00 0.01 0.05"
    """
    if not output:
        return None
    
    try:
        # Handle both comma and space separated values
        values = re.split(r'[,\s]+', output.strip())
        if len(values) >= 3:
            return (float(values[0]), float(values[1]), float(values[2]))
    except ValueError:
        pass
    
    return None


def parse_gpu_usage(output: str) -> Optional[List[int]]:
    """Parse GPU utilization from nvidia-smi output
    
    Expected format: One percentage per line (one per GPU)
    """
    if not output or "not found" in output.lower():
        return None
    
    gpu_usages = []
    for line in output.strip().split('\n'):
        try:
            gpu_usages.append(int(line.strip()))
        except ValueError:
            continue
    
    return gpu_usages if gpu_usages else None


def parse_gpu_memory(output: str) -> Optional[List[Dict[str, int]]]:
    """Parse GPU memory usage from nvidia-smi output
    
    Expected format: "used, total" in MB, one line per GPU
    """
    if not output or "not found" in output.lower():
        return None
    
    gpu_memories = []
    for line in output.strip().split('\n'):
        try:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                used = int(parts[0].strip())
                total = int(parts[1].strip())
                gpu_memories.append({
                    "used_mb": used,
                    "total_mb": total,
                    "used_percent": round((used / total) * 100, 1) if total > 0 else 0
                })
        except (ValueError, IndexError):
            continue
    
    return gpu_memories if gpu_memories else None


def parse_gpu_processes(output: str) -> Optional[List[Dict[str, str]]]:
    """Parse GPU processes from nvidia-smi output
    
    Expected format: "pid, name, memory" per line
    """
    if not output or "not found" in output.lower():
        return None
    
    processes = []
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3:
            processes.append({
                "pid": parts[0],
                "name": parts[1],
                "memory_mb": parts[2]
            })
    
    return processes if processes else None


def format_bytes(bytes_value: int) -> str:
    """Format bytes into human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_server_status(server_name: str, data: Dict) -> Dict:
    """Format server data for display
    
    Returns a dictionary suitable for tabulate or JSON output
    """
    status = {
        "server": server_name,
        "status": "online" if not data.get("error") else "offline",
        "cpu_usage": f"{data.get('cpu_usage', 0):.1f}%" if data.get('cpu_usage') is not None else "N/A",
        "memory_usage": f"{data.get('memory_usage', 0):.1f}%" if data.get('memory_usage') is not None else "N/A",
    }
    
    # Add load average if available
    if data.get('load_average'):
        load = data['load_average']
        status['load_avg'] = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
    else:
        status['load_avg'] = "N/A"
    
    # Add GPU info if available
    if data.get('gpu_usage') is not None:
        gpu_count = len(data['gpu_usage'])
        if gpu_count == 1:
            status['gpu_usage'] = f"{data['gpu_usage'][0]}%"
        else:
            # Show average for multiple GPUs
            avg_usage = sum(data['gpu_usage']) / gpu_count
            status['gpu_usage'] = f"{avg_usage:.0f}% (avg of {gpu_count})"
    else:
        status['gpu_usage'] = "No GPU"
    
    # Add GPU memory if available
    if data.get('gpu_memory'):
        total_used = sum(g['used_mb'] for g in data['gpu_memory'])
        total_capacity = sum(g['total_mb'] for g in data['gpu_memory'])
        if total_capacity > 0:
            percent = (total_used / total_capacity) * 100
            status['gpu_memory'] = f"{percent:.0f}% ({total_used}/{total_capacity} MB)"
        else:
            status['gpu_memory'] = "N/A"
    else:
        status['gpu_memory'] = "No GPU"
    
    # Add error message if offline
    if data.get("error"):
        status['error'] = data['error']
    
    return status