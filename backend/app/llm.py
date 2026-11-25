"""One place that talks to the GenAI model.

LLM_PROVIDER:
  local        -> open model from Hugging Face running on YOUR PC via Ollama (100% free, default)
  huggingface  -> Hugging Face Inference API (needs HF_TOKEN; free credit is very small)
  openai       -> any OpenAI-compatible API (LLM_API_KEY)
  fake         -> offline templates, no model (for testing)
If the model call fails, the app falls back to templates so the hiring flow never stops.
"""
from .config import (HF_MODEL, HF_TOKEN, LLM_API_KEY, LLM_MODEL, LLM_PROVIDER, LOCAL_MODEL,
                     LOCAL_URL, PROFILE_FILE)


def company_profile() -> str:
    try:
        return open(PROFILE_FILE, encoding="utf-8").read()
    except OSError:
        return ""


def system_prompt() -> str:
    return ("You are the HR recruitment assistant of the company described below. Write in its tone of voice. "
            "Use ONLY facts from the profile or the request. Never invent salary figures, dates, links or benefits.\n\n"
            "COMPANY PROFILE:\n" + company_profile())


_chat = None


def _langchain_chat():
    global _chat
    if _chat is None:
        from langchain_openai import ChatOpenAI
        if LLM_PROVIDER == "openai":
            _chat = ChatOpenAI(model=LLM_MODEL or "gpt-4o-mini", api_key=LLM_API_KEY, temperature=0.4)
        else:  # local Ollama exposes an OpenAI-compatible endpoint
            _chat = ChatOpenAI(model=LOCAL_MODEL, base_url=LOCAL_URL, api_key="ollama",
                               temperature=0.4, timeout=600, max_retries=0)
    return _chat


def ask(prompt: str, system: str | None = None, fake=None, max_tokens: int = 1200) -> str:
    """Call the LLM. `fake` is a callable giving an offline/fallback answer."""
    if LLM_PROVIDER == "fake":
        return fake() if fake else ""
    system = system or system_prompt()
    try:
        if LLM_PROVIDER == "huggingface":
            from huggingface_hub import InferenceClient
            r = InferenceClient(model=HF_MODEL, token=HF_TOKEN or None).chat_completion(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=0.4)
            return r.choices[0].message.content
        out = _langchain_chat().invoke([("system", system), ("human", prompt)]).content
        return out if isinstance(out, str) else "".join(str(p) for p in out)
    except Exception as e:
        print(f"[LLM ERROR] {LLM_PROVIDER}: {e}")
        if fake:
            print("[LLM] using fallback template")
            return fake()
        raise
