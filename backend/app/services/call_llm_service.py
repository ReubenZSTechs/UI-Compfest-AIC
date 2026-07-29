from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pathlib import Path

import yaml
import logging
import json

from app.core.decorators.log_llm_calls import log_llm_calls, log_output_call
from app.core.exceptions import SchemaValidationError

logger = logging.getLogger(__name__)



CONFIG = {
    'MODEL_BRIDGE': {
        'llm': {
            'url': 'http://localhost:15000/v1',
            'served_model_name': 'LLM'
        },
        'embedding': {
            'url': 'http://localhost:15001/v1',
            'served_model_name': 'embedding'
        }
    },

    "STRUCTURED_OVERRIDES": {
        'frequency_penalty': 0.0,
        'presence_penalty': 0.0,
        'temperature': 0.0,
        'top_p': 1.0
    }
}


class AgentReader:
    def __init__(self):
        pass

    def read_config(self, config: str) -> dict:
        try:
            with open(config, "r", encoding='utf-8') as f:
                agent_config = yaml.safe_load(f)

            return agent_config
        
        except FileNotFoundError as e:
            logger.error(f"YAML config not found:\n\n{e}")
            return {}

        except yaml.YAMLError as e:
            logger.error(f"Malformed yaml configuration:\n\n{e}")
            return {}

        except Exception as e:
            logger.error(f"Another error occured:\n\n{e}")
            return {}


    def read_schema(self, schema_path: str, base_dir: Path) -> dict:
        resolved = Path(schema_path)
        if not resolved.is_absolute():
            resolved = base_dir / resolved

        try:
            with open(resolved, "r", encoding='utf-8') as f:
                return json.load(f)

        except FileNotFoundError:
            raise FileNotFoundError(f"Schema file not found: {resolved}")

        except json.JSONDecodeError as e:
            raise SchemaValidationError(f"Schema file is not valid JSON: {e}")
        

