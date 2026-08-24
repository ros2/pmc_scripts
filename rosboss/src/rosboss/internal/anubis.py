from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import requests


def detect_anubis(content: str | bytes, response: requests.Response | None = None) -> bool:
    """Check if the provided content or HTTP response indicates Anubis bot protection."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    content_lower = content.lower()
    if (
        "anubis" in content_lower
        or "making sure you're not a bot" in content_lower
        or "making sure you" in content_lower
    ):
        return True

    if response is not None:
        if "anubis" in response.headers.get("Server", "").lower():
            return True
        if any("anubis" in k.lower() for k in response.cookies.keys()):
            return True

    return False
