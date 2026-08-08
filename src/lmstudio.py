"""Minimal OpenAI-compatible client for LM Studio's local server."""
import requests


class LMStudioError(Exception):
    pass


class LMStudio:
    """Talk to a local LM Studio server (OpenAI-compatible /v1 API)."""

    def __init__(self, base_url="http://localhost:1234/v1", timeout=600):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path, payload):
        try:
            resp = requests.post(self.base_url + path, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            raise LMStudioError(
                f"Cannot reach LM Studio at {self.base_url}. "
                "Start LM Studio, load a model, and enable the local server "
                "(Developer tab -> Start Server)."
            ) from e
        except requests.exceptions.Timeout as e:
            raise LMStudioError(f"LM Studio request timed out after {self.timeout}s.") from e
        if resp.status_code == 404:
            raise LMStudioError(
                f"Model '{payload.get('model')}' not found on LM Studio. "
                "Load the model in LM Studio first, or check config.json -> lmstudio.model."
            )
        if resp.status_code != 200:
            raise LMStudioError(f"LM Studio error {resp.status_code}: {resp.text[:400]}")
        return resp.json()

    def list_models(self):
        """Return the list of model ids served by LM Studio."""
        try:
            resp = requests.get(self.base_url + "/models", timeout=10)
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]
        except requests.exceptions.RequestException:
            return []

    def is_available(self):
        try:
            requests.get(self.base_url + "/models", timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def chat(self, messages, model, temperature=0.8, max_tokens=4096, json_mode=False):
        """Send a chat request; return the assistant text.

        json_mode=True requests a JSON object response via response_format;
        the server may reject it for models without grammar support, in which
        case callers should retry with json_mode=False.
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post("/chat/completions", payload)
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as e:
            raise LMStudioError(f"Unexpected LM Studio response: {str(data)[:300]}") from e