class Agent:
    def __init__(self, yaml_config: str, model_bridge: dict, schema_dir: Path, default_timeout: float = 300.0, default_max_retries: int = 2, api_key: str = "not-needed"):
        self.model_bridge = model_bridge
        self.schema_dir = schema_dir
        self.config_dir = Path(yaml_config).parent
        self.reader = AgentReader()
        self.agent_config = self.reader.read_config(yaml_config)

        if not self.agent_config:
            raise ValueError(f"Empty or unreadable agent config: {yaml_config}")

        self.agent_id = self.agent_config.get("agent")
        if not self.agent_id:
            raise KeyError("Missing 'agent' block in yaml configuration")

        missing_keys = []
        for key in ['model_type', 'role']:
            if key not in self.agent_id:
                missing_keys.append(key)

        if missing_keys:
            raise KeyError(f"Missing agent keys in yaml configuration: {missing_keys}")

        self.agent_system_prompt = self.agent_config.get("system_prompt")
        if not self.agent_system_prompt:
            raise KeyError("Missing 'system_prompt' in yaml configuration")

        self.agent_generation_config = self.agent_config.get("generation", {})
        self.role = self.agent_id["role"]

        self._resolve_bridge()
        self._resolve_structured_output()

        self.client = OpenAI(
            base_url=self.bridge_url,
            api_key=api_key,
            timeout=self.agent_generation_config.get("timeout", default_timeout),
            max_retries=self.agent_generation_config.get("max_retries", default_max_retries),
        )

        self.last_usage = None
        logger.info(
            f"Initiated agent role={self.role} "
            f"model={self.model_name} structured={self.structured_enabled}"
        )

    def _resolve_bridge(self):
        model_type = self.agent_id["model_type"]
        bridge = self.model_bridge.get(model_type)

        if bridge is None:
            raise ValueError(
                f"No vLLM container bridge available for model_type "
                f"'{model_type}' (role: {self.role})"
            )

        self.bridge_url = bridge["url"]
        self.model_name = bridge["served_model_name"]


    def _resolve_structured_output(self):
        structured_config = self.agent_config.get('structured_output', {})
        self.structured_enabled = structured_config.get('enabled', False)
        self.schema_name = structured_config.get('name', self.role)
        self.strict_schema = structured_config.get('strict', True)
        self.repair_attempts = structured_config.get('repair_attempts', 1)
        self.json_schema = None

        if not self.structured_enabled:
            return

        inline_schema = structured_config.get('schema')
        schema_path = structured_config.get('schema_path')

        if inline_schema:
            self.json_schema = inline_schema

        elif schema_path:
            self.json_schema = self.reader.read_schema(schema_path, self.schema_dir)

        else:
            raise SchemaValidationError(
                f"structured_output enabled for role '{self.role}' "
                f"but neither 'schema' nor 'schema_path' was provided"
            )


    def format_msg_payload(self, user_prompt, prior_messages=None): # TODO Add context agent manager for context management on system prompt and user prompt
        agent_input = [
            {
                'role': 'system',
                'content': self.agent_system_prompt
            }
        ]

        if prior_messages:
            agent_input.extend(prior_messages)

        agent_input.append({'role': 'user', 'content': user_prompt})

        return agent_input


    def format_generation_args(self):
        # TODO Find more generation arguments that is OpenAI compatible
        generation_args = {
            'max_tokens': self.agent_generation_config.get('max_tokens', 4096), # TODO Remove max_tokens when agent context manager is built
            'temperature': self.agent_generation_config.get('temperature', 0.1),
            'top_p': self.agent_generation_config.get('top_p', 0.9),
            'frequency_penalty': self.agent_generation_config.get("frequency_penalty", 0.0),
            'presence_penalty': self.agent_generation_config.get("presence_penalty", 0.0)
        }

        if self.structured_enabled:
            for k, v in CONFIG['STRUCTURED_OVERRIDES'].items():
                if k not in self.agent_generation_config:
                    generation_args[k] = v

        return generation_args


    def format_extra_body(self, extra_args=None):
        extra_body = {}

        min_p = self.agent_generation_config.get('min_p')
        if min_p is not None:
            extra_body['min_p'] = min_p

        repetition_penalty = self.agent_generation_config.get('repetition_penalty')
        if repetition_penalty is not None:
            extra_body['repetition_penalty'] = repetition_penalty

        if self.structured_enabled:
            extra_body['guided_json'] = self.json_schema
            extra_body['guided_decoding_backend'] = self.agent_generation_config.get(
                'guided_decoding_backend', 'xgrammar'
            )

        if extra_args:
            extra_body.update(extra_args)

        return extra_body


    def format_response_format(self):
        if not self.structured_enabled:
            return None

        return {
            'type': 'json_schema',
            'json_schema': {
                'name': self.schema_name,
                'schema': self.json_schema,
                'strict': self.strict_schema
            }
        }


    def parse_structured_output(self, raw_output):
        cleaned = raw_output.strip()

        if cleaned.startswith('```'):
            cleaned = cleaned.split('```')[1]
            if cleaned.startswith('json'):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        return json.loads(cleaned)


    def build_request_kwargs(self, msg_payload, extra_args):
        request_kwargs = {
            'model': self.model_name,
            'messages': msg_payload,
            'extra_body': self.format_extra_body(extra_args)
        }

        response_format = self.format_response_format()
        if response_format is not None:
            request_kwargs['response_format'] = response_format

        request_kwargs.update(self.format_generation_args())

        return request_kwargs
    

    @log_llm_calls
    def generate_response(self, user_prompt, extra_args=None, prior_messages=None):
        msg_payload = self.format_msg_payload(user_prompt, prior_messages)
        request_kwargs = self.build_request_kwargs(msg_payload, extra_args)

        response = self.client.chat.completions.create(**request_kwargs)
        self.last_usage = response.usage
        content = response.choices[0].message.content

        finish_reason = response.choices[0].finish_reason
        if finish_reason == 'length':
            logger.warning(
                f"Role '{self.role}' hit max_tokens; output is truncated"
            )

        return content


    def generate_structured(self, user_prompt, extra_args=None):
        if not self.structured_enabled:
            raise ValueError(
                f"Role '{self.role}' is not configured for structured output"
            )

        attempt = 0
        prior_messages = None
        last_error = None

        while attempt <= self.repair_attempts:
            raw_output = self.generate_response(
                user_prompt=user_prompt,
                extra_args=extra_args,
                prior_messages=prior_messages
            )

            try:
                return self.parse_structured_output(raw_output)

            except json.JSONDecodeError as e:
                last_error = e
                attempt += 1
                logger.warning(
                    f"Role '{self.role}' returned unparseable JSON "
                    f"on attempt {attempt}: {e}"
                )
                prior_messages = [
                    {'role': 'assistant', 'content': raw_output},
                    {
                        'role': 'user',
                        'content': (
                            f"That output failed JSON parsing: {e}. "
                            f"Return only the corrected raw JSON object."
                        )
                    }
                ]

        raise SchemaValidationError(
            f"Role '{self.role}' failed to produce valid JSON after "
            f"{self.repair_attempts + 1} attempts: {last_error}"
        )
    

    @log_output_call
    def generate_answer(self, user_prompt, extra_args=None, prior_messages=None):
        msg_payload = self.format_msg_payload(user_prompt, prior_messages)
        request_kwargs = self.build_request_kwargs(msg_payload, extra_args)
        request_kwargs['stream'] = True
        request_kwargs['stream_options'] = {'include_usage': True}

        stream = self.client.chat.completions.create(**request_kwargs)

        for chunk in stream:
            if chunk.usage:
                self.last_usage = chunk.usage

            if chunk.choices:
                delta = chunk.choices[0].delta.content
            else:
                delta = None

            if delta:
                yield delta