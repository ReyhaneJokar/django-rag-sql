import os
import requests
from django.shortcuts import get_object_or_404
from core.models import ConnectionConfig

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5001")

def build_conn_str(conn):
    DIALECT_MAP = {
        'postgres':   'postgresql+psycopg2',
        'sqlserver':  'mssql+pyodbc',
        'oracle':     'oracle+cx_oracle',
    }
    dialect = DIALECT_MAP.get(conn.db_type)
    if not dialect:
        raise ValueError("unsupported db type")
    if conn.db_type == 'sqlserver':
        return (
            f"{dialect}://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database_name}"
            f"?driver=ODBC+Driver+17+for+SQL+Server"
        )
    else:
        return f"{dialect}://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database_name}"

def call_tool(tool_name: str, conn, input_payload: dict, timeout: int = 60):
    """
    conn: ConnectionConfig instance OR raw conn_str (string)
    input_payload: dict of inputs (question, sql, plot_type, ...)
    """
    if hasattr(conn, "db_type"):
        conn_str = build_conn_str(conn)
    else:
        conn_str = conn
    payload = {"tool": tool_name, "input": {"conn_str": conn_str, **(input_payload or {})}}
    resp = requests.post(f"{MCP_URL}/call", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "result" in data:
        return data["result"]
    if "error" in data:
        raise RuntimeError(data["error"])
    return data
