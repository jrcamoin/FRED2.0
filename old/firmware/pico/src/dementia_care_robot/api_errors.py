import json
from urllib.error import HTTPError, URLError


class RemoteServiceError(RuntimeError):
    """A safe, user-facing explanation of a remote API failure."""


def explain_api_error(error: Exception, feature: str) -> RemoteServiceError:
    if isinstance(error, HTTPError):
        detail = ""
        try:
            payload = json.loads(error.read().decode("utf-8", errors="replace"))
            detail = str(payload.get("error", {}).get("message", "")).strip()
        except (json.JSONDecodeError, AttributeError, OSError):
            pass
        if error.code == 401:
            message = "The API key was rejected. Export a valid ROBOT_LLM_API_KEY and restart the server."
        elif error.code == 429:
            message = "The API rate limit or billing quota was reached. Check API billing and usage."
        elif error.code == 400 and feature == "Speech":
            message = "The recorded audio was rejected. Try a short recording in a supported browser."
        else:
            message = f"{feature} service returned HTTP {error.code}."
        if detail and error.code not in (401, 429):
            message += f" {detail[:240]}"
        return RemoteServiceError(message)
    if isinstance(error, (URLError, TimeoutError)):
        if feature == "Local AI":
            return RemoteServiceError("Local AI did not respond. Make sure Ollama is running, then try again; the first reply can take up to two minutes while the model loads.")
        return RemoteServiceError(f"{feature} service could not be reached. Check the internet connection and try again.")
    return RemoteServiceError(f"{feature} processing failed. Check the server terminal for details.")
