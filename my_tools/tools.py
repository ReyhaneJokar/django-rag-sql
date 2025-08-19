import re
import uuid
import os
import json
import logging
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
from .utils import schema_to_text, safe_execute_select
from core.rag.llm_utils import load_llm
from sqlalchemy import inspect
import matplotlib.pyplot as plt
from django.conf import settings

_LOG = logging.getLogger(__name__)

def _fix_date_funcs_for_dialect(engine, sql: str) -> str:
    dialect = getattr(engine.dialect, "name", "").lower()
    if dialect == "postgresql":
        sql = re.sub(r"STRFTIME\(\s*'%Y-?%m'\s*,\s*([^\)]+)\)", r"TO_CHAR(\1, 'YYYY-MM')", sql, flags=re.I)
    elif dialect in ("mysql","mariadb"):
        sql = re.sub(r"STRFTIME\(\s*'%Y-?%m'\s*,\s*([^\)]+)\)", r"DATE_FORMAT(\1, '%Y-%m')", sql, flags=re.I)
    elif dialect == "sqlite":
        sql = re.sub(r"TO_CHAR\(\s*([^\),]+)\s*,\s*'YYYY-?MM'\s*\)", r"STRFTIME('%Y-%m', \1)", sql, flags=re.I)
    return sql

def chart_detector(engine, question: str):
    """
    Use your LLM (load_llm) to decide:
    - whether to plot (true/false)
    - suggested plot_type (bar/line/pie/scatter/table)
    - suggested SQL (SELECT ...). Must be only SELECT (we will validate)
    Return dict.
    """
    inspector = inspect(engine)
    schema_text = schema_to_text(inspector)

    llm = load_llm()
    prompt = f"""
    You are a SQL+visualization assistant. Given a user question and database schema, decide:
    1) whether the question can/should be answered with a chart (true/false)
    2) if true, suggest one of: bar, line, pie, scatter, table
    3) provide a single SQL SELECT query that returns the fields needed for the suggested chart.
    Output MUST be valid JSON with keys: plot (true/false), plot_type (string or null), sql (string or null).
    Use only columns present in the schema below. Don't include comments or markdown.

    Schema:
    {schema_text}

    User question:
    {question}

    Examples of JSON output:
    {{"plot": true, "plot_type":"bar", "sql":"SELECT category, COUNT(*) as cnt FROM sales GROUP BY category;"}}
    """
    raw = llm.generate(prompt)
    text = raw.strip() if isinstance(raw, str) else str(raw)

    try:
        text_clean = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_clean)
    except Exception:
        m = re.search(r'\{.*\}', text, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception as e:
                _LOG.exception("Failed to parse JSON from model: %s", text)
                raise RuntimeError("Model returned non-JSON response")
        else:
            _LOG.exception("No JSON found in model output: %s", text)
            raise RuntimeError("Model did not return JSON")

    if data.get("plot") and data.get("sql"):
        return {
            "plot": bool(data.get("plot")),
            "plot_type": data.get("plot_type"),
            "sql": data.get("sql")
        }
    else:
        return {"plot": False, "plot_type": None, "sql": None}

def chart_renderer(engine, sql: str, plot_type: str, limit_rows: int = 200):
    """
    Execute SQL (safe), then render a chart and return a public URL.
    Returns dict with keys: plot_url, cols, rows
    """
    sql = _fix_date_funcs_for_dialect(engine, sql)
    cols, rows = safe_execute_select(engine, sql, limit=limit_rows)
    if not rows:
        raise RuntimeError("Query returned no rows")

    try:
        df = pd.DataFrame(rows, columns=cols)
    except Exception:
        _LOG.exception("Failed to build DataFrame from SQL result, coercing to strings.")
        df = pd.DataFrame([list(map(str, r)) for r in rows])
        df.columns = [f"col_{i}" for i in range(len(df.columns))]

    img_name = f"plot_{uuid.uuid4().hex}.png"
    out_path = os.path.join(settings.MEDIA_ROOT, "plots")
    os.makedirs(out_path, exist_ok=True)
    img_file = os.path.join(out_path, img_name)

    try:
        plt.figure(figsize=(8,4))
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
                cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
                if cat_cols and numeric_cols:
                    x = cat_cols[0]; y = numeric_cols[0]
                    agg = df.groupby(x)[y].sum()
                    agg.plot(kind="bar")
                elif numeric_cols and len(numeric_cols) >= 2:
                    df.plot(kind="bar", x=numeric_cols[0], y=numeric_cols[1])
                else:
                    df.plot(kind="bar")
                plt.tight_layout()
                plt.savefig(img_file, dpi=150)
                plt.close('all')

            elif plot_type == "line":
                if numeric_cols:
                    df.plot(kind="line")
                else:
                    df.plot(kind="line")
                plt.tight_layout()
                plt.savefig(img_file, dpi=150)
                plt.close('all')

            elif plot_type == "pie":
                if numeric_cols and len(numeric_cols) >= 1:
                    labels = df.iloc[:,0].astype(str)
                    values = df[numeric_cols[0]]
                    plt.pie(values, labels=labels, autopct='%1.1f%%')
                else:
                    if df.shape[1] >= 2:
                        s = df.iloc[:,1].value_counts()
                    else:
                        s = df.iloc[:,0].value_counts()
                    s.plot(kind="pie", autopct='%1.1f%%')
                plt.tight_layout()
                plt.savefig(img_file, dpi=150)
                plt.close('all')

            elif plot_type == "scatter":
                if len(numeric_cols) >= 2:
                    x = numeric_cols[0]; y = numeric_cols[1]
                    df.plot(kind="scatter", x=x, y=y)
                else:
                    try:
                        x = df.columns[0]; y = df.columns[1]
                        df.plot(kind="scatter", x=x, y=y)
                    except Exception:
                        df.plot(kind="bar")
                plt.tight_layout()
                plt.savefig(img_file, dpi=150)
                plt.close('all')

            else:
                plt.axis('off')
                tbl = plt.table(cellText=df.head(20).values, colLabels=df.columns, loc='center')
                tbl.auto_set_font_size(False)
                tbl.set_fontsize(8)
                plt.savefig(img_file, bbox_inches='tight', dpi=150)
                plt.close('all')

    except Exception as e:
        _LOG.exception("Chart rendering failed: %s", e)
        try:
            plt.close('all')
        except Exception:
            pass
        raise RuntimeError(f"Chart rendering failed: {e}")

    plot_url = os.path.join(settings.MEDIA_URL.rstrip('/'), "plots", img_name)
    return {"plot_url": plot_url, "cols": cols, "rows": rows}
