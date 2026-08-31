"""EduPath MCP-compatible tool protocol package."""

from app.mcp.protocol import InProcessMCPClient, MCPToolServer, ToolResult
from app.mcp.tool_server import build_edupath_mcp_server, build_mcp_client

__all__ = [
    "InProcessMCPClient",
    "MCPToolServer",
    "ToolResult",
    "build_edupath_mcp_server",
    "build_mcp_client",
]
