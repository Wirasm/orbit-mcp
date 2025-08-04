#!/usr/bin/env python3
"""
Pack Manager - Company/Team-specific tool collections for Orbit-MCP
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class PackManager:
    """Manages company/team-specific collections of MCP servers (packs)"""

    def __init__(self, docker_manager):
        self.docker_manager = docker_manager
        self.packs_dir = os.path.expanduser("~/.docker/mcp/packs")
        self._ensure_packs_directory()

    def _ensure_packs_directory(self):
        """Ensure the packs directory exists"""
        os.makedirs(self.packs_dir, exist_ok=True)

    def _get_pack_file_path(self, pack_name: str) -> str:
        """Get the file path for a pack configuration"""
        return os.path.join(self.packs_dir, f"{pack_name}.yaml")

    async def create_pack(self, pack_name: str, description: str, servers: List[str], 
                         tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new server pack

        Args:
            pack_name: Name of the pack (e.g., 'frontend-stack', 'devops-tools')
            description: Human-readable description of the pack
            servers: List of server names to include in the pack
            tags: Optional tags for categorization

        Returns:
            Dictionary with success status and pack details
        """
        try:
            pack_file = self._get_pack_file_path(pack_name)
            
            # Check if pack already exists
            if os.path.exists(pack_file):
                return {
                    "success": False,
                    "pack_name": pack_name,
                    "error": f"Pack '{pack_name}' already exists",
                    "message": f"Pack '{pack_name}' already exists. Use update_pack to modify it.",
                }

            # Validate that all servers exist in the catalog
            available_servers = await self.docker_manager.list_available_servers()
            available_names = {s["name"] for s in available_servers}
            
            invalid_servers = [s for s in servers if s not in available_names]
            if invalid_servers:
                return {
                    "success": False,
                    "pack_name": pack_name,
                    "error": f"Invalid servers: {', '.join(invalid_servers)}",
                    "invalid_servers": invalid_servers,
                    "available_servers": sorted(list(available_names)),
                }

            # Create pack configuration
            pack_config = {
                "name": pack_name,
                "description": description,
                "servers": servers,
                "tags": tags or [],
                "created_at": self._get_timestamp(),
                "updated_at": self._get_timestamp(),
                "version": "1.0.0",
            }

            # Write pack file
            with open(pack_file, "w") as f:
                yaml.dump(pack_config, f, default_flow_style=False, sort_keys=False)

            logger.info(f" Created pack '{pack_name}' with {len(servers)} servers")
            return {
                "success": True,
                "pack_name": pack_name,
                "message": f"Successfully created pack '{pack_name}'",
                "pack_config": pack_config,
            }

        except Exception as e:
            logger.error(f"L Error creating pack '{pack_name}': {str(e)}")
            return {
                "success": False,
                "pack_name": pack_name,
                "error": str(e),
                "message": f"Error creating pack '{pack_name}'",
            }

    async def install_pack(self, pack_name: str, enable_oauth: bool = True) -> Dict[str, Any]:
        """Install a pack by enabling all its servers

        Args:
            pack_name: Name of the pack to install
            enable_oauth: Whether to prompt for OAuth authorization if needed

        Returns:
            Dictionary with installation results and any auth requirements
        """
        try:
            pack_file = self._get_pack_file_path(pack_name)
            
            if not os.path.exists(pack_file):
                return {
                    "success": False,
                    "pack_name": pack_name,
                    "error": f"Pack '{pack_name}' not found",
                    "available_packs": await self.list_packs(),
                }

            # Load pack configuration
            with open(pack_file, "r") as f:
                pack_config = yaml.safe_load(f)

            servers = pack_config.get("servers", [])
            results = {
                "success": True,
                "pack_name": pack_name,
                "servers_enabled": [],
                "servers_failed": [],
                "auth_required": [],
                "summary": {},
            }

            # Enable each server in the pack
            for server_name in servers:
                try:
                    result = await self.docker_manager.enable_server(server_name)
                    
                    if result.get("success"):
                        results["servers_enabled"].append(server_name)
                    elif result.get("auth_required") and enable_oauth:
                        # Handle OAuth requirement
                        oauth_provider = result.get("oauth_provider")
                        if oauth_provider:
                            results["auth_required"].append({
                                "server": server_name,
                                "provider": oauth_provider,
                                "next_step": f"authorize_oauth('{oauth_provider}')",
                            })
                        else:
                            results["servers_failed"].append({
                                "server": server_name,
                                "error": result.get("error", "Authentication required"),
                            })
                    else:
                        results["servers_failed"].append({
                            "server": server_name,
                            "error": result.get("error", "Unknown error"),
                        })

                except Exception as e:
                    results["servers_failed"].append({
                        "server": server_name,
                        "error": str(e),
                    })

            # Generate summary
            enabled_count = len(results["servers_enabled"])
            failed_count = len(results["servers_failed"])
            auth_count = len(results["auth_required"])
            
            results["summary"] = {
                "total_servers": len(servers),
                "enabled": enabled_count,
                "failed": failed_count,
                "auth_required": auth_count,
            }

            # Determine overall success
            if failed_count > 0 or auth_count > 0:
                results["success"] = False
                results["message"] = f"Pack '{pack_name}' partially installed: {enabled_count}/{len(servers)} servers enabled"
            else:
                results["message"] = f"Pack '{pack_name}' successfully installed: {enabled_count} servers enabled"

            logger.info(f"Pack '{pack_name}' install result: {enabled_count}/{len(servers)} servers enabled")
            return results

        except Exception as e:
            logger.error(f"L Error installing pack '{pack_name}': {str(e)}")
            return {
                "success": False,
                "pack_name": pack_name,
                "error": str(e),
                "message": f"Error installing pack '{pack_name}'",
            }

    async def uninstall_pack(self, pack_name: str) -> Dict[str, Any]:
        """Uninstall a pack by disabling all its servers

        Args:
            pack_name: Name of the pack to uninstall

        Returns:
            Dictionary with uninstallation results
        """
        try:
            pack_file = self._get_pack_file_path(pack_name)
            
            if not os.path.exists(pack_file):
                return {
                    "success": False,
                    "pack_name": pack_name,
                    "error": f"Pack '{pack_name}' not found",
                }

            # Load pack configuration
            with open(pack_file, "r") as f:
                pack_config = yaml.safe_load(f)

            servers = pack_config.get("servers", [])
            results = {
                "success": True,
                "pack_name": pack_name,
                "servers_disabled": [],
                "servers_failed": [],
                "servers_not_enabled": [],
            }

            # Disable each server in the pack
            for server_name in servers:
                try:
                    result = await self.docker_manager.disable_server(server_name)
                    
                    if result.get("success"):
                        results["servers_disabled"].append(server_name)
                    elif "not currently enabled" in result.get("message", ""):
                        results["servers_not_enabled"].append(server_name)
                    else:
                        results["servers_failed"].append({
                            "server": server_name,
                            "error": result.get("error", "Unknown error"),
                        })

                except Exception as e:
                    results["servers_failed"].append({
                        "server": server_name,
                        "error": str(e),
                    })

            # Generate summary
            disabled_count = len(results["servers_disabled"])
            failed_count = len(results["servers_failed"])
            not_enabled_count = len(results["servers_not_enabled"])
            
            if failed_count > 0:
                results["success"] = False
                results["message"] = f"Pack '{pack_name}' partially uninstalled: {disabled_count} disabled, {failed_count} failed"
            else:
                results["message"] = f"Pack '{pack_name}' uninstalled: {disabled_count} servers disabled, {not_enabled_count} were not enabled"

            logger.info(f"Pack '{pack_name}' uninstall result: {disabled_count} servers disabled")
            return results

        except Exception as e:
            logger.error(f"L Error uninstalling pack '{pack_name}': {str(e)}")
            return {
                "success": False,
                "pack_name": pack_name,
                "error": str(e),
                "message": f"Error uninstalling pack '{pack_name}'",
            }

    async def list_packs(self) -> List[Dict[str, Any]]:
        """List all available packs

        Returns:
            List of pack configurations
        """
        try:
            packs = []
            
            if not os.path.exists(self.packs_dir):
                return packs

            for filename in os.listdir(self.packs_dir):
                if filename.endswith(".yaml") or filename.endswith(".yml"):
                    pack_file = os.path.join(self.packs_dir, filename)
                    try:
                        with open(pack_file, "r") as f:
                            pack_config = yaml.safe_load(f)
                            if pack_config:
                                packs.append(pack_config)
                    except Exception as e:
                        logger.warning(f"Failed to load pack file {filename}: {str(e)}")

            logger.info(f"Found {len(packs)} available packs")
            return sorted(packs, key=lambda x: x.get("name", ""))

        except Exception as e:
            logger.error(f"Error listing packs: {str(e)}")
            return []

    async def get_pack_info(self, pack_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific pack

        Args:
            pack_name: Name of the pack

        Returns:
            Dictionary with pack information and server status
        """
        try:
            pack_file = self._get_pack_file_path(pack_name)
            
            if not os.path.exists(pack_file):
                return {
                    "found": False,
                    "pack_name": pack_name,
                    "error": f"Pack '{pack_name}' not found",
                }

            # Load pack configuration
            with open(pack_file, "r") as f:
                pack_config = yaml.safe_load(f)

            # Check status of each server in the pack
            enabled_servers = await self.docker_manager.list_enabled_servers()
            enabled_names = {s["name"] for s in enabled_servers}
            
            server_status = []
            for server_name in pack_config.get("servers", []):
                server_status.append({
                    "name": server_name,
                    "enabled": server_name in enabled_names,
                })

            pack_config["server_status"] = server_status
            pack_config["found"] = True
            pack_config["enabled_count"] = len([s for s in server_status if s["enabled"]])
            pack_config["total_count"] = len(server_status)

            return pack_config

        except Exception as e:
            logger.error(f"Error getting pack info for '{pack_name}': {str(e)}")
            return {
                "found": False,
                "pack_name": pack_name,
                "error": str(e),
            }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


# Predefined company pack templates
COMPANY_PACK_TEMPLATES = {
    "frontend-stack": {
        "description": "Frontend development tools and services",
        "servers": ["github", "slack", "notion", "figma", "vercel"],
        "tags": ["frontend", "web", "ui", "development"],
    },
    "backend-stack": {
        "description": "Backend development and infrastructure tools",
        "servers": ["github", "docker", "aws", "postgres", "redis"],
        "tags": ["backend", "api", "database", "infrastructure"],
    },
    "devops-stack": {
        "description": "DevOps and infrastructure management tools",
        "servers": ["github", "docker", "aws", "kubernetes", "terraform", "grafana"],
        "tags": ["devops", "infrastructure", "monitoring", "deployment"],
    },
    "data-stack": {
        "description": "Data science and analytics tools",
        "servers": ["github", "postgres", "bigquery", "jupyter", "dbt"],
        "tags": ["data", "analytics", "ml", "database"],
    },
    "productivity-stack": {
        "description": "Team productivity and communication tools",
        "servers": ["slack", "notion", "calendar", "drive", "zoom"],
        "tags": ["productivity", "communication", "collaboration"],
    },
}