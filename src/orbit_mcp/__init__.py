def main() -> None:
    print("Hello from orbit-mcp!")

def mcp_main():
    """Entry point for MCP server"""
    import logging
    import sys
    import os
    
    # Disable all logging to stderr when running as MCP server
    logging.disable(logging.CRITICAL)
    
    # Disable rich console output if it's being used
    os.environ['TERM'] = 'dumb'
    
    # Ensure stdout is unbuffered for real-time communication
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
    
    # Import after setting environment
    from orbit_mcp.mcp_server import mcp
    
    try:
        # Run with stdio transport
        mcp.run(transport="stdio", show_banner=False)
    except (KeyboardInterrupt, EOFError):
        # Clean shutdown on interrupt
        sys.exit(0)
    except Exception as e:
        # Silent exit on other errors to avoid polluting stdio
        sys.exit(1)
