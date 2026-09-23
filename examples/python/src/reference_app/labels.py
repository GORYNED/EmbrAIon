def normalize_label(value: str) -> str:
    """Normalize a short user-facing label."""

    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("label must not be empty")

    return normalized.title()
