import json
import logging
from functools import wraps
from pathlib import Path
from time import perf_counter

LOG_FILE = Path(__file__).resolve().parents[1] / "logging" / "llm_call_logs.jsonl"

logger = logging.getLogger(__name__)


def _usage_fields(usage, latency):
    """Build token usage metrics from an OpenAI-style usage object."""
    if not usage:
        return {
            "prompt_tokens": None,
            "generated_tokens": None,
            "token_generation": None,
            "total_tokens": None,
        }
    prompt_tokens = usage.prompt_tokens or 0
    generated_tokens = usage.completion_tokens or 0
    return {
        "prompt_tokens": prompt_tokens,
        "generated_tokens": generated_tokens,
        "token_generation": round(generated_tokens / latency, 5) if latency > 0 else None,
        "total_tokens": prompt_tokens + generated_tokens,
    }


def _write_log(payload):
    """Append one JSON line to the LLM call log without ever failing the caller."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception as error:
        logger.warning("Gagal menulis log LLM: %s", error)


def log_llm_calls(func):
    """Log prompt, output, latency and token usage of a non-streaming LLM call."""
    @wraps(func)
    def wrapper(self, user_prompt, *args, **kwargs):
        status = "success"
        result = None
        start_time = perf_counter()

        try:
            result = func(self, user_prompt, *args, **kwargs)
            return result
        except Exception:
            status = "error"
            raise
        finally:
            latency = perf_counter() - start_time
            payload = {
                "input_prompt": user_prompt,
                "model_name": getattr(self, "model_name", None),
                "status": status,
                "model_latency": latency,
            }
            if status == "success":
                payload.update(_usage_fields(getattr(self, "last_usage", None), latency))
                payload["output"] = result
            _write_log(payload)

    return wrapper


def log_output_call(func):
    """Log prompt, concatenated output, latency and token usage of a streaming LLM call."""
    @wraps(func)
    def wrapper(self, user_prompt, *args, **kwargs):
        status = "success"
        output = ""
        start_time = perf_counter()

        try:
            for chunk in func(self, user_prompt, *args, **kwargs):
                output += chunk
                yield chunk
        except Exception:
            status = "error"
            raise
        finally:
            latency = perf_counter() - start_time
            payload = {
                "input_prompt": user_prompt,
                "model_name": getattr(self, "model_name", None),
                "status": status,
                "model_latency": latency,
            }
            if status == "success":
                payload.update(_usage_fields(getattr(self, "last_usage", None), latency))
                payload["output"] = output
            _write_log(payload)

    return wrapper
