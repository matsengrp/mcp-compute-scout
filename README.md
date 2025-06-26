# MCP Compute Scout

An MCP (Model Context Protocol) server for checking compute and GPU availability across SSH-accessible servers. Perfect for research groups and organizations with multiple compute servers.

## Features

- **Server Discovery**: Check CPU, memory, and GPU usage across all servers
- **GPU Monitoring**: Track GPU utilization, memory, and running processes
- **Smart Selection**: Find the best available server based on your requirements
- **Slash Commands**: Use intuitive `/scout_*` commands in Claude Desktop
- **Fast & Parallel**: Checks multiple servers concurrently with caching
- **Flexible Config**: YAML-based configuration with pattern support

## Installation

### Using pipx (Recommended)

[pipx](https://pypa.github.io/pipx/) is the recommended installation method as it creates an isolated environment and makes the command available globally:

```bash
# Install pipx if you haven't already
brew install pipx  # macOS with Homebrew
# or
python -m pip install --user pipx

# Clone and install
git clone https://github.com/matsengrp/mcp-compute-scout.git
cd mcp-compute-scout
pipx install -e .
```

### Alternative: Using pip

If you prefer to manage your own virtual environment:

```bash
git clone https://github.com/matsengrp/mcp-compute-scout.git
cd mcp-compute-scout
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Configuration

1. Copy and customize the configuration file:

```bash
mkdir -p ~/.config/mcp-compute-scout
cp config/servers.yml ~/.config/mcp-compute-scout/
```

2. Edit `~/.config/mcp-compute-scout/servers.yml` to add your servers:

```yaml
servers:
  - name: myserver1
    host: myserver1.example.com
    has_gpu: true
    
  # Use patterns for server groups
  - pattern: "node{01..10}"
    has_gpu: true

ssh:
  username: "${USER}"  # Uses environment variable
  timeout: 10
```

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

#### If installed with pipx (Recommended):
```json
{
  "mcpServers": {
    "compute-scout": {
      "command": "mcp-compute-scout",
      "env": {
        "SSH_USER": "your-username"  // Optional, defaults to current user
      }
    }
  }
}
```

#### If installed with pip in a virtual environment:
```json
{
  "mcpServers": {
    "compute-scout": {
      "command": "/path/to/mcp-compute-scout/.venv/bin/python",
      "args": ["-m", "mcp_compute_scout"],
      "env": {
        "SSH_USER": "your-username"  // Optional, defaults to current user
      }
    }
  }
}
```

## Usage

Once configured, the following slash commands are available in Claude Desktop:

### `/scout_all`
Show all servers with their current resource usage:
```
Server    Status   CPU      Memory   Load Avg        GPU Usage   GPU Memory
--------  -------  -------  -------  --------------  ----------  ------------
ermine    online   15.2%    45.3%    0.52, 0.48, 0.41  25%        30% (3072/10240 MB)
quokka    online   5.1%     22.1%    0.15, 0.20, 0.18  No GPU     No GPU
```

### `/scout_gpu`
Show only GPU-enabled servers with detailed GPU information:
```
Server    Status   CPU     Memory   GPU Usage       GPU Memory
--------  -------  ------  -------  -------------   ----------------
ermine    online   15.2%   45.3%    25%             30% (3072/10240 MB)
orca01    online   89.5%   78.2%    95% (avg of 4)  85% (34816/40960 MB)
```

### `/scout_server ermine`
Get detailed information about a specific server:
```
Server: ermine
Status: online
CPU Usage: 15.2%
Memory Usage: 45.3%
Load Avg: 0.52, 0.48, 0.41
GPU Usage: 25%
GPU Memory: 30% (3072/10240 MB)

GPU Processes:
  - python (PID: 12345, Memory: 2048 MB)
  - jupyter (PID: 23456, Memory: 1024 MB)
```

### `/scout_find need_gpu=true max_cpu=50`
Find the best server matching your criteria:
```
Best available server: orca03

Status: online
CPU Usage: 12.5%
Memory Usage: 35.2%
Load Avg: 0.25, 0.30, 0.28
GPU Usage: 10%
GPU Memory: 5% (512/10240 MB)
```

### `/scout_free`
Quick view of servers with low load (CPU < 20%, Memory < 50%):
```
Server    Status   CPU     Memory   Load Avg         GPU Usage
--------  -------  ------  -------  --------------   ----------
quokka    online   5.1%    22.1%    0.15, 0.20, 0.18  No GPU
orca03    online   12.5%   35.2%    0.25, 0.30, 0.28  10%
```

## Advanced Usage

### JSON Output

All commands support JSON output for programmatic use:

```
/scout_all format=json
/scout_find need_gpu=true format=json
```

### Finding Servers Programmatically

The `/scout_find` command supports multiple filters:

- `need_gpu`: Require GPU availability (true/false)
- `max_cpu`: Maximum CPU usage percentage (0-100)
- `min_memory_gb`: Minimum free memory in GB

Example: Find a GPU server with less than 30% CPU usage:
```
/scout_find need_gpu=true max_cpu=30
```

## SSH Configuration

The tool uses your system's SSH configuration. Make sure:

1. SSH keys are set up for passwordless access
2. Servers are accessible via SSH
3. Your SSH config (`~/.ssh/config`) has appropriate settings

Example SSH config entry:
```
Host orca*
    User myusername
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
```

## Customizing Commands

You can customize the commands used to check system resources in `servers.yml`:

```yaml
commands:
  cpu_usage: |
    # Your custom CPU check command
    top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
  
  gpu_usage: |
    # Your custom GPU check command
    nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits
```

## Troubleshooting

### "Unknown host" errors
- Verify the server hostname is correct
- Check your SSH config and `/etc/hosts`

### "Permission denied" errors
- Ensure SSH key authentication is set up
- Check the username in configuration

### GPU information not showing
- Verify `nvidia-smi` is installed on the server
- Check that `has_gpu: true` is set for GPU servers

### Slow responses
- Adjust the SSH timeout in configuration
- Check network connectivity
- The cache TTL can be adjusted (default: 30 seconds)

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

MIT License - see LICENSE file for details
