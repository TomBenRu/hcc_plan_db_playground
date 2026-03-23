from collections.abc import Generator

from sqlmodel import Session

from database.database import engine


def get_db_session() -> Generator[Session, None, None]:
    """Request-scoped DB-Session. Commit bei Erfolg, Rollback bei Exception."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
