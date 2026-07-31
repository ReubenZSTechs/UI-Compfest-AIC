"""
Operasi database untuk sesi & pesan chat, sibling module dari app.py.

Setiap method membuka koneksi dari connection pool (engine.connect()),
commit, lalu mengembalikan koneksi ke pool. Tidak ada satu koneksi yang
dipegang seumur hidup objek -- penting karena instance SessionChat ini
dipakai bersama oleh banyak request yang berjalan lewat run_in_threadpool
di app.py.
"""

from typing import Optional, Any
from sqlalchemy import MetaData, Table
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


class SessionChat:
    """Operasi CRUD untuk tabel `sessions` dan `messages`."""

    VALID_ROLES = {"user", "assistant"}

    def __init__(self, engine: Engine):
        self.engine = engine
        meta = MetaData()
        self.sessions = Table("sessions", meta, autoload_with=self.engine)
        self.messages = Table("messages", meta, autoload_with=self.engine)

    # --- sessions ---------------------------------------------------------
    def create_new_session(self, user_id: int, title: str) -> int:
        stmt = (
            self.sessions.insert()
            .values(user_id=user_id, title=title)
            .returning(self.sessions.c.id)
        )
        with self.engine.connect() as conn:
            try:
                new_id = conn.execute(stmt).scalar_one()
                conn.commit()
                return new_id
            except SQLAlchemyError:
                conn.rollback()
                raise

    def get_sessions_for_user(self, user_id: int) -> list[dict]:
        stmt = self.sessions.select().where(self.sessions.c.user_id == user_id)
        if "created_at" in self.sessions.c:
            stmt = stmt.order_by(self.sessions.c.created_at.desc())
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [dict(row) for row in result.mappings()]

    def get_session_by_id(self, session_id: int, user_id: Optional[int] = None) -> Optional[dict]:
        """Jika user_id diberikan, sekaligus validasi kepemilikan."""
        stmt = self.sessions.select().where(self.sessions.c.id == session_id)
        if user_id is not None:
            stmt = stmt.where(self.sessions.c.user_id == user_id)
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            row = result.mappings().first()
            return dict(row) if row else None

    def delete_session(self, session_id: int, user_id: int) -> bool:
        stmt = (
            self.sessions.delete()
            .where(self.sessions.c.id == session_id)
            .where(self.sessions.c.user_id == user_id)
        )
        with self.engine.connect() as conn:
            try:
                result = conn.execute(stmt)
                conn.commit()
                return result.rowcount > 0
            except SQLAlchemyError:
                conn.rollback()
                raise

    # --- messages -----------------------------------------------------------
    def add_chat_and_respons(
        self,
        session_id: int,
        role: str,
        query: Optional[str] = None,
        content: Optional[str] = None,
        model: Optional[str] = None,
        rewritten_query: Optional[str] = None,
        reason: Optional[str] = None,
        sources: Optional[list] = None,
    ) -> Any:
        if role not in self.VALID_ROLES:
            raise ValueError(f"role harus salah satu dari {self.VALID_ROLES}, dapat: {role!r}")

        if role == "user":
            values = dict(
                session_id=session_id, role="user", model=None,
                query=query, rewritten_query=rewritten_query,
                reason=None, content=None, sources=None,
            )
        else:  # assistant
            values = dict(
                session_id=session_id, role="assistant", model=model,
                query=rewritten_query or query, rewritten_query=None,
                reason=reason, content=content,
                sources=sources if sources is not None else [],
            )

        stmt = self.messages.insert().values(**values)
        with self.engine.connect() as conn:
            try:
                result = conn.execute(stmt)
                conn.commit()
                return result.inserted_primary_key
            except SQLAlchemyError:
                conn.rollback()
                raise

    def get_messages_for_session(self, session_id: int) -> list[dict]:
        stmt = self.messages.select().where(self.messages.c.session_id == session_id)
        order_col = self.messages.c.created_at if "created_at" in self.messages.c else self.messages.c.id
        stmt = stmt.order_by(order_col.asc())
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [dict(row) for row in result.mappings()]