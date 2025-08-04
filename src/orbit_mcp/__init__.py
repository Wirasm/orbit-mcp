def main() -> None:
    print("Hello from orbit-mcp!")

def mcp_main():
    """Entry point for MCP server"""
    from orbit_mcp.mcp_server import mcp
    mcp.run()
