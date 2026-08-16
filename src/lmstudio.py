"""Local LLM client: supports both Ollama and LM Studio."""
import json
import requests


class LMStudioError(Exception):
    pass


class LMStudio:
    """Unified client for local LLM servers (Ollama or LM Studio)."""

    def __init__(self, base_url="http://localhost:11434/v1", timeout=600):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.backend = self._detect_backend()

    def _detect_backend(self):
        """Detect if we're talking to Ollama or LM Studio."""
        if "11434" in self.base_url:
            return "ollama"
        if "1234" in self.base_url:
            return "lmstudio"
        # Try to detect by making a test request
        try:
            if "ollama" in requests.get(self.base_url + "/tags", timeout=2).text:
                return "ollama"
        except Exception:
            pass
        return "lmstudio"

    def _post(self, path, payload, timeout=None):
        """Make an HTTP POST request to the LLM server."""
        timeout = timeout or self.timeout
        try:
            resp = requests.post(self.base_url + path, json=payload, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            backend_name = "Ollama" if self.backend == "ollama" else "LM Studio"
            port = "11434" if self.backend == "ollama" else "1234"
            raise LMStudioError(
                f"Cannot reach {backend_name} at {self.base_url}. "
                f"Start {backend_name} with: {'ollama serve' if self.backend == 'ollama' else 'LM Studio (Developer tab -> Start Server)'}"
            ) from e
        except requests.exceptions.Timeout as e:
            raise LMStudioError(f"Request timed out after {timeout}s.") from e
        if resp.status_code == 404:
            raise LMStudioError(
                f"Model '{payload.get('model')}' not found. "
                f"For Ollama: ollama pull <model>. For LM Studio: load model in UI."
            )
        if resp.status_code != 200:
            raise LMStudioError(f"Server error {resp.status_code}: {resp.text[:400]}")
        return resp.json()

    def list_models(self):
        """Return the list of model ids available."""
        try:
            if self.backend == "ollama":
                # Ollama uses /api/tags instead of /models
                resp = requests.get(self.base_url.replace("/v1", "") + "/api/tags", timeout=10)
                resp.raise_for_status()
                return [m["name"].split(":")[0] for m in resp.json().get("models", [])]
            else:
                # LM Studio uses /models
                resp = requests.get(self.base_url + "/models", timeout=10)
                resp.raise_for_status()
                return [m["id"] for m in resp.json().get("data", [])]
        except requests.exceptions.RequestException:
            return []

    def is_available(self):
        """Check if the server is reachable."""
        try:
            if self.backend == "ollama":
                requests.get(self.base_url.replace("/v1", "") + "/api/tags", timeout=5)
            else:
                requests.get(self.base_url + "/models", timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def chat(self, messages, model, temperature=0.8, max_tokens=4096, json_mode=False,
             timeout=None):
        """Send a chat request; return the assistant text.

        json_mode=True requests a JSON object response;
        the server may reject it for models without grammar support.
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode and self.backend == "lmstudio":
            payload["response_format"] = {"type": "json_object"}
        
        data = self._post("/chat/completions", payload, timeout=timeout)
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as e:
            raise LMStudioError(f"Unexpected response: {str(data)[:300]}") from e
