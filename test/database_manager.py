import os
from sqlalchemy import create_engine

from databse.create_table import create_table_chatbot
from databse.create_dummy_data import create_dummy_data
from databse.drop_table import drop_table_chatbot
from databse.add_chat import SessionChat

from dotenv import load_dotenv
import os

load_dotenv()


class DatabaseChatbot:
    """Facade untuk operasi database chatbot (skema + sesi chat)."""

    def __init__(self, user, password, db, user_id, host="localhost", port=5432):
        self.url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
        self.POSTGRES_USER = user
        self.POSTGRES_PASSWORD = password
        self.POSTGRES_DB = db
        self.user_id = user_id
        
        self.engine = create_engine(self.url)
        
        # PERBAIKAN: Jangan inisialisasi SessionChat di sini karena tabel belum tentu ada.
        # Kita set None dulu dan inisialisasi secara 'lazy' lewat properti.
        self._session = None 
        self.current_session_id = None 

    @property
    def session(self):
        """Property untuk memuat SessionChat secara lazy (hanya saat dibutuhkan)."""
        if self._session is None:
            self._session = SessionChat(self.engine)
        return self._session

    # --- context manager support -------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Tutup koneksi database."""
        self.engine.dispose()

    # --- skema & data ----------------------------------------------------
    def build_table(self):
        create_table_chatbot(self.url)

    def build_dummy_data(self):
        # PERBAIKAN: Pastikan data dummy dibuat setelah tabel ada
        create_dummy_data(self.url)

    def drop_all_table(self):
        drop_table_chatbot(self.url)
        # Reset session chatbot jika tabel di-drop agar meta-data di-load ulang nanti
        self._session = None

    drob_all_table = drop_all_table

    # --- sesi & pesan (Sekarang menggunakan properti self.session) --------
    def get_session(self):
        return self.session.get_sessions_for_user(self.user_id)

    def set_session(self, session_id):
        self.current_session_id = session_id

    def get_messages(self):
        if not self.current_session_id:
            return []
        return self.session.get_messages_for_session(self.current_session_id)

    def add_chat(
        self,
        query,
        content,
        role,
        model=None,
        rewritten_query=None,
        reason=None,
        sources=None,
    ):
        if not self.current_session_id:
            raise ValueError("Session ID belum diset. Panggil set_session() terlebih dahulu.")
            
        return self.session.add_chat_and_respons(
            session_id=self.current_session_id,
            role=role,
            query=query,
            content=content,
            model=model,
            rewritten_query=rewritten_query,
            reason=reason,
            sources=sources,
        )
    
if __name__ == "__main__":
    POSTGRES_USER=os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB=os.getenv("POSTGRES_DB")

    user_id = 1

    with DatabaseChatbot(POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, user_id) as database:
        database.drop_all_table()
        database.build_table()
        database.build_dummy_data()

        print("==================================================")
        sessions = database.get_session()
        for s in sessions:
            print(s)

        print("==================================================")
        database.set_session(1)
        database.add_chat(
            query="hi",
            content=None,
            role="user",
            rewritten_query="hihihihi",
        )
        database.add_chat(
            query="hi",
            content="hi again",
            role="assistant",
            model="nano",
            reason="hohoho",
        )

        messages = database.get_messages()
        for message in messages:
            print(message)