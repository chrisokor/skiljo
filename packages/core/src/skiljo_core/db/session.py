from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from skiljo_core import config

assert config.DATABASE_URL is not None, "DATABASE_URL must be set"
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
