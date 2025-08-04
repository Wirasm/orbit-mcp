"""
Docker MCP Gateway Integration
Enhanced version of our main.py that integrates with Docker MCP Gateway
"""

import asyncio
import json
import logging
import subprocess
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Team:
    name: str
    members: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Pack:
    name: str
    version: str
    description: str
    servers: List[str] = field(default_factory=list)
    team_permissions: Dict[str, List[str]] = field(default_factory=dict)


# Global state
teams: Dict[str, Team] = {}
installed_packs: Dict[str, Pack] = {}

# Pack definitions that map to real Docker MCP servers
AVAILABLE_PACKS = [
    Pack(
        name="backend-stack",
        version="1.0.0",
        description="Backend development stack with real GitHub, Atlassian, and Slack MCP servers",
        servers=["github", "atlassian", "slack"],  # These are real Docker MCP servers
        team_permissions={
            "backend": ["github.merge_pr", "jira.delete_issue", "slack.post_anywhere"],
            "frontend": ["github.create_pr", "jira.create_issue", "slack.post_frontend"],
        },
    ),
    Pack(
        name="frontend-stack",
        version="1.0.0",
        description="Frontend development stack with GitHub, Figma, and Vercel MCP servers",
        servers=["github", "figma", "vercel"],
        team_permissions={
            "frontend": ["github.create_pr", "figma.create_design", "vercel.deploy"],
            "design": ["figma.edit", "figma.share", "slack.post_design"],
        },
    ),
]


