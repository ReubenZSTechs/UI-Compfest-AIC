"""Exception khusus modul simulation (perancangan flowchart manual)."""

from __future__ import annotations

from typing import Any


class SimulationError(Exception):
    def __init__(self, stage: str, message: str, *, details: list[Any] | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.details = details or []

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "message": self.message, "details": self.details}


class FactoryNotFoundError(SimulationError):
    def __init__(self, factory_id: str) -> None:
        super().__init__(
            "factory_lookup",
            f"Factory dengan factory_id '{factory_id}' tidak ditemukan. "
            f"Buat factory terlebih dahulu melalui POST /factories.",
        )


class SimulationValidationError(SimulationError):
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__("validation", message, details=details)


class SimulationPersistenceError(SimulationError):
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__("persistence", message, details=details)