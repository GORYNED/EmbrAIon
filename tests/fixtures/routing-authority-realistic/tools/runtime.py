"""Generic runtime plumbing with no manually selected model."""

def record_attempt(model, provider, effort, fallback):
    values = {"model": model, "provider": provider, "effort": effort}
    values["fallback"] = fallback
    fallbacks = [fallback]
    values["fallbacks"] = fallbacks
    return values


def choose(model: str, provider: str):
    return provider, model