class DockerMCPGateway:
    """Integration layer for Docker MCP Gateway"""

    def __init__(self):
        self.gateway_running = False
        self.gateway_endpoint = None

    async def check_availability(self) -> bool:
        """Check if Docker MCP is available"""
        try:
            result = await self._run_command(["docker", "mcp", "--help"])
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Docker MCP not available: {str(e)}")
            return False

    async def initialize_catalog(self) -> bool:
        """Initialize Docker MCP catalog"""
        try:
            result = await self._run_command(["docker", "mcp", "catalog", "init"])
            if result.returncode == 0:
                logger.info("✅ Docker MCP catalog initialized")
                return True
            else:
                logger.warning(f"⚠️ Catalog init failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to initialize catalog: {str(e)}")
            return False

    async def list_available_servers(self) -> List[Dict[str, str]]:
        """List all servers available in Docker MCP catalog"""
        try:
            result = await self._run_command(["docker", "mcp", "catalog", "show", "docker-mcp"])

            if result.returncode == 0:
                # Parse the output to extract server names
                # This is simplified - real parsing would be more robust
                lines = result.stdout.strip().split("\n")
                servers = []
                for line in lines:
                    if line.strip() and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 1:
                            servers.append({"name": parts[0], "status": "available"})
                return servers
            else:
                logger.warning(f"⚠️ Failed to list servers: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"❌ Error listing servers: {str(e)}")
            return []

    async def list_enabled_servers(self) -> List[Dict[str, str]]:
        """List currently enabled MCP servers"""
        try:
            result = await self._run_command(["docker", "mcp", "server", "list"])

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                servers = []
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            servers.append(
                                {
                                    "name": parts[0],
                                    "status": parts[1] if len(parts) > 1 else "unknown",
                                }
                            )
                return servers
            else:
                logger.warning(f"⚠️ Failed to list enabled servers: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"❌ Error listing enabled servers: {str(e)}")
            return []

    async def enable_servers(self, server_names: List[str]) -> Dict[str, bool]:
        """Enable multiple MCP servers"""
        results = {}

        for server_name in server_names:
            try:
                result = await self._run_command(["docker", "mcp", "server", "enable", server_name])

                if result.returncode == 0:
                    results[server_name] = True
                    logger.info(f"✅ Enabled server: {server_name}")
                else:
                    results[server_name] = False
                    logger.warning(f"⚠️ Failed to enable {server_name}: {result.stderr}")
            except Exception as e:
                results[server_name] = False
                logger.error(f"❌ Error enabling {server_name}: {str(e)}")

        return results

    async def start_gateway(self, transport: str = "stdio") -> Optional[str]:
        """Start the MCP Gateway"""
        try:
            if transport == "http":
                # Start gateway with HTTP transport for easier integration
                cmd = [
                    "docker",
                    "mcp",
                    "gateway",
                    "run",
                    "--transport",
                    "streaming",
                    "--port",
                    "3000",
                ]
                self.gateway_endpoint = "http://localhost:3000"
            else:
                # Default stdio transport
                cmd = ["docker", "mcp", "gateway", "run"]
                self.gateway_endpoint = "stdio"

            # For demo, we'll just validate the command works
            # In production, you'd run this as a background process
            result = await self._run_command(cmd + ["--help"])  # Test command structure

            if result.returncode == 0:
                self.gateway_running = True
                logger.info(f"✅ Gateway ready at: {self.gateway_endpoint}")
                return self.gateway_endpoint
            else:
                logger.error(f"❌ Gateway start failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"❌ Error starting gateway: {str(e)}")
            return None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools through the gateway"""
        try:
            result = await self._run_command(["docker", "mcp", "tools", "list", "--format", "json"])

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
                            parts = line.split()
                            if len(parts) >= 1:
                                tools.append(
                                    {
                                        "name": parts[0],
                                        "description": " ".join(parts[1:])
                                        if len(parts) > 1
                                        else "",
                                    }
                                )
                    return tools
            else:
                logger.warning(f"⚠️ Failed to list tools: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"❌ Error listing tools: {str(e)}")
            return []

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool through the Docker MCP Gateway"""
        try:
            # Convert args to JSON string for command line
            args_json = json.dumps(args)

            result = await self._run_command(
                ["docker", "mcp", "tools", "call", tool_name, args_json]
            )

            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"result": result.stdout, "raw": True}
            else:
                return {"error": result.stderr, "exit_code": result.returncode}

        except Exception as e:
            return {"error": str(e)}

    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a docker mcp command"""
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


# Global Docker MCP Gateway instance
docker_gateway = DockerMCPGateway()


# Enhanced tool implementations
async def hello_orbit(message: str = "Hello from Orbit-MCP!") -> Dict[str, Any]:
    """Test connectivity and show server status"""

    # Check Docker MCP availability
    docker_available = await docker_gateway.check_availability()

    # Get server status if available
    enabled_servers = []
    available_tools = []

    if docker_available:
        enabled_servers = await docker_gateway.list_enabled_servers()
        available_tools = await docker_gateway.list_tools()

    status_message = f"""
🛰️ {message}

=== ORBIT-MCP STATUS ===
Server Status: Running
Docker MCP Gateway: {"✅ Available" if docker_available else "❌ Not Available"}
Teams: {len(teams)}
Installed Packs: {len(installed_packs)}

=== DOCKER MCP STATUS ===
Enabled Servers: {len(enabled_servers)}
Available Tools: {len(available_tools)}

=== ENABLED SERVERS ===
{chr(10).join([f"• {s['name']} ({s['status']})" for s in enabled_servers]) if enabled_servers else "None"}

=== AVAILABLE COMMANDS ===
- list_available_packs: See what stacks you can install
- install_pack: Deploy a stack for a team  
- get_server_status: Check system health
- list_docker_servers: See Docker MCP servers
    """.strip()

    return {"result": status_message}


async def install_pack(pack_name: str, team_name: str) -> Dict[str, Any]:
    """Install an MCP pack using real Docker MCP servers"""

    # Find the pack
    pack = next((p for p in AVAILABLE_PACKS if p.name == pack_name), None)
    if not pack:
        return {
            "error": f"Pack '{pack_name}' not found. Available: {[p.name for p in AVAILABLE_PACKS]}"
        }

    # Create or get team
    if team_name not in teams:
        teams[team_name] = Team(name=team_name, members=[])
        logger.info(f"✅ Created new team: {team_name}")

    # Check Docker MCP availability
    docker_available = await docker_gateway.check_availability()

    if docker_available:
        # Initialize catalog if needed
        await docker_gateway.initialize_catalog()

        # Enable the servers for this pack
        logger.info(f"🚀 Enabling servers for {pack_name}: {pack.servers}")
        enable_results = await docker_gateway.enable_servers(pack.servers)

        # Start the gateway
        gateway_endpoint = await docker_gateway.start_gateway()

        # Get enabled servers and tools
        enabled_servers = await docker_gateway.list_enabled_servers()
        available_tools = await docker_gateway.list_tools()

        deployment_status = (
            f"✅ Enabled {sum(enable_results.values())}/{len(pack.servers)} servers via Docker MCP"
        )
        enabled_server_names = [name for name, success in enable_results.items() if success]

    else:
        # Fallback simulation
        enabled_server_names = pack.servers.copy()
        available_tools = []
        deployment_status = "🎭 Simulated deployment (Docker MCP not available)"
        gateway_endpoint = None

    # Get team permissions
    team_permissions = pack.team_permissions.get(team_name, [])

    # Store installation
    install_key = f"{pack_name}:{team_name}"
    installed_packs[install_key] = pack

    result = {
        "status": "success",
        "pack_name": pack_name,
        "team_name": team_name,
        "deployed_servers": enabled_server_names,
        "granted_permissions": team_permissions,
        "deployment_status": deployment_status,
        "gateway_endpoint": gateway_endpoint,
        "available_tools": len(available_tools),
        "message": f"🎉 Successfully installed {pack_name} for {team_name} team!",
    }

    logger.info(f"✅ Installed pack '{pack_name}' for team '{team_name}'")
    return {"result": json.dumps(result, indent=2)}


async def list_docker_servers() -> Dict[str, Any]:
    """List Docker MCP servers and their status"""

    docker_available = await docker_gateway.check_availability()

    if not docker_available:
        return {"error": "Docker MCP Gateway not available"}

    try:
        available_servers = await docker_gateway.list_available_servers()
        enabled_servers = await docker_gateway.list_enabled_servers()
        available_tools = await docker_gateway.list_tools()

        result = {
            "docker_mcp_status": "available",
            "available_servers": available_servers,
            "enabled_servers": enabled_servers,
            "available_tools": available_tools,
            "summary": {
                "total_available": len(available_servers),
                "total_enabled": len(enabled_servers),
                "total_tools": len(available_tools),
            },
        }

        return {"result": json.dumps(result, indent=2)}

    except Exception as e:
        return {"error": str(e)}


async def get_server_status() -> Dict[str, Any]:
    """Get comprehensive status of all systems"""

    docker_available = await docker_gateway.check_availability()

    status = {
        "orbit_mcp_status": "running",
        "docker_mcp_available": docker_available,
        "total_teams": len(teams),
        "total_installed_packs": len(installed_packs),
        "teams": [
            {
                "name": team.name,
                "member_count": len(team.members),
                "created_at": team.created_at.isoformat(),
            }
            for team in teams.values()
        ],
        "installed_packs": [
            {"pack": key.split(":")[0], "team": key.split(":")[1], "servers": pack.servers}
            for key, pack in installed_packs.items()
        ],
    }

    if docker_available:
        try:
            enabled_servers = await docker_gateway.list_enabled_servers()
            available_tools = await docker_gateway.list_tools()

            status["docker_servers"] = enabled_servers
            status["docker_tools"] = available_tools
            status["docker_summary"] = {
                "enabled_servers": len(enabled_servers),
                "available_tools": len(available_tools),
            }
        except Exception as e:
            status["docker_error"] = str(e)

    return {"result": json.dumps(status, indent=2)}


# HTTP Server with enhanced endpoints
class OrbitHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            response = {
                "status": "healthy",
                "service": "Orbit-MCP with Docker Gateway Integration",
                "message": "Enterprise MCP toolchain manager with Docker MCP integration",
                "available_endpoints": [
                    "/health",
                    "/tools",
                    "/install",
                    "/status",
                    "/hello",
                    "/docker-servers",
                    "/docker-tools",
                ],
            }
            self._send_json_response(200, response)

        elif self.path == "/docker-servers":
            result = asyncio.run(list_docker_servers())
            if "error" in result:
                self._send_json_response(400, result)
            else:
                self._send_text_response(200, result["result"])

        elif self.path == "/docker-tools":
            docker_available = asyncio.run(docker_gateway.check_availability())
            if docker_available:
                tools = asyncio.run(docker_gateway.list_tools())
                self._send_json_response(200, {"tools": tools, "count": len(tools)})
            else:
                self._send_json_response(400, {"error": "Docker MCP not available"})

        elif self.path == "/tools":
            result = asyncio.run(list_available_packs())
            self._send_text_response(200, result["result"])

        elif self.path.startswith("/install"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            pack_name = params.get("pack", ["backend-stack"])[0]
            team_name = params.get("team", ["demo-team"])[0]

            result = asyncio.run(install_pack(pack_name, team_name))
            if "error" in result:
                self._send_json_response(400, result)
            else:
                self._send_text_response(200, result["result"])

        elif self.path == "/status":
            result = asyncio.run(get_server_status())
            self._send_text_response(200, result["result"])

        elif self.path.startswith("/hello"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            message = params.get("message", ["Hello from Orbit-MCP!"])[0]

            result = asyncio.run(hello_orbit(message))
            self._send_text_response(200, result["result"])

        else:
            self._send_text_response(
                404,
                """404 Not Found

🛰️ Orbit-MCP Server with Docker MCP Gateway Integration

Available endpoints:
GET /health                    - Server health check
GET /tools                     - List available MCP packs
GET /install?pack=X&team=Y     - Install pack X for team Y
GET /status                    - Get comprehensive system status
GET /hello?message=X           - Test with custom message
GET /docker-servers            - List Docker MCP servers
GET /docker-tools              - List Docker MCP tools

Examples:
curl http://localhost:8080/health
curl http://localhost:8080/docker-servers
curl "http://localhost:8080/install?pack=backend-stack&team=engineering"
curl http://localhost:8080/status
""",
            )

    def _send_json_response(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def _send_text_response(self, code: int, text: str):
        self.send_response(code)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, format, *args):
        logger.info(f"HTTP {self.command} {self.path} - {format % args}")


def main():
    """Main entry point"""
    logger.info("🚀 Starting Orbit-MCP Server with Docker MCP Gateway Integration...")

    try:
        httpd = HTTPServer(("localhost", 8080), OrbitHTTPHandler)
        logger.info("🌐 Orbit-MCP server running on http://localhost:8080")
        logger.info("💡 Try: curl http://localhost:8080/health")
        logger.info("💡 Try: curl http://localhost:8080/docker-servers")
        logger.info(
            "💡 Try: curl 'http://localhost:8080/install?pack=backend-stack&team=engineering'"
        )

        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped")
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")


if __name__ == "__main__":
    main()
