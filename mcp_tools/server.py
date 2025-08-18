from fastapi import FastAPI
from .mcp import router as mcp_router
from . import tools

app = FastAPI(title="MCP Tools Server")
app.include_router(mcp_router, prefix="")
