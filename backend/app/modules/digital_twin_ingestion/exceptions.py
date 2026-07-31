class DigitalTwinNotFoundError(Exception):
    """Tidak ada snapshot digital twin untuk factory_id yang diminta."""
    def __init__(self, factory_id: str | None = None):
        self.factory_id = factory_id
        msg = (
            f"Digital twin snapshot untuk factory_id={factory_id!r} tidak ditemukan."
            if factory_id
            else "Belum ada digital twin snapshot yang tersimpan."
        )
        super().__init__(msg)