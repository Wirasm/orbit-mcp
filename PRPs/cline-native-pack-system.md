---
name: "Cline-Native Pack System for Orbit-MCP"
description: "Transform Orbit-MCP to support Cline marketplace servers with curated pack management alongside existing Docker implementation"
---

## Goal

**Feature Goal**: Enable one-click installation of curated MCP server collections from Cline marketplace without Docker dependencies

**Deliverable**: Dual-mode MCP server (Docker + Cline) with pack management for both ecosystems

**Success Definition**: Successfully install and configure 5+ Cline MCP servers in under 30 seconds via pack system during hackathon demo

## User Persona

**Target User**: Developers using Cline who want quick access to curated tool collections

**Use Case**: Developer needs full-stack tools (GitHub, database, filesystem) installed with one command instead of manually finding and installing each server

**User Journey**: 
1. User opens Cline with Orbit-MCP installed
2. User types: "Install the full-stack development pack"
3. Orbit-MCP shows pack contents and installs all servers
4. User immediately uses tools without further configuration

**Pain Points Addressed**: 
- Discovery friction - hard to find relevant MCP servers
- Installation complexity - each server requires manual setup
- Configuration burden - editing JSON files for each server

## Why

- Cline has 2.7M+ developers but MCP server discovery/installation is fragmented
- Docker MCP Gateway adds unnecessary complexity for hackathon demo
- Teams need curated tool collections, not individual server management
- Direct STDIO communication is faster and simpler than Docker Gateway layer

## What

Enable Orbit-MCP to work with both Docker MCP and Cline marketplace servers, with focus on Cline for hackathon demo.

### Success Criteria

- [ ] Install pack of 5+ servers in under 30 seconds
- [ ] Zero Docker dependencies when running in Cline mode
- [ ] Clean separation between Docker and Cline implementations
- [ ] Pre-built packs for common stacks (frontend, backend, data, devops)
- [ ] Automatic configuration of cline_mcp_settings.json
- [ ] Side-by-side operation without breaking existing Docker tools

## All Needed Context

### Context Completeness Check

_Someone unfamiliar with the codebase has everything needed to implement this feature successfully._

### Documentation & References

```yaml
# MUST READ - Include these in your context window
- url: https://docs.cline.bot/mcp/configuring-mcp-servers
  why: Cline MCP configuration format and settings file location
  critical: Settings file is at ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json

- url: https://github.com/cline/mcp-marketplace
  why: Understanding marketplace structure and server availability
  pattern: Servers installed to ~/Documents/Cline/MCP/ directory

- file: src/orbit_mcp/mcp_server.py
  why: Existing FastMCP server structure and tool registration pattern
  pattern: DockerMCPManager class structure and tool decorators
  gotcha: Need to conditionally register tools based on config

- file: src/orbit_mcp/pack_manager.py
  why: Existing pack management logic to extend for Cline
  pattern: PackManager class with YAML pack definitions
  gotcha: Currently tied to Docker, needs abstraction
```

### Current Codebase tree

```bash
orbit-mcp/
├── src/
│   └── orbit_mcp/
│       ├── __init__.py          # Entry points
│       ├── mcp_server.py        # Main FastMCP server
│       ├── pack_manager.py      # Docker pack management
│       ├── docker_client.py     # Empty Docker client
│       └── team_manager.py      # Team management (future)
├── packs/                        # Pack definitions
│   └── oauth-demo.yaml
├── PRPs/                         # PRP documents
│   └── templates/
│       └── prp_base.md
├── pyproject.toml               # Dependencies
└── CLAUDE.md                    # AI instructions
```

### Desired Codebase tree with files to be added and responsibility of file

```bash
orbit-mcp/
├── src/
│   └── orbit_mcp/
│       ├── __init__.py          # Entry points
│       ├── mcp_server.py        # Main FastMCP server (modified for dual-mode)
│       ├── config.py            # NEW: Feature flags and mode selection
│       ├── cline_manager.py     # NEW: Cline marketplace integration
│       ├── marketplace_cache.py # NEW: Cached server definitions
│       ├── pack_manager.py      # Modified to support both backends
│       ├── docker_manager.py    # NEW: Extracted from mcp_server.py
│       ├── docker_client.py     # Existing (empty)
│       └── team_manager.py      # Existing (future)
├── packs/
│   ├── marketplace/             # NEW: Cline-specific packs
│   │   ├── fullstack.yaml
│   │   ├── frontend.yaml
│   │   ├── backend.yaml
│   │   └── data.yaml
│   └── docker/                  # Existing Docker packs
│       └── oauth-demo.yaml
├── PRPs/
│   ├── cline-native-pack-system.md  # This document
│   └── templates/
└── pyproject.toml
```

