"""Ket noi SQLAlchemy - Postgres khi chay Docker/production, SQLite cuc bo
trong development/test. Production bat buoc cung cap DATABASE_URL hoac bo
DB_HOST/DB_USER/DB_PASSWORD/DB_NAME, khong co credential mac dinh.
"""
from __future__ import annotations

import os
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

def _database_url() -> str:
    environment = os.environ.get("APP_ENV", "development").strip().lower()
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    host = os.environ.get("DB_HOST")
    if host:
        user = os.environ.get("DB_USER", "datt")
        password = os.environ.get("DB_PASSWORD", "")
        database = os.environ.get("DB_NAME", "datt")
        port = os.environ.get("DB_PORT", "5432")
        if environment == "production" and not password:
            raise RuntimeError("Bat buoc dat DB_PASSWORD khi APP_ENV=production")
        return (
            f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{quote_plus(database)}"
        )
    if environment == "production":
        raise RuntimeError("Production bat buoc dat DATABASE_URL hoac DB_HOST")
    return "sqlite:///./datt.db"


DATABASE_URL = _database_url()

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
