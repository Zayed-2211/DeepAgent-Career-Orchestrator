"""
HTML / text cleaning utilities for scraped job descriptions.
"""

import re
from html import unescape


def clean_html(raw_html: str | None) -> str | None:
    """
    Strip HTML tags, decode entities, and normalize whitespace.
    Returns None if input is None or empty after cleaning.
    """
    if not raw_html:
        return None

    # Decode HTML entities (&amp; → &, etc.)
    text = unescape(raw_html)

    # Replace <br>, <p>, <li> with newlines for readability
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)

    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)           # Collapse horizontal spaces
    text = re.sub(r"\n{3,}", "\n\n", text)         # Max 2 consecutive newlines
    text = "\n".join(line.strip() for line in text.splitlines())

    text = text.strip()
    return text if text else None
