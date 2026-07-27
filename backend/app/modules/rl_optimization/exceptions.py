# app/modules/rl_optimization/exceptions.py
"""
Domain-specific exceptions untuk RL Optimization.

Semua inherit dari app.core.exceptions.AppError, jadi otomatis ditangani
oleh handler global di core/exceptions.py (dikonversi ke response HTTP
yang tepat) tanpa perlu try/except manual di tiap endpoint.

Dipisah dari core/exceptions.py karena pesan errornya spesifik-domain
(menyebut factory_id, job_id, scenario_id) — kalau digabung ke core,
core jadi tahu detail domain yang seharusnya tidak perlu diketahuinya.
"""

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError


class FactoryNotFoundError(NotFoundError):
    def __init__(self, factory_id: str):
        super().__init__(f"Factory dengan factory_id '{factory_id}' tidak ditemukan.")
        self.factory_id = factory_id


class DigitalTwinNotFoundError(NotFoundError):
    def __init__(self, factory_id: str):
        super().__init__(
            f"Digital twin untuk factory_id '{factory_id}' belum ada. "
            "Lakukan ingestion terlebih dahulu."
        )
        self.factory_id = factory_id


class LiveSimulationNotFoundError(NotFoundError):
    def __init__(self, factory_id: str):
        super().__init__(f"Live simulation state untuk factory_id '{factory_id}' tidak ditemukan.")
        self.factory_id = factory_id


class OptimizationJobNotFoundError(NotFoundError):
    def __init__(self, job_id: str):
        super().__init__(f"Optimization job '{job_id}' tidak ditemukan.")
        self.job_id = job_id


class OptimizationJobNotConvergedError(ValidationAppError):
    """Dilempar saat scenario/hasil diminta tapi job belum selesai training."""

    def __init__(self, job_id: str, current_status: str):
        super().__init__(
            f"Optimization job '{job_id}' belum selesai (status saat ini: '{current_status}'). "
            "Tunggu hingga status menjadi 'converged'."
        )
        self.job_id = job_id
        self.current_status = current_status


class ScenarioNotFoundError(NotFoundError):
    def __init__(self, job_id: str, scenario_id: str):
        super().__init__(f"Skenario '{scenario_id}' tidak ditemukan pada job '{job_id}'.")
        self.job_id = job_id
        self.scenario_id = scenario_id


class ScenarioAlreadyAppliedError(ConflictError):
    def __init__(self, scenario_id: str, applied_at: str):
        super().__init__(
            f"Skenario '{scenario_id}' sudah diterapkan sebelumnya pada {applied_at}. "
            "Terapkan ulang hanya jika memang disengaja."
        )
        self.scenario_id = scenario_id


class InvalidOptimizationConstraintsError(ValidationAppError):
    def __init__(self, reason: str):
        super().__init__(f"Constraint optimasi tidak valid: {reason}")