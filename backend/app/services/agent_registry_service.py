import logging
import threading
from functools import lru_cache
from enum import StrEnum
from pathlib import Path

import yaml

from app.core.agent_config import AgentSettings, get_agent_settings
from app.services.call_llm_service import Agent
from app.core.exceptions import AgentNotFoundError, DuplicateAgentRoleError

logger = logging.getLogger(__name__)


class AgentRole(StrEnum):
    FACTORY_STRUCTURE = "factory_md_creator"
    WORKER_PROFILE = "cv_to_worker_profile_creator"
    WORKER_COMPATIBILITY = "worker_job_compatibility_creator"
    INIT_STATE = "init_state_creator"
    SIMULATION_STATE = "simulation_state_agent"
    OPTIMIZATION_SCENARIO = "optimization_scenario_agent"

    CHATBOT_QUERY_REWRITER = "chatbot_query_rewriter"
    CHATBOT_ROUTER = "chatbot_router"
    CHATBOT_TWIN_ANALYST = "chatbot_twin_analyst"
    CHATBOT_SCENARIO_EXPLAINER = "chatbot_scenario_explainer"
    CHATBOT_GENERAL = "chatbot_general"
    CHATBOT_SUMMARIZER = "chatbot_summarizer"
    FACTORY_CLARIFICATION = "factory_clarification_agent"
    CV_CLARIFICATION = "cv_clarification_agent"


class AgentRegistry:
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.model_bridge = settings.model_bridge
        self._role_paths: dict[str, Path] = {}
        self._instances: dict[str, Agent] = {}
        self._lock = threading.RLock()

        self._discover()

        if settings.AGENT_EAGER_LOAD:
            self.preload()


    def _discover(self) -> None:
        config_dir = self.settings.config_dir
        yaml_files = sorted(config_dir.glob("*.yaml")) + sorted(config_dir.glob("*.yml"))

        if not yaml_files:
            raise FileNotFoundError(
                f"Tidak ada file .yaml ditemukan di {config_dir}. "
                f"Pastikan file konfigurasi agent sudah disalin ke direktori ini."
            )

        skipped = []

        for path in yaml_files:
            role = self._peek_role(path)
            if role is None:
                skipped.append(path.name)
                continue

            if role in self._role_paths:
                raise DuplicateAgentRoleError(
                    f"Role '{role}' terdaftar di dua file: "
                    f"{self._role_paths[role]} dan {path}"
                )

            self._role_paths[role] = path

        if skipped:
            raise ValueError(
                f"{len(skipped)} file YAML ditemukan tapi gagal di-parse sebagai agent config: "
                f"{skipped}. Cek field 'agent.role' di tiap file."
            )

        if not self._role_paths:
            raise FileNotFoundError(
                f"File .yaml ditemukan di {config_dir} tapi tidak satupun valid sebagai agent config."
            )

        logger.info(f"Agent registry menemukan {len(self._role_paths)} role")


    def _peek_role(self, path: Path) -> str | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)

        except yaml.YAMLError as e:
            logger.error(f"Melewati YAML rusak {path}: {e}")
            return None

        if not isinstance(raw, dict):
            logger.error(f"Melewati YAML non-mapping {path}")
            return None

        agent_block = raw.get("agent")
        if not isinstance(agent_block, dict):
            logger.error(f"Melewati {path}: blok 'agent' tidak ada")
            return None

        role = agent_block.get("role")
        if not role:
            logger.error(f"Melewati {path}: field 'role' tidak ada")
            return None

        return role


    def get(self, role: str) -> Agent:
        instance = self._instances.get(role)
        if instance is not None:
            return instance

        with self._lock:
            instance = self._instances.get(role)
            if instance is not None:
                return instance

            path = self._role_paths.get(role)
            if path is None:
                raise AgentNotFoundError(
                    f"Role '{role}' tidak terdaftar. "
                    f"Tersedia: {sorted(self._role_paths.keys())}"
                )

            instance = Agent(
                yaml_config=str(path),
                model_bridge=self.model_bridge,
                schema_dir=self.settings.schema_dir,
                default_timeout=self.settings.AGENT_DEFAULT_TIMEOUT,
                default_max_retries=self.settings.AGENT_DEFAULT_MAX_RETRIES,
                api_key=self.settings.AGENT_API_KEY,
            )
            self._instances[role] = instance
            logger.info(f"Agent '{role}' dimuat dari {path.name}")

            return instance


    def preload(self, roles: list[str] | None = None) -> None:
        targets = roles or list(self._role_paths.keys())
        for role in targets:
            self.get(role)


    def list_roles(self) -> list[str]:
        return sorted(self._role_paths.keys())


    def is_loaded(self, role: str) -> bool:
        return role in self._instances


    def reload(self, role: str | None = None) -> None:
        with self._lock:
            if role is None:
                self._instances.clear()
                self._role_paths.clear()
                self._discover()
                logger.info("Agent registry dimuat ulang sepenuhnya")
                return

            self._instances.pop(role, None)
            logger.info(f"Agent '{role}' di-invalidate, akan dimuat ulang saat dipakai")


@lru_cache
def get_agent_registry() -> AgentRegistry:
    return AgentRegistry(settings=get_agent_settings())


def get_agent(role: AgentRole | str) -> Agent:
    return get_agent_registry().get(AgentRole(role))