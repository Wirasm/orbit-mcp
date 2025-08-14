#!/usr/bin/env python3
"""
Orbit-MCP Server - Meta-MCP Server for managing Docker MCP Gateway
"""

import asyncio
import json
import logging
import signal
import subprocess
import time
from typing import Any, Dict, List, Optional

import aiohttp
from fastmcp import FastMCP

from .pack_manager import PackManager, COMPANY_PACK_TEMPLATES

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("Orbit-MCP")


class DockerMCPManager:
    """Docker MCP Gateway manager with lifecycle and tool discovery"""

    def __init__(self):
        self.gateway_process: Optional[asyncio.subprocess.Process] = None
        self.gateway_port = 3001  # Use a different port than default
        self.gateway_running = False

    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a docker mcp command"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
            )
        except Exception as e:
            logger.error(f"Command failed: {cmd}, error: {str(e)}")
            raise

    async def check_availability(self) -> bool:
        """Check if Docker MCP is available"""
        try:
            result = await self._run_command(["docker", "mcp", "--help"])
            return result.returncode == 0
        except Exception:
            return False

    async def list_available_servers(self) -> List[Dict[str, str]]:
        """List all servers available in Docker MCP catalog"""
        try:
            result = await self._run_command(["docker", "mcp", "catalog", "show", "docker-mcp"])

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                servers = []
                for line in lines:
                    if line.strip() and not line.startswith("#"):
                        parts = line.split(":", 2)  # Split on first colon to get name
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            description = parts[1].strip() if len(parts) > 1 else ""
                            servers.append(
                                {
                                    "name": name,
                                    "description": description[:100] + "..."
                                    if len(description) > 100
                                    else description,
                                    "status": "available",
                                }
                            )
                return servers
            else:
                logger.warning(f"Failed to list servers: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Error listing servers: {str(e)}")
            return []

    async def list_enabled_servers(self) -> List[Dict[str, str]]:
        """List currently enabled MCP servers by reading registry.yaml"""
        try:
            # Read the registry.yaml file directly since docker mcp server list isn't working as expected
            import os

            import yaml

            registry_path = os.path.expanduser("~/.docker/mcp/registry.yaml")

            if not os.path.exists(registry_path):
                logger.info("No registry.yaml file found - no servers enabled")
                return []

            with open(registry_path, "r") as f:
                registry_data = yaml.safe_load(f) or {}

            servers = []
            registry = registry_data.get("registry", {})

            for server_name, server_config in registry.items():
                servers.append(
                    {
                        "name": server_name,
                        "status": "enabled",
                        "ref": server_config.get("ref", "")
                        if isinstance(server_config, dict)
                        else str(server_config),
                    }
                )

            logger.info(f"Found {len(servers)} enabled servers from registry")
            return servers

        except Exception as e:
            logger.error(f"Error reading enabled servers from registry: {str(e)}")
            # Fallback to command-line approach
            try:
                result = await self._run_command(["docker", "mcp", "server", "list"])
                if result.returncode == 0 and result.stdout.strip():
                    # Simple parsing of server names
                    servers = []
                    for line in result.stdout.strip().split("\n"):
                        if line.strip():
                            servers.append(
                                {"name": line.strip(), "status": "enabled", "ref": "unknown"}
                            )
                    return servers
                return []
            except Exception as fallback_error:
                logger.error(f"Fallback command also failed: {str(fallback_error)}")
                return []

    async def enable_server(self, server_name: str) -> Dict[str, Any]:
        """Enable a specific MCP server"""
        try:
            result = await self._run_command(["docker", "mcp", "server", "enable", server_name])

            if result.returncode == 0:
                logger.info(f"✅ Enabled server: {server_name}")
                return {
                    "success": True,
                    "server_name": server_name,
                    "message": f"Successfully enabled {server_name}",
                    "output": result.stdout.strip(),
                }
            else:
                logger.warning(f"⚠️ Failed to enable {server_name}: {result.stderr}")
                return {
                    "success": False,
                    "server_name": server_name,
                    "error": result.stderr.strip(),
                    "message": f"Failed to enable {server_name}",
                }
        except Exception as e:
            logger.error(f"❌ Error enabling {server_name}: {str(e)}")
            return {
                "success": False,
                "server_name": server_name,
                "error": str(e),
                "message": f"Error enabling {server_name}",
            }

    async def disable_server(self, server_name: str) -> Dict[str, Any]:
        """Disable a specific MCP server"""
        try:
            # Check if server is currently enabled
            enabled_servers = await self.list_enabled_servers()
            server_names = [s["name"] for s in enabled_servers]
            
            if server_name not in server_names:
                return {
                    "success": False,
                    "server_name": server_name,
                    "message": f"Server '{server_name}' is not currently enabled",
                    "enabled_servers": server_names,
                }

            result = await self._run_command(["docker", "mcp", "server", "disable", server_name])

            if result.returncode == 0:
                logger.info(f"✅ Disabled server: {server_name}")
                return {
                    "success": True,
                    "server_name": server_name,
                    "message": f"Successfully disabled {server_name}",
                    "output": result.stdout.strip(),
                }
            else:
                logger.warning(f"⚠️ Failed to disable {server_name}: {result.stderr}")
                return {
                    "success": False,
                    "server_name": server_name,
                    "error": result.stderr.strip(),
                    "message": f"Failed to disable {server_name}",
                }
        except Exception as e:
            logger.error(f"❌ Error disabling {server_name}: {str(e)}")
            return {
                "success": False,
                "server_name": server_name,
                "error": str(e),
                "message": f"Error disabling {server_name}",
            }

    async def reset_all_servers(self) -> Dict[str, Any]:
        """Disable all currently enabled MCP servers"""
        try:
            # Get currently enabled servers for reporting
            enabled_servers = await self.list_enabled_servers()
            server_count = len(enabled_servers)
            
            if server_count == 0:
                return {
                    "success": True,
                    "message": "No servers are currently enabled",
                    "servers_disabled": [],
                }

            result = await self._run_command(["docker", "mcp", "server", "reset"])

            if result.returncode == 0:
                disabled_servers = [s["name"] for s in enabled_servers]
                logger.info(f"✅ Disabled all {server_count} servers: {', '.join(disabled_servers)}")
                return {
                    "success": True,
                    "message": f"Successfully disabled all {server_count} servers",
                    "servers_disabled": disabled_servers,
                    "output": result.stdout.strip(),
                }
            else:
                logger.warning(f"⚠️ Failed to reset servers: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr.strip(),
                    "message": "Failed to disable all servers",
                }
        except Exception as e:
            logger.error(f"❌ Error resetting servers: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Error disabling all servers",
            }

    async def list_oauth_providers(self) -> List[Dict[str, Any]]:
        """List available OAuth providers and their authorization status"""
        try:
            result = await self._run_command(["docker", "mcp", "oauth", "ls"])

            if result.returncode == 0:
                providers = []
                for line in result.stdout.strip().split("\n"):
                    if " | " in line:
                        parts = line.split(" | ")
                        if len(parts) >= 2:
                            providers.append(
                                {
                                    "provider": parts[0].strip(),
                                    "status": parts[1].strip(),
                                    "authorized": parts[1].strip() != "not authorized",
                                }
                            )
                return providers
            else:
                logger.warning(f"Failed to list OAuth providers: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Error listing OAuth providers: {str(e)}")
            return []

    async def authorize_oauth_provider(self, provider: str) -> Dict[str, Any]:
        """Start OAuth authorization flow for a provider"""
        try:
            result = await self._run_command(["docker", "mcp", "oauth", "authorize", provider])

            if result.returncode == 0:
                return {
                    "success": True,
                    "provider": provider,
                    "message": f"OAuth authorization flow started for {provider}",
                    "output": result.stdout.strip(),
                }
            else:
                return {
                    "success": False,
                    "provider": provider,
                    "error": result.stderr.strip(),
                    "message": f"Failed to start OAuth flow for {provider}",
                }
        except Exception as e:
            return {
                "success": False,
                "provider": provider,
                "error": str(e),
                "message": f"Error starting OAuth flow for {provider}",
            }

    async def revoke_oauth_provider(self, provider: str) -> Dict[str, Any]:
        """Revoke OAuth authorization for a provider"""
        try:
            result = await self._run_command(["docker", "mcp", "oauth", "revoke", provider])

            if result.returncode == 0:
                return {
                    "success": True,
                    "provider": provider,
                    "message": f"OAuth authorization revoked for {provider}",
                    "output": result.stdout.strip(),
                }
            else:
                return {
                    "success": False,
                    "provider": provider,
                    "error": result.stderr.strip(),
                    "message": f"Failed to revoke OAuth for {provider}",
                }
        except Exception as e:
            return {
                "success": False,
                "provider": provider,
                "error": str(e),
                "message": f"Error revoking OAuth for {provider}",
            }

    async def check_server_auth_requirements(self, server_name: str) -> Dict[str, Any]:
        """Check what authentication is required for a server"""
        try:
            # Read from catalog to get OAuth requirements
            import os

            import yaml

            catalog_path = os.path.expanduser("~/.docker/mcp/catalogs/docker-mcp.yaml")

            if not os.path.exists(catalog_path):
                return {"error": "Docker MCP catalog not found"}

            with open(catalog_path, "r") as f:
                catalog_data = yaml.safe_load(f)

            registry = catalog_data.get("registry", {})
            server_config = registry.get(server_name, {})

            if not server_config:
                return {
                    "server": server_name,
                    "found": False,
                    "message": f"Server '{server_name}' not found in catalog",
                }

            auth_info = {
                "server": server_name,
                "found": True,
                "title": server_config.get("title", server_name),
                "description": server_config.get("description", ""),
                "oauth": server_config.get("oauth", {}),
                "secrets": server_config.get("secrets", {}),
                "auth_required": bool(server_config.get("oauth") or server_config.get("secrets")),
            }

            # Check if OAuth is available
            if auth_info["oauth"]:
                providers = auth_info["oauth"].get("providers", [])
                if providers:
                    auth_info["oauth_provider"] = providers[0].get("provider")
                    auth_info["preferred_auth"] = "oauth"

            # Check current OAuth status
            if auth_info.get("oauth_provider"):
                oauth_providers = await self.list_oauth_providers()
                for provider in oauth_providers:
                    if provider["provider"] == auth_info["oauth_provider"]:
                        auth_info["oauth_status"] = provider["status"]
                        auth_info["oauth_authorized"] = provider["authorized"]
                        break

            return auth_info

        except Exception as e:
            logger.error(f"Error checking auth requirements for {server_name}: {str(e)}")
            return {
                "server": server_name,
                "error": str(e),
                "message": f"Failed to check authentication requirements for {server_name}",
            }

    async def start_gateway(self) -> Dict[str, Any]:
        """Start the Docker MCP Gateway for tool execution"""
        try:
            if self.gateway_running and self.gateway_process:
                return {
                    "success": True,
                    "message": "Gateway already running",
                    "port": self.gateway_port,
                    "endpoint": f"http://localhost:{self.gateway_port}",
                }

            # Start gateway with HTTP transport
            cmd = [
                "docker",
                "mcp",
                "gateway",
                "run",
                "--transport=streaming",
                f"--port={self.gateway_port}",
                "--block-secrets=false",  # Allow secrets for OAuth
            ]

            logger.info(f"Starting Docker MCP Gateway on port {self.gateway_port}...")
            self.gateway_process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            # Wait a moment for gateway to start
            await asyncio.sleep(2)

            # Check if process is still running
            if self.gateway_process.returncode is None:
                self.gateway_running = True
                logger.info(f"✅ Gateway started successfully on port {self.gateway_port}")
                return {
                    "success": True,
                    "message": f"Gateway started on port {self.gateway_port}",
                    "port": self.gateway_port,
                    "endpoint": f"http://localhost:{self.gateway_port}",
                    "pid": self.gateway_process.pid,
                }
            else:
                stdout, stderr = await self.gateway_process.communicate()
                return {
                    "success": False,
                    "error": stderr.decode() if stderr else "Gateway failed to start",
                    "stdout": stdout.decode() if stdout else "",
                }

        except Exception as e:
            logger.error(f"Error starting gateway: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to start Docker MCP Gateway",
            }

    async def stop_gateway(self) -> Dict[str, Any]:
        """Stop the Docker MCP Gateway"""
        try:
            if not self.gateway_running or not self.gateway_process:
                return {"success": True, "message": "Gateway not running"}

            # Terminate the gateway process
            self.gateway_process.terminate()

            try:
                # Wait for graceful shutdown
                await asyncio.wait_for(self.gateway_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if not shutdown gracefully
                self.gateway_process.kill()
                await self.gateway_process.wait()

            self.gateway_running = False
            self.gateway_process = None

            logger.info("✅ Gateway stopped successfully")
            return {"success": True, "message": "Gateway stopped successfully"}

        except Exception as e:
            logger.error(f"Error stopping gateway: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to stop Docker MCP Gateway",
            }

    async def gateway_status(self) -> Dict[str, Any]:
        """Check Docker MCP Gateway status"""
        try:
            if not self.gateway_running or not self.gateway_process:
                return {"running": False, "message": "Gateway not running"}

            # Check if process is still alive
            if self.gateway_process.returncode is not None:
                self.gateway_running = False
                return {
                    "running": False,
                    "message": "Gateway process has terminated",
                    "exit_code": self.gateway_process.returncode,
                }

            return {
                "running": True,
                "port": self.gateway_port,
                "endpoint": f"http://localhost:{self.gateway_port}",
                "pid": self.gateway_process.pid,
            }

        except Exception as e:
            logger.error(f"Error checking gateway status: {str(e)}")
            return {"running": False, "error": str(e)}

    async def discover_tools_from_gateway(self) -> List[Dict[str, Any]]:
        """Discover tools from enabled servers using Docker MCP CLI"""
        try:
            # Use CLI approach instead of HTTP - more reliable
            result = await asyncio.wait_for(
                self._run_command(["docker", "mcp", "tools", "list", "--format", "json"]),
                timeout=15.0,  # Give it more time for CLI execution
            )

            if result.returncode == 0:
                try:
                    tools_data = json.loads(result.stdout)
                    logger.info(f"Discovered {len(tools_data)} tools from Docker MCP CLI")
                    return tools_data if isinstance(tools_data, list) else []
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse tools JSON: {str(e)}")
                    # Fallback to text parsing if JSON fails
                    lines = result.stdout.strip().split("\n")
                    tools = []
                    for line in lines:
                        if line.strip() and not line.startswith("#"):
                            parts = line.split(None, 1)  # Split on first whitespace
                            if len(parts) >= 1:
                                tools.append({
                                    "name": parts[0],
                                    "description": parts[1] if len(parts) > 1 else "",
                                    "server": "unknown",
                                })
                    return tools
            else:
                logger.warning(f"Docker MCP tools list failed: {result.stderr}")
                return []

        except asyncio.TimeoutError:
            logger.warning("Docker MCP tools list timed out")
            return []
        except Exception as e:
            logger.error(f"Error discovering tools via CLI: {str(e)}")
            return []

    async def call_gateway_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool through Docker MCP CLI"""
        try:
            # Build the docker mcp tools call command
            cmd = ["docker", "mcp", "tools", "call", tool_name]
            
            # Add arguments in key=value format
            if arguments:
                import json
                for key, value in arguments.items():
                    if isinstance(value, str):
                        cmd.append(f"{key}={value}")
                    else:
                        # For non-string values, convert to JSON
                        cmd.append(f"{key}={json.dumps(value)}")

            # Execute the tool call with timeout
            result = await asyncio.wait_for(
                self._run_command(cmd),
                timeout=60.0,  # Longer timeout for tool execution
            )

            if result.returncode == 0:
                # Tool executed successfully
                try:
                    # Try to parse output as JSON
                    if result.stdout.strip():
                        # Parse the JSON result that comes after timing info
                        lines = result.stdout.strip().split('\n')
                        json_lines = [line for line in lines if line.startswith('{') or line.startswith('[')]
                        if json_lines:
                            output_data = json.loads(json_lines[-1])  # Use the last JSON line
                            return {"success": True, "result": output_data}
                        else:
                            return {"success": True, "result": {"output": result.stdout.strip()}}
                    else:
                        return {"success": True, "result": {"output": "Tool executed successfully"}}
                except json.JSONDecodeError:
                    # Return raw stdout if not JSON
                    return {"success": True, "result": {"output": result.stdout.strip()}}
            else:
                # Tool execution failed
                error_msg = result.stderr.strip() if result.stderr else "Tool execution failed"
                logger.warning(f"Tool {tool_name} failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "stdout": result.stdout.strip() if result.stdout else "",
                }

        except asyncio.TimeoutError:
            logger.warning(f"Tool {tool_name} execution timed out")
            return {"success": False, "error": "Tool execution timed out"}
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from enabled servers"""
        try:
            # Check if we have any enabled servers first
            enabled_servers = await self.list_enabled_servers()
            if not enabled_servers:
                logger.info("No enabled servers found, no tools available")
                return []

            # Try to list tools with a shorter timeout
            result = await asyncio.wait_for(
                self._run_command(["docker", "mcp", "tools", "list", "--format", "json"]),
                timeout=10.0,  # 10 second timeout instead of default
            )

            if result.returncode == 0:
                try:
                    tools_data = json.loads(result.stdout)
                    return tools_data if isinstance(tools_data, list) else []
                except json.JSONDecodeError:
                    # Fallback to parsing text output
                    lines = result.stdout.strip().split("\n")
                    tools = []
                    for line in lines:
                        if line.strip() and not line.startswith("#"):
                            parts = line.split(None, 1)  # Split on first whitespace
                            if len(parts) >= 1:
                                tools.append(
                                    {
                                        "name": parts[0],
                                        "description": parts[1] if len(parts) > 1 else "",
                                        "server": "unknown",
                                    }
                                )
                    return tools
            else:
                logger.warning(f"Failed to list tools: {result.stderr}")
                # Return placeholder info about enabled servers instead
                return [
                    {
                        "name": f"{server['name']}_tools",
                        "description": f"Tools from {server['name']} server (gateway not running)",
                        "server": server["name"],
                        "status": "requires_gateway",
                    }
                    for server in enabled_servers
                ]

        except asyncio.TimeoutError:
            logger.warning("Tools listing timed out - Docker MCP Gateway may not be running")
            # Return helpful information about enabled servers
            enabled_servers = await self.list_enabled_servers()
            return [
                {
                    "name": f"{server['name']}_gateway_required",
                    "description": f"Tools from {server['name']} require Docker MCP Gateway to be running. Use 'docker mcp gateway run' to start it.",
                    "server": server["name"],
                    "status": "gateway_required",
                }
                for server in enabled_servers
            ]

        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            return []


# Global Docker MCP manager
docker_manager = DockerMCPManager()

# Global Pack manager
pack_manager = PackManager(docker_manager)


@mcp.tool()
async def hello_orbit(message: str = "Hello from Orbit-MCP!") -> str:
    """Test connectivity and show Orbit-MCP status"""

    # Check Docker MCP availability
    docker_available = await docker_manager.check_availability()

    # Get basic stats
    enabled_servers = await docker_manager.list_enabled_servers() if docker_available else []
    available_tools = await docker_manager.list_available_tools() if docker_available else []
    available_packs = await pack_manager.list_packs() if docker_available else []

    status_message = f"""🛰️ {message}

=== ORBIT-MCP STATUS ===
Docker MCP Gateway: {"✅ Available" if docker_available else "❌ Not Available"}
Enabled Servers: {len(enabled_servers)}
Available Tools: {len(available_tools)}
Company Packs: {len(available_packs)}

=== ENABLED SERVERS ===
{chr(10).join([f"• {s['name']} ({s['status']})" for s in enabled_servers]) if enabled_servers else "None"}

=== AVAILABLE PACKS ===
{chr(10).join([f"• {p['name']} - {p.get('description', 'No description')}" for p in available_packs]) if available_packs else "None (create with create_company_pack_template)"}

=== NEXT STEPS ===
1. Use create_company_pack_template('frontend-stack') for quick setup
2. Use install_pack to enable entire company toolchains  
3. Use list_available_servers to see what you can enable individually
4. Use enable_server to enable specific Docker MCP servers
""".strip()

    return status_message


@mcp.tool()
async def list_available_servers() -> List[Dict[str, str]]:
    """List all available MCP servers from Docker MCP catalog

    Returns a list of server dictionaries with name, description, and status.
    Use this to see what servers you can enable with enable_server.
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    servers = await docker_manager.list_available_servers()
    logger.info(f"Found {len(servers)} available servers")
    return servers


@mcp.tool()
async def enable_server(server_name: str) -> Dict[str, Any]:
    """Enable a specific Docker MCP server by name (with OAuth-first authentication)

    Args:
        server_name: Name of the server to enable (e.g., 'github', 'slack', 'notion')

    Returns:
        Dictionary with success status, message, and authentication details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    # Step 1: Check authentication requirements
    auth_info = await docker_manager.check_server_auth_requirements(server_name)

    if "error" in auth_info:
        return {
            "success": False,
            "server_name": server_name,
            "error": auth_info["error"],
            "message": f"Failed to check authentication requirements for {server_name}",
        }

    if not auth_info.get("found"):
        return {
            "success": False,
            "server_name": server_name,
            "error": "Server not found",
            "message": f"Server '{server_name}' not found in Docker MCP catalog",
        }

    # Step 2: Handle authentication if required
    if auth_info.get("auth_required"):
        oauth_provider = auth_info.get("oauth_provider")

        if oauth_provider:
            # Check if OAuth is already authorized
            if not auth_info.get("oauth_authorized", False):
                return {
                    "success": False,
                    "server_name": server_name,
                    "auth_required": True,
                    "oauth_provider": oauth_provider,
                    "message": f"Authentication required for {server_name}. Use authorize_oauth('{oauth_provider}') first.",
                    "next_step": f"authorize_oauth('{oauth_provider}')",
                    "auth_info": auth_info,
                }
            else:
                logger.info(f"✅ OAuth already authorized for {oauth_provider}")
        else:
            # Server requires secrets but no OAuth available
            return {
                "success": False,
                "server_name": server_name,
                "auth_required": True,
                "message": f"Authentication required for {server_name}. This server requires manual secret configuration.",
                "auth_info": auth_info,
            }

    # Step 3: Enable the server
    result = await docker_manager.enable_server(server_name)

    # Add authentication info to the result
    if result.get("success"):
        result["auth_info"] = auth_info
        if auth_info.get("oauth_authorized"):
            result["message"] += f" (OAuth authenticated via {auth_info.get('oauth_provider')})"
        
        # Restart gateway if running to pick up the new server
        if docker_manager.gateway_running:
            await docker_manager.stop_gateway()
            await docker_manager.start_gateway()
            logger.info(f"Restarted gateway to pick up server '{server_name}'")

    logger.info(f"Enable server '{server_name}' result: {result['success']}")
    return result


@mcp.tool()
async def list_enabled_servers() -> List[Dict[str, str]]:
    """List currently enabled MCP servers

    Returns a list of enabled server dictionaries with name, status, and container info.
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    servers = await docker_manager.list_enabled_servers()
    logger.info(f"Found {len(servers)} enabled servers")
    return servers


@mcp.tool()
async def list_oauth_providers() -> List[Dict[str, Any]]:
    """List available OAuth providers and their authorization status

    Returns a list of OAuth providers with their authorization status.
    Use this to see which services support OAuth and whether they're authorized.
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    providers = await docker_manager.list_oauth_providers()
    logger.info(f"Found {len(providers)} OAuth providers")
    return providers


@mcp.tool()
async def authorize_oauth(provider: str) -> Dict[str, Any]:
    """Start OAuth authorization flow for a provider (e.g., 'github', 'gdrive')

    Args:
        provider: OAuth provider name (e.g., 'github', 'gdrive')

    Returns:
        Dictionary with success status and authorization details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    result = await docker_manager.authorize_oauth_provider(provider)
    logger.info(f"OAuth authorization for '{provider}' result: {result['success']}")
    return result


@mcp.tool()
async def revoke_oauth(provider: str) -> Dict[str, Any]:
    """Revoke OAuth authorization for a provider

    Args:
        provider: OAuth provider name (e.g., 'github', 'gdrive')

    Returns:
        Dictionary with success status and revocation details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    result = await docker_manager.revoke_oauth_provider(provider)
    logger.info(f"OAuth revocation for '{provider}' result: {result['success']}")
    return result


@mcp.tool()
async def disable_server(server_name: str) -> Dict[str, Any]:
    """Disable a specific Docker MCP server by name

    Args:
        server_name: Name of the server to disable (e.g., 'github', 'slack', 'notion')

    Returns:
        Dictionary with success status and server removal details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await docker_manager.disable_server(server_name)
    
    # Restart gateway if running to remove the server's tools
    if result.get("success") and docker_manager.gateway_running:
        await docker_manager.stop_gateway()
        await docker_manager.start_gateway()
        logger.info(f"Restarted gateway after disabling server '{server_name}'")
    
    logger.info(f"Disable server '{server_name}' result: {result['success']}")
    return result


@mcp.tool()
async def reset_all_servers() -> Dict[str, Any]:
    """Disable all currently enabled MCP servers (company reset functionality)

    Returns:
        Dictionary with success status and list of disabled servers
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await docker_manager.reset_all_servers()
    disabled_count = len(result.get("servers_disabled", []))
    logger.info(f"Reset all servers result: {result['success']}, disabled {disabled_count} servers")
    return result


@mcp.tool()
async def check_server_auth(server_name: str) -> Dict[str, Any]:
    """Check authentication requirements and status for a server

    Args:
        server_name: Name of the server to check (e.g., 'github', 'slack')

    Returns:
        Dictionary with authentication requirements and current status
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    auth_info = await docker_manager.check_server_auth_requirements(server_name)
    logger.info(
        f"Authentication check for '{server_name}': auth_required={auth_info.get('auth_required', False)}"
    )
    return auth_info


@mcp.tool()
async def start_gateway() -> Dict[str, Any]:
    """Start the Docker MCP Gateway for tool execution

    Returns:
        Dictionary with success status and gateway details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    result = await docker_manager.start_gateway()
    logger.info(f"Start gateway result: {result.get('success', False)}")
    return result


@mcp.tool()
async def stop_gateway() -> Dict[str, Any]:
    """Stop the Docker MCP Gateway

    Returns:
        Dictionary with success status and details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    result = await docker_manager.stop_gateway()
    logger.info(f"Stop gateway result: {result.get('success', False)}")
    return result


@mcp.tool()
async def gateway_status() -> Dict[str, Any]:
    """Check the status of the Docker MCP Gateway

    Returns:
        Dictionary with gateway status and details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    result = await docker_manager.gateway_status()
    logger.info(f"Gateway status: running={result.get('running', False)}")
    return result


@mcp.tool()
async def discover_gateway_tools() -> List[Dict[str, Any]]:
    """Discover tools available from enabled Docker MCP servers

    Returns:
        List of tool definitions from enabled servers
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    # Use CLI approach - no gateway needed for discovery
    tools = await docker_manager.discover_tools_from_gateway()
    logger.info(f"Discovered {len(tools)} tools from enabled servers")
    return tools


@mcp.tool()
async def call_gateway_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool from enabled Docker MCP servers

    Args:
        tool_name: Name of the tool to call (e.g., 'create_issue', 'search_repositories')
        arguments: Dictionary of arguments to pass to the tool

    Returns:
        Dictionary with tool execution result
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    # Use CLI approach - direct tool execution
    result = await docker_manager.call_gateway_tool(tool_name, arguments)
    logger.info(f"Tool call '{tool_name}' result: {result.get('success', False)}")
    return result


@mcp.tool()
async def list_enabled_tools() -> List[Dict[str, Any]]:
    """List all available tools from currently enabled servers

    Returns a list of tool dictionaries with name, description, and server info.
    Use this after enabling servers to see what tools are available.
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP Gateway not available. Please install Docker MCP.")

    tools = await docker_manager.list_available_tools()
    logger.info(f"Found {len(tools)} available tools")
    return tools


# ===== PACK MANAGEMENT TOOLS =====

@mcp.tool()
async def create_pack(pack_name: str, description: str, servers: List[str]) -> Dict[str, Any]:
    """Create a new company/team pack with specific MCP servers

    Args:
        pack_name: Name of the pack (e.g., 'frontend-stack', 'acme-devops')
        description: Human-readable description of the pack
        servers: List of server names to include in the pack

    Returns:
        Dictionary with success status and pack creation details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await pack_manager.create_pack(pack_name, description, servers)
    logger.info(f"Create pack '{pack_name}' result: {result['success']}")
    return result


@mcp.tool()
async def install_pack(pack_name: str, enable_oauth: bool = True) -> Dict[str, Any]:
    """Install a pack by enabling all its servers

    Args:
        pack_name: Name of the pack to install (e.g., 'frontend-stack')
        enable_oauth: Whether to prompt for OAuth authorization if needed

    Returns:
        Dictionary with installation results and any auth requirements
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await pack_manager.install_pack(pack_name, enable_oauth)
    enabled_count = len(result.get("servers_enabled", []))
    logger.info(f"Install pack '{pack_name}' result: {result['success']}, enabled {enabled_count} servers")
    return result


@mcp.tool()
async def uninstall_pack(pack_name: str) -> Dict[str, Any]:
    """Uninstall a pack by disabling all its servers

    Args:
        pack_name: Name of the pack to uninstall

    Returns:
        Dictionary with uninstallation results
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await pack_manager.uninstall_pack(pack_name)
    disabled_count = len(result.get("servers_disabled", []))
    logger.info(f"Uninstall pack '{pack_name}' result: {result['success']}, disabled {disabled_count} servers")
    return result


@mcp.tool()
async def list_packs() -> List[Dict[str, Any]]:
    """List all available company/team packs

    Returns:
        List of pack configurations with server details
    """

    packs = await pack_manager.list_packs()
    logger.info(f"Found {len(packs)} available packs")
    return packs


@mcp.tool()
async def get_pack_info(pack_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific pack

    Args:
        pack_name: Name of the pack to inspect

    Returns:
        Dictionary with pack information and server status
    """

    pack_info = await pack_manager.get_pack_info(pack_name)
    logger.info(f"Pack info for '{pack_name}': found={pack_info.get('found', False)}")
    return pack_info


@mcp.tool()
async def create_company_pack_template(template_name: str) -> Dict[str, Any]:
    """Create a predefined company pack from templates

    Args:
        template_name: Name of the template ('frontend-stack', 'backend-stack', 'devops-stack', 'data-stack', 'productivity-stack', 'web-scraping-stack')

    Returns:
        Dictionary with pack creation results
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    if template_name not in COMPANY_PACK_TEMPLATES:
        available_templates = list(COMPANY_PACK_TEMPLATES.keys())
        return {
            "success": False,
            "template_name": template_name,
            "error": f"Template '{template_name}' not found",
            "available_templates": available_templates,
        }

    template = COMPANY_PACK_TEMPLATES[template_name]
    result = await pack_manager.create_pack(
        pack_name=template_name,
        description=template["description"],
        servers=template["servers"],
        tags=template["tags"],
    )

    logger.info(f"Create company pack template '{template_name}' result: {result['success']}")
    return result


@mcp.tool()
async def update_pack(pack_name: str, description: Optional[str] = None, 
                     servers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Update an existing pack with new configuration

    Args:
        pack_name: Name of the pack to update
        description: New description (optional)
        servers: New list of servers (optional)

    Returns:
        Dictionary with success status and update details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await pack_manager.update_pack(pack_name, description, servers)
    changes = len(result.get("changes", []))
    logger.info(f"Update pack '{pack_name}' result: {result['success']}, made {changes} changes")
    return result


@mcp.tool()
async def add_server_to_pack(pack_name: str, server_name: str) -> Dict[str, Any]:
    """Add a server to an existing pack

    Args:
        pack_name: Name of the pack
        server_name: Name of the server to add

    Returns:
        Dictionary with success status and operation details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await pack_manager.add_server_to_pack(pack_name, server_name)
    logger.info(f"Add server '{server_name}' to pack '{pack_name}' result: {result['success']}")
    return result


@mcp.tool()
async def remove_server_from_pack(pack_name: str, server_name: str) -> Dict[str, Any]:
    """Remove a server from an existing pack

    Args:
        pack_name: Name of the pack
        server_name: Name of the server to remove

    Returns:
        Dictionary with success status and operation details
    """

    # Check Docker MCP availability first
    if not await docker_manager.check_availability():
        raise Exception("Docker MCP not available. Please install Docker MCP.")

    result = await pack_manager.remove_server_from_pack(pack_name, server_name)
    logger.info(f"Remove server '{server_name}' from pack '{pack_name}' result: {result['success']}")
    return result


if __name__ == "__main__":
    logger.info("🚀 Starting Orbit-MCP Server...")
    mcp.run()
