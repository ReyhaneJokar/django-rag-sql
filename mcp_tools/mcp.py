from fastapi import APIRouter
from typing import Callable, Dict, Any
import inspect


class MCPRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def tool(self, name: str = None, description: str = ""):
        """
        Decorator to register a function as a tool.
        Usage:
            @mcp.tool(name="chart_detector", description="...")
            def chart_detector(payload): ...
        """
        def _decorator(func: Callable):
            tool_name = name or func.__name__
            sig = inspect.signature(func)
            self._tools[tool_name] = {
                "name": tool_name,
                "description": description,
                "callable": func,
                "signature": str(sig),
            }
            return func
        return _decorator

    def get_tools(self):
        return {n: {"name": v["name"], "description": v["description"], "signature": v["signature"]} for n,v in self._tools.items()}

    def call(self, name: str, payload: dict):
        if name not in self._tools:
            raise KeyError(name)
        func = self._tools[name]["callable"]
        return func(payload)

mcp = MCPRegistry()

router = APIRouter()

@router.get("/tools")
def list_tools():
    return {"tools": mcp.get_tools()}

@router.post("/call")
def call_tool(payload: dict):
    """
    payload: { "tool": "<name>", "input": {...} }
    """
    tool = payload.get("tool")
    if not tool:
        return {"error": "missing tool"}
    input_data = payload.get("input", {})
    try:
        res = mcp.call(tool, input_data)
        return {"result": res}
    except KeyError:
        return {"error": "tool not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500
