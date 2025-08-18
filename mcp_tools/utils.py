import sqlparse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

def validate_select_sql(sql: str) -> bool:
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False
        first = parsed[0]
        tok0 = first.token_first(skip_cm=True)
        if tok0 is None:
            return False
        val = tok0.value.upper()
        return val == 'SELECT'
    except Exception:
        return False

def safe_execute_select(engine, sql: str, limit: int = 100):
    if not validate_select_sql(sql):
        raise ValueError("Only SELECT queries are allowed.")
    sql_lc = sql.lower()
    if "limit" not in sql_lc:
        sql = sql.strip().rstrip(';') + f" LIMIT {int(limit)};"
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            cols = list(result.keys())
            rows = result.fetchall()
        return cols, [list(r) for r in rows]
    except SQLAlchemyError as e:
        raise

def schema_to_text(inspector):
    parts = []
    for t in inspector.get_table_names():
        cols = inspector.get_columns(t)
        col_lines = ", ".join([c['name'] for c in cols])
        parts.append(f"Table: {t} Columns: {col_lines}")
    return "\n".join(parts)