### Known Gotchas of our codebase & Library Quirks

```python
# CRITICAL: FastMCP requires async functions for all tools
# CRITICAL: Cline settings file uses mcpServers key (not mcp_servers)
# CRITICAL: Must preserve exact JSON structure in cline_mcp_settings.json
# GOTCHA: Cline installs servers to ~/Documents/Cline/MCP/ not configurable
# GOTCHA: Some servers use npm, others use npx, some are Python
```

## Implementation Blueprint

### Data models and structure

```python
# src/orbit_mcp/config.py
from typing import Dict, Literal
from pydantic import BaseModel

class OrbitConfig(BaseModel):
    mode: Literal["docker", "cline", "hybrid"] = "cline"
    enabled_features: Dict[str, bool] = {
        "docker_tools": False,
        "cline_tools": True,
        "legacy_packs": False,
        "marketplace_packs": True
    }

# src/orbit_mcp/marketplace_cache.py
class MarketplaceServer(BaseModel):
    name: str
    command: str
    args: List[str]
    description: str
    category: str
    install_type: Literal["npm", "npx", "pip", "git"]

class ClinePack(BaseModel):
    name: str
    description: str
    servers: List[str]  # Server names from marketplace
    tags: List[str]
    created_at: str
```

### Implementation Tasks (ordered by dependencies)

```yaml
Task 1: CREATE src/orbit_mcp/config.py
  - IMPLEMENT: OrbitConfig model with mode selection and feature flags
  - ADD: Environment variable support for ORBIT_MODE
  - NAMING: OrbitConfig class, ENABLED_FEATURES constant
  - PLACEMENT: Config module for centralized settings

Task 2: CREATE src/orbit_mcp/docker_manager.py
  - EXTRACT: DockerMCPManager class from mcp_server.py
  - PRESERVE: All existing Docker functionality unchanged
  - NAMING: Keep DockerMCPManager class name
  - PLACEMENT: Separate module for Docker implementation

Task 3: CREATE src/orbit_mcp/cline_manager.py
  - IMPLEMENT: ClineManager class with marketplace integration
  - FOLLOW pattern: DockerMCPManager structure but for Cline
  - NAMING: ClineManager class with install_server, configure_server methods
  - KEY METHODS: 
    - read_cline_settings() -> Dict
    - write_cline_settings(settings: Dict) -> None
    - install_server(server_name: str) -> Dict
    - install_pack(pack_name: str) -> Dict
  - PLACEMENT: Parallel to docker_manager.py

Task 4: CREATE src/orbit_mcp/marketplace_cache.py
  - IMPLEMENT: Hardcoded marketplace server definitions for speed
  - ADD: Popular servers like github, filesystem, postgres, fetch
  - NAMING: MARKETPLACE_SERVERS constant with server definitions
  - PLACEMENT: Separate module for marketplace data

Task 5: MODIFY src/orbit_mcp/pack_manager.py
  - ADD: backend parameter to support docker/cline modes
  - IMPLEMENT: Dual-mode pack loading from packs/marketplace/ or packs/docker/
  - PRESERVE: Existing Docker pack functionality
  - NAMING: Add backend="docker"|"cline" to methods

Task 6: MODIFY src/orbit_mcp/mcp_server.py
  - IMPORT: config, docker_manager, cline_manager modules
  - ADD: Conditional tool registration based on ENABLED_FEATURES
  - IMPLEMENT: Cline-specific tools with cline_ prefix
  - PRESERVE: All existing Docker tools (conditionally enabled)

Task 7: CREATE packs/marketplace/*.yaml
  - IMPLEMENT: Pack definitions for common stacks
  - STRUCTURE: name, description, servers (list), tags
  - FILES: fullstack.yaml, frontend.yaml, backend.yaml, data.yaml
  - PLACEMENT: packs/marketplace/ directory
```

### Implementation Patterns & Key Details

