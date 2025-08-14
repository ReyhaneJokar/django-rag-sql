import re
import uuid
import os
import json
import logging
import numpy as np
import pandas as pd
from .utils import schema_to_text, safe_execute_select
from core.rag.llm_utils import load_llm
from sqlalchemy import inspect
import matplotlib.pyplot as plt
from django.conf import settings


_LOG = logging.getLogger(__name__)

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
    text = raw.strip()
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
    """
    cols, rows = safe_execute_select(engine, sql, limit=limit_rows)
    if not rows:
        raise RuntimeError("Query returned no rows")

    df = pd.DataFrame(rows, columns=cols)

    img_name = f"plot_{uuid.uuid4().hex}.png"
    out_path = os.path.join(settings.MEDIA_ROOT, "plots")
    os.makedirs(out_path, exist_ok=True)
    img_file = os.path.join(out_path, img_name)

    plt.figure(figsize=(8,4))
    if plot_type == "table":
        plt.axis('off')
        tbl = plt.table(cellText=df.head(20).values, colLabels=df.columns, loc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        plt.savefig(img_file, bbox_inches='tight', dpi=150)
        plt.close()
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
            plt.close()
        elif plot_type == "line":
            if numeric_cols:
                df.plot(kind="line")
            else:
                df.plot(kind="line")
            plt.tight_layout()
            plt.savefig(img_file, dpi=150)
            plt.close()
        elif plot_type == "pie":
            if numeric_cols and len(numeric_cols) >= 1:
                s = df[numeric_cols[0]].groupby(df.iloc[:,0]).sum()
                s.plot(kind="pie", autopct='%1.1f%%')
            else:
                df.iloc[:,1].value_counts().plot(kind='pie', autopct='%1.1f%%')
            plt.tight_layout()
            plt.savefig(img_file, dpi=150)
            plt.close()
        elif plot_type == "scatter":
            if len(numeric_cols) >= 2:
                x = numeric_cols[0]; y = numeric_cols[1]
                df.plot(kind="scatter", x=x, y=y)
            else:
                df.plot(kind="scatter")
            plt.tight_layout()
            plt.savefig(img_file, dpi=150)
            plt.close()
        else:
            plt.axis('off')
            tbl = plt.table(cellText=df.head(20).values, colLabels=df.columns, loc='center')
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(8)
            plt.savefig(img_file, bbox_inches='tight', dpi=150)
            plt.close()

    url = os.path.join(settings.MEDIA_URL, "plots", img_name)
    return {"image_url": url, "cols": cols, "rows_count": len(rows)}
