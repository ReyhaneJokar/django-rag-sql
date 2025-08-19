import sqlparse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

def validate_select_sql(sql: str) -> bool:
    """
    Very simple guard: allow only SELECT statements. Reject any DDL/DML.
    We do a basic parse using sqlparse: ensure first token is SELECT.
    """
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
    """
    Execute SELECT safely with a enforced LIMIT if possible.
    Return rows as list[tuple] and columns.
    """
    if not validate_select_sql(sql):
        raise ValueError("Only SELECT queries are allowed.")

    sql_lc = sql.lower()
    if "limit" not in sql_lc:
        sql = sql.strip().rstrip(';') + f" LIMIT {int(limit)};"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            cols = result.keys()
            rows = result.fetchall()
        return list(cols), [list(r) for r in rows]
    except SQLAlchemyError as e:
        raise

def schema_to_text(inspector):
    """
    Build a compact textual schema description from SQLAlchemy inspector.
    Return string describing tables and columns.
    """
    parts = []
    for t in inspector.get_table_names():
        cols = inspector.get_columns(t)
        col_lines = ", ".join([c['name'] for c in cols])
        parts.append(f"Table: {t} Columns: {col_lines}")
    return "\n".join(parts)
