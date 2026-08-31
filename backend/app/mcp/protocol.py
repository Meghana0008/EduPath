"""MCP-compatible tool protocol for EduPath.

Provides runtime tool discovery (`list_tools`) and invocation (`call_tool`)
with JSON Schema inputs/outputs. Works in-process for the agent loop and can
also be exported via FastMCP/stdio when the optional `mcp` package is installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = field(default_factory=dict)
    side_effect: bool = False


@dataclass
class ToolResult:
    ok: bool
    content: Any
    error: Optional[str] = None
    is_error: bool = False

    def as_observation(self) -> dict[str, Any]:
        if self.is_error or not self.ok:
            return {"ok": False, "error": self.error or "tool failed"}
        return {"ok": True, "result": self.content}


ToolHandler = Callable[[dict[str, Any]], Any]


class MCPToolServer:
    """Minimal MCP-style tool server: register, list, call."""

    def __init__(self, name: str = "edupath-mcp") -> None:
        self.name = name
        self._tools: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        *,
        output_schema: Optional[dict[str, Any]] = None,
        side_effect: bool = False,
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(fn: ToolHandler) -> ToolHandler:
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema or {"type": "object"},
                side_effect=side_effect,
            )
            self._handlers[name] = fn
            return fn

        return decorator

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: ToolHandler,
        *,
        side_effect: bool = False,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema,
            side_effect=side_effect,
        )
        self._handlers[name] = handler

    def list_tools(self) -> list[dict[str, Any]]:
        """MCP tools/list equivalent."""
        out = []
        for spec in self._tools.values():
            out.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.input_schema,
                    "outputSchema": spec.output_schema,
                    "annotations": {"sideEffect": spec.side_effect},
                }
            )
        return out

    def call_tool(self, name: str, arguments: Optional[dict[str, Any]] = None) -> ToolResult:
        """MCP tools/call equivalent with unknown-tool recovery."""
        arguments = arguments or {}
        if name not in self._handlers:
            return ToolResult(
                ok=False,
                content=None,
                error=f"Unknown tool '{name}'. Discover tools with list_tools().",
                is_error=True,
            )
        spec = self._tools[name]
        # Lightweight required-field validation
        required = list((spec.input_schema or {}).get("required") or [])
        missing = [r for r in required if r not in arguments]
        if missing:
            return ToolResult(
                ok=False,
                content=None,
                error=f"Invalid arguments for '{name}': missing {missing}",
                is_error=True,
            )
        try:
            result = self._handlers[name](arguments)
            return ToolResult(ok=True, content=result)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, content=None, error=str(exc), is_error=True)


class InProcessMCPClient:
    """Client session bound to an MCPToolServer (in-memory transport)."""

    def __init__(self, server: MCPToolServer) -> None:
        self.server = server
        self._initialized = False

    def initialize(self) -> dict[str, Any]:
        self._initialized = True
        return {
            "protocol": "edupath-mcp/1.0",
            "server": self.server.name,
            "capabilities": {"tools": {"listChanged": False}},
        }

    def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        return self.server.list_tools()

    def call_tool(self, name: str, arguments: Optional[dict[str, Any]] = None) -> ToolResult:
        if not self._initialized:
            self.initialize()
        return self.server.call_tool(name, arguments)
