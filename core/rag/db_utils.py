from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import re

def connect_db(connection_string: str) -> Engine:
    '''
    Parses and validates the connection string, then returns a SQLAlchemy Engine.
    Raises ValueError or SQLAlchemyError on failure.
    '''
    # Basic validation: must start with dialect://
    pattern = r'^[a-zA-Z0-9_+\-]+://'
    if not re.match(pattern, connection_string):
        raise ValueError("Invalid connection string format.")
    try:
        engine = create_engine(connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return engine
    except SQLAlchemyError as e:
        raise SQLAlchemyError(f"Failed to connect to database: {e}")
