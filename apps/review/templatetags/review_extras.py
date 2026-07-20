from django import template

register = template.Library()


@register.filter
def humanize_clause(value: str) -> str:
    """Turn snake_case / kebab ids into plain labels (governing_law → Governing law)."""
    raw = (value or "").strip()
    if not raw:
        return "Untitled rule"
    text = raw.replace("_", " ").replace("-", " ").strip()
    # Prefer sentence case for multi-word clause types
    parts = [p for p in text.split() if p]
    if not parts:
        return "Untitled rule"
    return " ".join([parts[0].capitalize()] + [p.lower() for p in parts[1:]])
