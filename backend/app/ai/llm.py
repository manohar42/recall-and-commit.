"""Gemini access through LangChain. The rest of the app never imports the provider SDK directly."""
import logging

from app.config import get_settings

logger = logging.getLogger("recall_commit.ai")


class AIError(RuntimeError):
    """A configured model call failed (bad key, quota, network, invalid output)."""


def get_chat_model():
    """Return a LangChain chat model, or None when Gemini is not configured."""
    settings = get_settings()
    if not settings.ai_configured:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key.strip(),
        temperature=settings.ai_temperature,
        max_retries=settings.ai_max_retries,
        timeout=settings.ai_timeout_seconds,
    )


def structured_call(model, schema, system: str, user: str):
    """Invoke the model and return a validated instance of `schema`."""
    try:
        result = model.with_structured_output(schema).invoke([("system", system), ("human", user)])
    except Exception as exc:  # provider errors vary widely; surface a readable message
        logger.warning("Gemini call failed: %s", exc)
        raise AIError(friendly_error(exc)) from exc
    if result is None:
        raise AIError("Gemini returned no structured output.")
    if isinstance(result, dict):
        result = schema.model_validate(result)
    return result


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "api key" in lowered or "api_key" in lowered or "permission" in lowered or "401" in lowered or "403" in lowered:
        return "Gemini rejected the API key. Check GOOGLE_API_KEY in your .env file."
    if "429" in lowered or "quota" in lowered or "resource_exhausted" in lowered or "rate" in lowered:
        return "Gemini rate limit or quota reached. Wait a minute and run the analysis again."
    if "not found" in lowered or "404" in lowered:
        return f"Gemini model '{get_settings().gemini_model}' was not found. Check GEMINI_MODEL in your .env file."
    return f"Gemini request failed: {text[:300]}"


def ai_status() -> dict:
    s = get_settings()
    return {
        "configured": s.ai_configured,
        "provider": "google-gemini",
        "model": s.gemini_model,
        "framework": "LangChain + LangGraph",
        "mode": "gemini" if s.ai_configured else "rules_fallback",
        "message": (
            f"Gemini ({s.gemini_model}) is active for commitment review, recall answers, and What If explanations."
            if s.ai_configured
            else "GOOGLE_API_KEY is not set. The app is using the built-in rules fallback; add a key to enable Gemini."
        ),
    }
