

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    DateTime, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import JSONB


def build_metadata() -> MetaData:
    """Membangun definisi skema (MetaData) tanpa menyentuh database sama
    sekali. Dipisah dari create_table_chatbot supaya bisa dipakai ulang
    oleh modul lain (misalnya drop_table.py) tanpa duplikasi definisi tabel."""
    meta = MetaData()

    # Table untuk menyimpan akun user (untuk login)
    users = Table(
        "users",
        meta,
        Column("id", Integer, primary_key=True),
        Column("username", String, nullable=False, unique=True),
        Column("email", String, nullable=False, unique=True),
        Column("password_hash", String, nullable=False),  # simpan hash, JANGAN plain text
        Column("created_at", DateTime, server_default=func.now()),
    )

    # Table untuk menyimpan sesi chat (1 sesi = 1 percakapan milik 1 user)
    sessions = Table(
        "sessions",
        meta,
        Column("id", Integer, primary_key=True),
        Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        Column("title", String),  # label obrolan untuk sidebar, contoh: "Tanya soal Yohanes 3:16"
        Column("created_at", DateTime, server_default=func.now()),
        Index("ix_sessions_user_id", "user_id"),
    )

    # Table untuk menyimpan tiap pesan dalam sesi (user & assistant)
    # Kolom di bawah dipetakan ke request/response JSON:
    #   request  -> { query, model, history }
    #   response -> { content, model, sources }
    messages = Table(
        "messages",
        meta,
        Column("id", Integer, primary_key=True),
        Column("session_id", Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        Column("role", String, nullable=False),  # "user" / "assistant"
        Column("model", String),                 # model yang dipakai untuk pesan ini, contoh: "gemma4" -> field "model"
        Column("query", Text),                   # query asli dari user
        Column("rewritten_query", Text),         # hasil history_agent (kalau ada)
        Column("reason", Text),                  # hasil clean_reason dari graph
        Column("content", Text),                 # jawaban final dari answer_agent -> field "content"
        Column("sources", JSONB),                # field "sources" dari response, siap dipakai kalau RAG aktif lagi
        Column("created_at", DateTime, server_default=func.now()),
        Index("ix_messages_session_id", "session_id"),
    )

    return meta


def create_table_chatbot(url: str, echo: bool = False) -> None:
    """Membuat seluruh tabel chatbot (users, sessions, messages) jika belum ada.
    Aman dipanggil berulang kali -- create_all() melewati tabel yang sudah ada."""
    engine = create_engine(url, echo=echo)
    try:
        meta = build_metadata()
        meta.create_all(engine)
    finally:
        engine.dispose()