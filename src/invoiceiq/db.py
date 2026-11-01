from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from invoiceiq.config import settings


class Base(DeclarativeBase):
    pass


def _sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
if settings.database_url.startswith("sqlite"):
    event.listen(engine, "connect", _sqlite_foreign_keys)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_session() -> Generator[Session]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    from invoiceiq import models  # noqa: F401

    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        document_columns = {
            column["name"] for column in inspect(engine).get_columns("documents")
        }
        if "content" not in document_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE documents ADD COLUMN content BLOB")
                )
