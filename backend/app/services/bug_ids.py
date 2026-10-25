import re


def extract_bug_ids(text: str, pattern: str, max_ids: int = 5) -> list[str]:
    """Deterministic extraction: unique IDs in order of first appearance, capped.

    The pattern is configurable because it must match the real tracker's ID format.
    Detected IDs are candidates only; the tracker decides whether they exist.
    """
    seen: dict[str, None] = {}
    for match in re.finditer(pattern, text):
        seen.setdefault(match.group(0), None)
        if len(seen) >= max_ids:
            break
    return list(seen)