```python
# config.py pattern
import os
from typing import Dict, Literal

ORBIT_MODE = os.getenv("ORBIT_MODE", "cline")
ENABLED_FEATURES = {
    "docker_tools": ORBIT_MODE in ["docker", "hybrid"],
    "cline_tools": ORBIT_MODE in ["cline", "hybrid"],
}

# cline_manager.py pattern
import json
import os
from pathlib import Path

class ClineManager:
    def __init__(self):
        self.settings_path = Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        self.install_dir = Path.home() / "Documents" / "Cline" / "MCP"
    
    async def read_cline_settings(self) -> Dict:
        if not self.settings_path.exists():
            return {"mcpServers": {}}
        with open(self.settings_path, 'r') as f:
            return json.load(f)
    
    async def write_cline_settings(self, settings: Dict) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

# mcp_server.py conditional registration
from .config import ENABLED_FEATURES

if ENABLED_FEATURES.get("docker_tools", False):
    @mcp.tool()
    async def enable_server(server_name: str) -> Dict[str, Any]:
        # Existing Docker implementation
        return await docker_manager.enable_server(server_name)

if ENABLED_FEATURES.get("cline_tools", False):
    @mcp.tool()
    async def cline_install_pack(pack_name: str) -> Dict[str, Any]:
        # New Cline implementation
        return await cline_manager.install_pack(pack_name)
```

### Integration Points

```yaml
CONFIG:
  - add to: Environment variables or .env file
  - pattern: "ORBIT_MODE=cline"

PACKS:
  - location: packs/marketplace/*.yaml
  - format: Standard YAML with servers list

CLINE_SETTINGS:
  - file: ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
  - format: JSON with mcpServers object
```

## Validation Loop

### Level 1: Syntax & Style (Immediate Feedback)

```bash
# Run after each file creation
ruff check src/orbit_mcp --fix
mypy src/orbit_mcp
ruff format src/orbit_mcp

# Expected: Zero errors
```

### Level 2: Unit Tests (Component Validation)

```bash
# Test configuration loading
python -c "from orbit_mcp.config import ORBIT_MODE; print(f'Mode: {ORBIT_MODE}')"

# Test Cline settings reading
python -c "from orbit_mcp.cline_manager import ClineManager; import asyncio; cm = ClineManager(); print(asyncio.run(cm.read_cline_settings()))"

# Expected: Proper JSON output or empty dict
```

### Level 3: Integration Testing (System Validation)

```bash
# Start MCP server in Cline mode
ORBIT_MODE=cline uv run orbit-mcp-server

# Test tool discovery
echo '{"method": "tools/list"}' | ORBIT_MODE=cline uv run python -m orbit_mcp

# Test pack installation (dry run)
echo '{"method": "tools/call", "params": {"name": "cline_list_packs", "arguments": {}}}' | \
  ORBIT_MODE=cline uv run python -m orbit_mcp

# Expected: JSON responses with Cline tools only
```

### Level 4: Hackathon Demo Validation

```bash
# Full demo flow simulation
ORBIT_MODE=cline uv run orbit-mcp-server &
SERVER_PID=$!

# List available packs
echo "Available packs:"
echo '{"method": "tools/call", "params": {"name": "cline_list_packs", "arguments": {}}}' | \
  ORBIT_MODE=cline uv run python -m orbit_mcp

# Install fullstack pack (simulation)
echo "Installing fullstack pack:"
echo '{"method": "tools/call", "params": {"name": "cline_install_pack", "arguments": {"pack_name": "fullstack"}}}' | \
  ORBIT_MODE=cline uv run python -m orbit_mcp

# Verify settings file updated
cat ~/Library/Application\ Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json

kill $SERVER_PID

# Expected: Pack installed, settings updated, ready for demo
```

## Final Validation Checklist

### Technical Validation

- [ ] Config system working with environment variables
- [ ] Docker tools hidden when ORBIT_MODE=cline
- [ ] Cline tools available and functional
- [ ] Settings file properly read/written

### Feature Validation

- [ ] Can list available packs
- [ ] Can install pack with multiple servers
- [ ] Settings file updated correctly
- [ ] No Docker dependencies in Cline mode

### Code Quality Validation

- [ ] Clean separation between Docker and Cline code
- [ ] No breaking changes to existing Docker functionality
- [ ] Follows existing FastMCP patterns
- [ ] Error handling for missing settings file

### Documentation & Deployment

- [ ] ORBIT_MODE environment variable documented
- [ ] Pack format documented in YAML files
- [ ] Installation directory paths verified

---

## Anti-Patterns to Avoid

- ❌ Don't modify Docker functionality - keep it isolated
- ❌ Don't hardcode paths - use Path objects
- ❌ Don't mix Docker and Cline logic in same functions
- ❌ Don't skip settings file validation
- ❌ Don't assume Cline is installed - check paths exist
- ❌ Don't break existing pack YAML format