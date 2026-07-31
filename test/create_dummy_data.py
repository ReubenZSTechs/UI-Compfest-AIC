from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session


def create_dummy_data(url):
    engine = create_engine(url, echo=True)
    meta = MetaData()
    # Reflect table yang sudah dibuat oleh create_table_chatbot()
    users = Table('users', meta, autoload_with=engine)
    sessions = Table('sessions', meta, autoload_with=engine)
    messages = Table('messages', meta, autoload_with=engine)

    insert_statement = []

    
    #  USERS (3 user untuk testing isolasi data)
    
    insert_statement.append(
        users.insert().values(
            username='budi',
            email='budi@example.com',
            password_hash='$2b$12$dummyhashbudi1234567890',  # ganti pakai bcrypt.hash() di kode asli
        )
    )
    insert_statement.append(
        users.insert().values(
            username='sinta',
            email='sinta@example.com',
            password_hash='$2b$12$dummyhashsinta1234567890',
        )
    )
    insert_statement.append(
        users.insert().values(
            username='andre',
            email='andre@example.com',
            password_hash='$2b$12$dummyhashandre1234567890',
        )
    )
    # user_id=1 -> budi, user_id=2 -> sinta, user_id=3 -> andre
    # (asumsi id auto-increment mulai dari 1, table masih kosong sebelum ini)

    
    #  SESSIONS (3-4 sesi per user)
    

    # ── Budi (user_id=1) — 4 sesi ────────────────────────────────────────────
    insert_statement.append(sessions.insert().values(user_id=1, title='Tanya soal Yohanes 3:16'))            # session_id=1
    insert_statement.append(sessions.insert().values(user_id=1, title='Diskusi tafsiran kasih Allah'))        # session_id=2
    insert_statement.append(sessions.insert().values(user_id=1, title='Persiapan khotbah Minggu'))            # session_id=3
    insert_statement.append(sessions.insert().values(user_id=1, title='Tanya jadwal ibadah'))                  # session_id=4

    # ── Sinta (user_id=2) — 3 sesi ───────────────────────────────────────────
    insert_statement.append(sessions.insert().values(user_id=2, title='Pertanyaan umum seputar doa'))         # session_id=5
    insert_statement.append(sessions.insert().values(user_id=2, title='Belajar Mazmur untuk renungan'))       # session_id=6
    insert_statement.append(sessions.insert().values(user_id=2, title='Diskusi tentang pengampunan'))         # session_id=7

    # ── Andre (user_id=3) — 4 sesi ────────────────────────────────────────────
    insert_statement.append(sessions.insert().values(user_id=3, title='Tanya soal kisah Nabi Musa'))          # session_id=8
    insert_statement.append(sessions.insert().values(user_id=3, title='Obrolan singkat sapaan'))               # session_id=9
    insert_statement.append(sessions.insert().values(user_id=3, title='Diskusi perumpamaan anak hilang'))      # session_id=10
    insert_statement.append(sessions.insert().values(user_id=3, title='Tanya tentang baptisan'))               # session_id=11

    
    #  MESSAGES (2-5 turn per sesi, role bergantian user/assistant)
    #  Tiap "turn" = 1 pesan user + 1 pesan assistant
    

    SOURCE_KHOTBAH_YOHANES = [
        {
            "type": "pdf",
            "title": "Dokumen Khotbah — Yohanes 3:16",
            "excerpt": "Karena begitu besar kasih Allah akan dunia ini, sehingga Ia telah mengaruniakan Anak-Nya yang tunggal, supaya setiap orang yang percaya kepada-Nya tidak binasa, melainkan beroleh hidup yang kekal.",
            "url": "https://example.com/khotbah-yohanes.pdf",
            "page": 12,
        },
        {
            "type": "article",
            "title": "Tafsiran Alkitab — Kasih Allah",
            "excerpt": "Kasih Allah dalam konteks Perjanjian Baru menggambarkan pengorbanan yang bersifat tanpa syarat. Kata Yunani 'agape' digunakan untuk membedakannya dari bentuk kasih lainnya.",
            "url": "https://example.com/tafsiran-kasih",
            "page": None,
        },
    ]
    SOURCE_YOUTUBE_KHOTBAH = [
        {
            "type": "youtube",
            "title": "Khotbah Minggu — Kasih yang Tak Terbatas",
            "excerpt": "Dalam khotbah ini, pembicara menjelaskan bagaimana kasih Allah dinyatakan melalui pengorbanan Kristus dan relevansinya bagi kehidupan sehari-hari.",
            "url": "https://youtube.com/watch?v=example123",
            "page": None,
        },
    ]
    SOURCE_ARTIKEL_MAZMUR = [
        {
            "type": "article",
            "title": "Tafsiran Mazmur 23 — Tuhan Adalah Gembalaku",
            "excerpt": "Mazmur ini menggambarkan kepercayaan penuh Daud kepada penyertaan Tuhan dalam setiap musim kehidupan, baik suka maupun duka.",
            "url": "https://example.com/tafsiran-mazmur-23",
            "page": 4,
        },
    ]
    SOURCE_PDF_PERUMPAMAAN = [
        {
            "type": "pdf",
            "title": "Bahan Studi — Perumpamaan Anak yang Hilang",
            "excerpt": "Perumpamaan ini menggambarkan kasih dan pengampunan Bapa yang tidak terbatas, meskipun sang anak telah menghambur-hamburkan hartanya.",
            "url": "https://example.com/studi-anak-hilang.pdf",
            "page": 7,
        },
        {
            "type": "article",
            "title": "Makna Teologis Lukas 15",
            "excerpt": "Lukas 15 berisi tiga perumpamaan tentang sesuatu yang hilang lalu ditemukan, menekankan sukacita surga atas pertobatan.",
            "url": "https://example.com/lukas-15-makna",
            "page": None,
        },
    ]

    def add_turn(session_id, query, content, model='gemma4', rewritten_query=None, reason=None, sources=None):
        """Helper internal: 1 turn = 1 pesan user + 1 pesan assistant."""
        insert_statement.append(
            messages.insert().values(
                session_id=session_id, role='user', model=None,
                query=query, rewritten_query=rewritten_query,
                reason=None, content=None, sources=None,
            )
        )
        insert_statement.append(
            messages.insert().values(
                session_id=session_id, role='assistant', model=model,
                query=rewritten_query or query, rewritten_query=None,
                reason=reason, content=content,
                sources=sources if sources is not None else [],
            )
        )

    # ── session_id=1 (Budi) — Yohanes 3:16 — 3 turn, ada sources ─────────────
    add_turn(
        1,
        query='Apa arti Yohanes 3:16?',
        reason='Ayat ini berbicara tentang kasih Allah kepada dunia melalui pengorbanan Anak-Nya.',
        content='Yohanes 3:16 menjelaskan bahwa Allah begitu mengasihi dunia sehingga Ia mengaruniakan Anak-Nya yang tunggal, supaya setiap orang yang percaya kepada-Nya tidak binasa melainkan beroleh hidup yang kekal.',
        sources=SOURCE_KHOTBAH_YOHANES,
    )
    add_turn(
        1,
        query='Siapa yang menulis ayat ini?',
        rewritten_query='Siapa penulis Injil Yohanes yang memuat ayat 3:16?',
        reason='Tradisi gereja mengaitkan penulisan Injil ini dengan salah satu murid Yesus.',
        content='Menurut tradisi gereja, Injil Yohanes ditulis oleh Rasul Yohanes, salah satu dari dua belas murid Yesus.',
        sources=[],
    )
    add_turn(
        1,
        query='Apakah ada video penjelasan tentang ayat ini?',
        reason='Tersedia rekaman khotbah yang membahas tema kasih Allah dalam ayat ini.',
        content='Ya, ada rekaman khotbah berjudul "Kasih yang Tak Terbatas" yang membahas tema ini secara mendalam, termasuk relevansinya untuk kehidupan sehari-hari.',
        sources=SOURCE_YOUTUBE_KHOTBAH,
    )

    # ── session_id=2 (Budi) — Tafsiran kasih Allah — 4 turn, ganti model ─────
    add_turn(
        2,
        query='Apa beda kasih agape dengan kasih biasa?',
        reason='Agape adalah kasih tanpa syarat, berbeda dengan eros atau philia.',
        content='Kasih agape dalam Perjanjian Baru menggambarkan kasih tanpa syarat dan pengorbanan, berbeda dari kasih romantis (eros) atau kasih persahabatan (philia).',
        model='gemma4',
        sources=SOURCE_KHOTBAH_YOHANES[1:],
    )
    add_turn(
        2,
        query='Coba jelaskan pakai model lain.',
        rewritten_query='Berdasarkan riwayat sebelumnya tentang kasih agape, jelaskan ulang dengan model lain.',
        reason='Penjelasan ulang dengan sudut pandang teologis yang lebih ringkas.',
        content='Agape adalah bentuk kasih yang diberikan tanpa mengharapkan balasan, sering dikaitkan dengan kasih Allah kepada manusia.',
        model='qwen3.5',
        sources=[],
    )
    add_turn(
        2,
        query='Apakah konsep ini ada di kitab-kitab lain juga?',
        rewritten_query='Apakah konsep kasih agape juga muncul di bagian lain Perjanjian Baru selain Yohanes?',
        reason='Konsep agape juga muncul di surat-surat Paulus, terutama 1 Korintus 13.',
        content='Ya, konsep agape juga banyak dibahas dalam surat-surat Paulus, terutama dalam 1 Korintus 13 yang sering disebut "Bab Kasih".',
        model='qwen3.5',
        sources=[],
    )
    add_turn(
        2,
        query='Terima kasih, sudah cukup jelas.',
        content='Sama-sama! Senang bisa membantu menjelaskan soal kasih agape. Jangan ragu bertanya lagi kalau ada topik lain.',
        model='qwen3.5',
        sources=[],
    )

    # ── session_id=3 (Budi) — Persiapan khotbah — 5 turn ─────────────────────
    add_turn(
        3,
        query='Bantu saya cari tema khotbah untuk Minggu ini.',
        reason='Tema kasih dan pengorbanan relevan untuk konteks ibadah umum.',
        content='Beberapa tema yang bisa dipertimbangkan: kasih Allah yang tak bersyarat, pengampunan, atau ucapan syukur. Tema mana yang paling sesuai dengan jemaat Anda?',
        sources=[],
    )
    add_turn(
        3,
        query='Saya pilih tema kasih Allah saja.',
        reason='Tema ini bisa dikembangkan dari Yohanes 3:16 dan 1 Korintus 13.',
        content='Baik, untuk tema kasih Allah, Anda bisa membuka dengan Yohanes 3:16 sebagai ayat utama, lalu memperdalam dengan 1 Korintus 13 tentang ciri-ciri kasih.',
        sources=SOURCE_KHOTBAH_YOHANES,
    )
    add_turn(
        3,
        query='Apa contoh ilustrasi yang cocok untuk pembukaan?',
        reason='Ilustrasi sederhana tentang pengorbanan orang tua sering relevan untuk audiens umum.',
        content='Anda bisa menggunakan ilustrasi pengorbanan orang tua bagi anaknya sebagai gambaran sederhana tentang kasih tanpa pamrih, sebelum masuk ke kasih Allah yang jauh lebih besar.',
        sources=[],
    )
    add_turn(
        3,
        query='Bagaimana cara menutup khotbah dengan baik?',
        reason='Penutup yang baik biasanya berisi ajakan refleksi atau aplikasi praktis.',
        content='Tutup dengan mengajak jemaat merefleksikan: "Bagaimana saya bisa mewujudkan kasih ini dalam minggu ini?" — lalu akhiri dengan doa singkat.',
        sources=[],
    )
    add_turn(
        3,
        query='Terima kasih banyak atas bantuannya.',
        content='Sama-sama, semoga khotbahnya memberkati jemaat. Selamat melayani!',
        sources=[],
    )

    # ── session_id=4 (Budi) — Jadwal ibadah — 2 turn ─────────────────────────
    add_turn(
        4,
        query='Jam berapa ibadah Minggu biasanya dimulai?',
        content='Maaf, saya tidak punya akses ke jadwal ibadah gereja spesifik Anda. Sebaiknya hubungi sekretariat gereja atau cek pengumuman terbaru untuk informasi jadwal yang akurat.',
        sources=[],
    )
    add_turn(
        4,
        query='Oke, terima kasih infonya.',
        content='Sama-sama, semoga ibadahnya berjalan lancar!',
        sources=[],
    )

    # ── session_id=5 (Sinta) — Doa — 3 turn ──────────────────────────────────
    add_turn(
        5,
        query='Bagaimana cara berdoa yang baik?',
        reason='Doa yang baik melibatkan ketulusan hati, bukan sekadar rutinitas.',
        content='Doa yang baik tidak harus panjang atau formal — yang penting adalah ketulusan hati saat berbicara kepada Tuhan, baik untuk memuji, meminta, maupun bersyukur.',
        sources=[],
    )
    add_turn(
        5,
        query='Apakah ada contoh doa yang dicontohkan Yesus?',
        rewritten_query='Apakah ada contoh doa yang diajarkan langsung oleh Yesus kepada murid-murid-Nya?',
        reason='Doa Bapa Kami adalah contoh doa yang diajarkan Yesus.',
        content='Ya, contoh paling dikenal adalah Doa Bapa Kami, yang diajarkan Yesus kepada murid-murid-Nya sebagai panduan berdoa.',
        sources=[],
    )
    add_turn(
        5,
        query='Apa struktur dari Doa Bapa Kami itu?',
        reason='Doa Bapa Kami terdiri dari pujian, permohonan, dan pengakuan.',
        content='Strukturnya umumnya terdiri dari pujian kepada Tuhan, permohonan kebutuhan harian, permohonan pengampunan, dan permohonan perlindungan dari pencobaan.',
        sources=[],
    )

    # ── session_id=6 (Sinta) — Mazmur — 4 turn, ada sources ──────────────────
    add_turn(
        6,
        query='Tolong jelaskan makna Mazmur 23.',
        reason='Mazmur 23 menggambarkan Tuhan sebagai gembala yang menyertai dalam segala musim.',
        content='Mazmur 23 menggambarkan Tuhan sebagai gembala yang membimbing dan menyertai umat-Nya, bahkan ketika melalui "lembah kekelaman" sekalipun, sebagai gambaran masa-masa sulit dalam hidup.',
        sources=SOURCE_ARTIKEL_MAZMUR,
    )
    add_turn(
        6,
        query='Kapan kira-kira mazmur ini ditulis?',
        reason='Mazmur ini secara tradisional dikaitkan dengan Daud.',
        content='Mazmur 23 secara tradisional dikaitkan dengan Raja Daud, kemungkinan ditulis berdasarkan pengalamannya sebagai gembala di masa muda sebelum menjadi raja.',
        sources=[],
    )
    add_turn(
        6,
        query='Cocok untuk renungan tema apa?',
        reason='Tema ketenangan dan kepercayaan kepada Tuhan sangat cocok dengan mazmur ini.',
        content='Mazmur ini sangat cocok untuk renungan tentang ketenangan hati, kepercayaan kepada penyertaan Tuhan, dan penghiburan di masa-masa sulit.',
        sources=[],
    )
    add_turn(
        6,
        query='Boleh beri saya ayat penutup yang menguatkan dari mazmur ini?',
        reason='Ayat terakhir mazmur ini berisi pengharapan akan kebaikan Tuhan seumur hidup.',
        content='Ayat penutupnya menyatakan kepercayaan bahwa kebaikan dan kasih setia Tuhan akan mengikuti sepanjang hidup, dan akan tinggal di rumah Tuhan selama-lamanya — sangat menguatkan untuk renungan penutup.',
        sources=SOURCE_ARTIKEL_MAZMUR,
    )

    # ── session_id=7 (Sinta) — Pengampunan — 2 turn ──────────────────────────
    add_turn(
        7,
        query='Mengapa pengampunan itu penting dalam iman Kristen?',
        reason='Pengampunan adalah inti dari ajaran Kristus dan teladan dari kayu salib.',
        content='Pengampunan penting karena merupakan inti dari ajaran Kristus — Ia sendiri memberi teladan pengampunan di kayu salib, dan mengajarkan umat-Nya untuk saling mengampuni seperti telah diampuni.',
        sources=[],
    )
    add_turn(
        7,
        query='Bagaimana jika sulit mengampuni seseorang?',
        reason='Pengampunan adalah proses, bisa dimulai dengan doa dan niat, bukan harus instan.',
        content='Sulit mengampuni adalah hal yang manusiawi. Anda bisa memulainya dengan berdoa meminta kekuatan hati, dan menyadari bahwa pengampunan adalah proses bertahap, bukan sesuatu yang harus terjadi instan.',
        sources=[],
    )

    # ── session_id=8 (Andre) — Kisah Musa — 4 turn ───────────────────────────
    add_turn(
        8,
        query='Ceritakan singkat tentang kisah Musa dan Laut Merah.',
        reason='Kisah ini menggambarkan pembebasan umat Israel dari Mesir melalui mukjizat.',
        content='Musa memimpin umat Israel keluar dari Mesir. Ketika dikejar pasukan Firaun, Tuhan membelah Laut Merah sehingga mereka bisa menyeberang, dan air kembali menutup ketika pasukan Mesir mengejar.',
        sources=[],
    )
    add_turn(
        8,
        query='Apa pelajaran yang bisa diambil dari kisah ini?',
        reason='Kisah ini mengajarkan kepercayaan kepada Tuhan di tengah situasi yang tampak mustahil.',
        content='Pelajaran utamanya adalah pentingnya kepercayaan kepada Tuhan, bahkan ketika situasi tampak mustahil — Tuhan dapat membuka jalan yang tidak terpikirkan oleh manusia.',
        sources=[],
    )
    add_turn(
        8,
        query='Apakah Musa pernah ragu sebelum kejadian ini?',
        reason='Musa sempat menyatakan keraguan dan ketakutan sebelum memimpin umat Israel.',
        content='Ya, sebelumnya Musa beberapa kali menyatakan keraguan saat dipanggil Tuhan, termasuk merasa tidak pandai bicara, namun Tuhan tetap memakainya untuk memimpin umat-Nya.',
        sources=[],
    )
    add_turn(
        8,
        query='Menarik, terima kasih ceritanya.',
        content='Sama-sama! Kisah Musa memang penuh pelajaran tentang iman dan ketaatan. Senang bisa berbagi.',
        sources=[],
    )

    # ── session_id=9 (Andre) — Obrolan singkat — 2 turn ──────────────────────
    add_turn(
        9,
        query='Halo, selamat pagi!',
        content='Selamat pagi! Senang bisa membantu Anda hari ini. Ada yang ingin ditanyakan?',
        sources=[],
    )
    add_turn(
        9,
        query='Tidak ada, cuma menyapa saja hehe.',
        content='Hehe, baik! Kalau nanti ada pertanyaan, jangan ragu untuk bertanya ya.',
        sources=[],
    )

    # ── session_id=10 (Andre) — Perumpamaan anak hilang — 5 turn, ada sources ─
    add_turn(
        10,
        query='Apa makna perumpamaan anak yang hilang?',
        reason='Perumpamaan ini menggambarkan kasih dan pengampunan Bapa kepada anak yang kembali.',
        content='Perumpamaan ini menggambarkan kasih dan pengampunan Bapa yang tidak terbatas terhadap anak bungsu yang telah menghambur-hamburkan hartanya, namun disambut kembali dengan sukacita ketika bertobat.',
        sources=SOURCE_PDF_PERUMPAMAAN,
    )
    add_turn(
        10,
        query='Bagaimana dengan sikap anak sulungnya?',
        reason='Anak sulung mewakili sikap yang merasa berhak namun kurang berbelas kasih.',
        content='Anak sulung dalam perumpamaan ini merasa cemburu dan kurang berbelas kasih atas penyambutan adiknya, menggambarkan sikap "merasa berhak" yang juga perlu direnungkan.',
        sources=[],
    )
    add_turn(
        10,
        query='Perumpamaan ini ada di kitab mana?',
        reason='Perumpamaan ini tercatat dalam Injil Lukas.',
        content='Perumpamaan anak yang hilang tercatat dalam Injil Lukas, bab 15, bersama dua perumpamaan lain tentang sesuatu yang hilang lalu ditemukan.',
        sources=SOURCE_PDF_PERUMPAMAAN[1:],
    )
    add_turn(
        10,
        query='Apa relevansinya untuk kehidupan sehari-hari?',
        reason='Perumpamaan ini relevan untuk siapa pun yang merasa jauh dari Tuhan namun ingin kembali.',
        content='Perumpamaan ini relevan bagi siapa pun yang merasa telah jauh menyimpang, sebagai pengingat bahwa selalu ada kesempatan untuk kembali dan diterima dengan kasih, tanpa memandang seberapa jauh kesalahan yang dibuat.',
        sources=[],
    )
    add_turn(
        10,
        query='Terima kasih atas penjelasannya yang mendalam.',
        content='Sama-sama! Semoga perumpamaan ini bisa menjadi renungan yang bermakna bagi Anda.',
        sources=[],
    )

    # ── session_id=11 (Andre) — Baptisan — 3 turn ────────────────────────────
    add_turn(
        11,
        query='Apa makna baptisan dalam iman Kristen?',
        reason='Baptisan melambangkan kematian dan kebangkitan bersama Kristus, serta pernyataan iman.',
        content='Baptisan melambangkan kematian terhadap cara hidup lama dan kebangkitan menjadi ciptaan baru bersama Kristus, sekaligus menjadi pernyataan iman secara terbuka di hadapan jemaat.',
        sources=[],
    )
    add_turn(
        11,
        query='Apakah ada syarat tertentu sebelum dibaptis?',
        reason='Syarat baptisan biasanya melibatkan pengakuan iman dan pemahaman dasar ajaran.',
        content='Umumnya calon yang dibaptis diharapkan memahami dasar-dasar pengakuan iman dan menyatakan keinginan secara sadar untuk mengikuti Kristus, namun syarat detailnya bisa berbeda tergantung tradisi gereja masing-masing.',
        sources=[],
    )
    add_turn(
        11,
        query='Baik, saya akan tanyakan ke gembala gereja saya juga.',
        content='Itu langkah yang baik — gembala atau pendeta di gereja Anda akan bisa memberi panduan yang lebih sesuai dengan tradisi dan persiapan baptisan di sana.',
        sources=[],
    )

    
    conn = engine.connect()
    for stmt in insert_statement:
        conn.execute(stmt)
    conn.commit()