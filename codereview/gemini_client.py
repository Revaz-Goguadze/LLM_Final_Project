from .llm_utils import RateLimiter, should_retry, backoff_sleep


class GeminiClient:
    """Gemini client wrapper with fallback and rate limiting."""

    def __init__(
        self,
        api_key: str,
        model: str,
        min_delay: float,
        max_retries: int,
    ):
        self.model = model
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(min_delay)
        self._client = None

        try:
            from google import genai as genai_module
        except Exception as exc:
            raise RuntimeError(
                "google.genai is required. Install the google-genai package."
            ) from exc

        self._client = genai_module.Client(api_key=api_key)

    def generate(self, prompt: str) -> str:
        for attempt in range(self.max_retries):
            try:
                self.rate_limiter.wait()
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                text = getattr(response, "text", None)
                if text:
                    return text
                return str(response)
            except Exception as e:
                if attempt < self.max_retries - 1 and should_retry(str(e)):
                    backoff_sleep(attempt)
                    continue
                return ""
        return ""
