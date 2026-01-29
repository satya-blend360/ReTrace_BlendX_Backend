# app/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from src.utils.config import SF_USER, SF_PASSWORD, SF_ACCOUNT, SF_WAREHOUSE, SF_SCHEMA, SF_DATABASE, SF_ROLE

user = SF_USER
password = SF_PASSWORD
account = SF_ACCOUNT
warehouse = SF_WAREHOUSE
database = SF_DATABASE
schema = SF_SCHEMA
role = SF_ROLE

# Snowflake connection URL
DATABASE_URL = f"snowflake://{user}:{password}@{account}/{database}/{schema}?warehouse={warehouse}&role={role}"


# Configure the connection pool
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,  # Use the QueuePool for connection pooling
    pool_size=5,          # Max number of connections to keep in the pool
    max_overflow=10,      # Allow up to 10 additional connections to be created if needed
    pool_timeout=30,      # Timeout (in seconds) to wait for a connection from the pool
    pool_recycle=1800,    # Connections are recycled after this many seconds
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()