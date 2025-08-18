import os
import uuid
import json
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, inspect, text
from .mcp import mcp
from .utils import safe_execute_select, schema_to_text

_LOG = logging.getLogger(__name__)

@mcp.tool(name="chart_detector", description="Decide if question needs a chart and provide SQL")
def chart_detector_tool(payload: dict):
    """
    payload:
      - conn_str: sqlalchemy connection string
      - question: user question
    returns: {"plot": bool, "plot_type": str|null, "sql": str|null}
    """
    conn_str = payload.get("conn_str")
    question = payload.get("question", "")
    if not conn_str:
        raise ValueError("conn_str required")
    engine = create_engine(conn_str)
    insp = inspect(engine)
    schema_text = schema_to_text(insp)

    q = question.lower()
    keywords = ["plot","chart","trend","count","by","distribution","compare","histogram","per","per month","per year","over time"]
    wants_plot = any(k in q for k in keywords)

    if any(k in q for k in ["list ", "show ", "give ", "return "]) and "per" not in q:
        wants_plot = wants_plot and ("per" in q or "by" in q or "trend" in q)

    if not wants_plot:
        return {"plot": False, "plot_type": None, "sql": None}

    for t in insp.get_table_names():
        cols = insp.get_columns(t)
        cat = None
        num = None
        for c in cols:
            tn = str(c["type"]).lower()
            name = c["name"]
            if num is None and any(x in tn for x in ("int","numeric","decimal","float","real")):
                num = name
            if cat is None and any(x in tn for x in ("char","text","varchar","date","time")):
                cat = name
        if cat and num:
            sample_sql = f"SELECT {cat} as label, SUM({num}) as value FROM {t} GROUP BY {cat} ORDER BY value DESC;"
            return {"plot": True, "plot_type": "bar", "sql": sample_sql}
    return {"plot": False, "plot_type": None, "sql": None}

@mcp.tool(name="chart_renderer", description="Render chart from SQL and return image URL and data")
def chart_renderer_tool(payload: dict):
    """
    payload:
      - conn_str
      - sql
      - plot_type (bar,line,pie,scatter,table)
      - limit_rows (optional)
    returns: {"plot_url": str, "cols": [...], "rows": [...]}
    """
    conn_str = payload.get("conn_str")
    sql = payload.get("sql")
    plot_type = payload.get("plot_type", "bar")
    limit_rows = int(payload.get("limit_rows", 200))
    if not conn_str or not sql:
        raise ValueError("conn_str and sql required")
    engine = create_engine(conn_str)
    cols, rows = safe_execute_select(engine, sql, limit=limit_rows)
    if not rows:
        raise RuntimeError("Query returned no rows")
    try:
        df = pd.DataFrame(rows, columns=cols)
    except Exception:
        df = pd.DataFrame([list(map(str, r)) for r in rows])
        df.columns = [f"col_{i}" for i in range(len(df.columns))]

    img_name = f"plot_{uuid.uuid4().hex}.png"
    media_root = os.environ.get("MCP_MEDIA_ROOT", os.path.abspath("media"))
    media_url = os.environ.get("MCP_MEDIA_URL", "/media/")
    os.makedirs(os.path.join(media_root, "plots"), exist_ok=True)
    img_file = os.path.join(media_root, "plots", img_name)

    plt.figure(figsize=(8,4))
    try:
        if plot_type == "table":
            plt.axis('off')
            tbl = plt.table(cellText=df.head(20).values, colLabels=df.columns, loc='center')
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(8)
            plt.savefig(img_file, bbox_inches='tight', dpi=150)
            plt.close('all')
        else:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if plot_type == "bar":
                cat_cols = df.select_dtypes(include=['object','category']).columns.tolist()
                if cat_cols and numeric_cols:
                    x = cat_cols[0]; y = numeric_cols[0]
                    agg = df.groupby(x)[y].sum()
                    agg.plot(kind="bar")
                elif numeric_cols and len(numeric_cols) >= 2:
                    df.plot(kind="bar", x=numeric_cols[0], y=numeric_cols[1])
                else:
                    df.plot(kind="bar")
            elif plot_type == "line":
                df.plot(kind="line")
            elif plot_type == "pie":
                if numeric_cols:
                    labels = df.iloc[:,0].astype(str) if df.shape[1] >= 1 else df.index.astype(str)
                    values = df[numeric_cols[0]] if numeric_cols else df.iloc[:,1]
                    plt.pie(values, labels=labels, autopct='%1.1f%%')
                else:
                    s = df.iloc[:,0].value_counts()
                    s.plot(kind="pie", autopct='%1.1f%%')
            elif plot_type == "scatter":
                if len(numeric_cols) >= 2:
                    x = numeric_cols[0]; y = numeric_cols[1]
                    df.plot(kind="scatter", x=x, y=y)
                else:
                    df.plot(kind="scatter")
            else:
                df.plot(kind="bar")
            plt.tight_layout()
            plt.savefig(img_file, dpi=150)
            plt.close('all')
    except Exception as e:
        _LOG.exception("Chart rendering failed: %s", e)
        try:
            plt.close('all')
        except:
            pass
        raise RuntimeError(f"Chart rendering failed: {e}")

    plot_url = media_url.rstrip('/') + "/plots/" + img_name
    return {"plot_url": plot_url, "cols": cols, "rows": rows}
