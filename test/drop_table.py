from sqlalchemy import create_engine, MetaData


def drop_table_chatbot(url: str):
    """
    Menghapus SEMUA table (users, sessions, messages) beserta seluruh datanya.
    Ini operasi DROP, bukan hanya hapus isi — struktur table ikut hilang.
    Setelah ini, jalankan create_table_chatbot(url) lagi untuk membuat ulang table-nya.
    """
    engine = create_engine(url, echo=True)
    meta = MetaData()

    # Reflect dulu semua table yang ada saat ini di database,
    # supaya drop_all tahu apa saja yang harus dihapus (termasuk foreign key-nya).
    meta.reflect(bind=engine)
    meta.drop_all(engine)

    conn = engine.connect()
    conn.commit()
    conn.close()


if __name__ == "__main__":
    drop_table_chatbot('postgresql+psycopg://---:----@localhost:5432/---')