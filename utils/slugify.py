import re

def safe_slug(text: str, max_length: int = 80) -> str:
    """Create a safe underscore_slug from a title (lowercase, alnum + _)."""
    text = (text or "").lower().strip()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:max_length].strip("_")
