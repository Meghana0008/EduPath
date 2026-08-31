"""Optional FastMCP / stdio export for EduPath tools.

Install the optional `mcp` package to run:
  python -m app.mcp.fastmcp_server

When FastMCP is unavailable, the in-process MCPToolServer in
`app.mcp.protocol` remains the primary L2 tool boundary used by PolicyAgent.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _build_stdio_handlers() -> dict[str, Any]:
    """Lazy import app stack only when launching as a process."""
    from app.database import SessionLocal
    from app.mcp.tool_server import build_edupath_mcp_server
    from app.models import User

    db = SessionLocal()
    user = db.query(User).filter(User.email == "meghana@edupath.ai").first()
    if not user:
        user = db.query(User).first()
    if not user:
        raise RuntimeError("No user found to bind MCP server session")
    server = build_edupath_mcp_server(db, user)
    return {"db": db, "server": server}


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except Exception:
        # Fallback: JSON-RPC-ish stdio loop over in-process MCPToolServer
        print(
            json.dumps(
                {
                    "info": "FastMCP package not installed; using EduPath MCPToolServer stdio bridge",
                    "protocol": "edupath-mcp/1.0",
                }
            ),
            flush=True,
        )
        ctx = _build_stdio_handlers()
        server = ctx["server"]
        print(json.dumps({"tools": server.list_tools()}), flush=True)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                print(json.dumps({"ok": False, "error": "invalid json"}), flush=True)
                continue
            method = req.get("method")
            if method == "tools/list":
                print(json.dumps({"tools": server.list_tools()}), flush=True)
            elif method == "tools/call":
                name = (req.get("params") or {}).get("name")
                args = (req.get("params") or {}).get("arguments") or {}
                result = server.call_tool(name, args)
                print(
                    json.dumps(
                        {
                            "ok": result.ok,
                            "content": result.content,
                            "error": result.error,
                        },
                        default=str,
                    ),
                    flush=True,
                )
            elif method in {"shutdown", "exit"}:
                break
            else:
                print(json.dumps({"ok": False, "error": f"unknown method {method}"}), flush=True)
        ctx["db"].close()
        return

    mcp = FastMCP("edupath-scholarship-mcp")
    ctx = _build_stdio_handlers()
    server = ctx["server"]

    for tool in server.list_tools():
        name = tool["name"]
        description = tool.get("description") or name

        def _make_handler(tool_name: str):
            def handler(**kwargs: Any) -> Any:
                result = server.call_tool(tool_name, kwargs)
                if not result.ok:
                    return {"error": result.error}
                return result.content

            handler.__name__ = tool_name
            handler.__doc__ = description
            return handler

        mcp.tool(name=name, description=description)(_make_handler(name))

    mcp.run()


if __name__ == "__main__":
    main()
