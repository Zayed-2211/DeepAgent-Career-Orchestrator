"""
Contact information extraction from raw job post text.

Extracts:
  - Egyptian mobile phone numbers (all formats)
  - Email addresses
  - WhatsApp links
  - Telegram handles

Egyptian mobile numbers always start with:
  010x (Vodafone), 011x (Etisalat/e&), 012x (Orange), 015x (WE/Telecom Egypt)

Handles formats:
  - 01012345678         (standard 11-digit)
  - +201012345678       (international)
  - 00201012345678      (international, double-zero prefix)
  - 0101 234 5678       (with spaces)
  - 0101-234-5678       (with dashes)
  - ٠١٠١٢٣٤٥٦٧٨        (Arabic-Indic numerals)
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# Arabic-Indic numeral normalization
# ---------------------------------------------------------------------------
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize_arabic(text: str) -> str:
    """Replace Arabic-Indic numerals with ASCII digits."""
    return text.translate(_AR_DIGITS)


# ---------------------------------------------------------------------------
# Pre-compiled regex patterns
# ---------------------------------------------------------------------------

# Egyptian mobile: 010/011/012/015 followed by 8 digits.
# Supports: optional +20 / 0020 prefix, optional spaces/dashes between groups.
_PHONE_RE = re.compile(
    r"""
    (?:
        (?:\+20|0020)                # international prefix (+20 or 0020)
        [\s\-]?                      # optional separator
        (1[0-2,5]\d{8})             # mobile number without leading 0
        |
        (0[1][0-2,5]\d{8})          # local format: 01x-xxxxxxxx (tight, no spaces)
        |
        (0[1][0-2,5]                 # local format: 01x with spaces/dashes
         [\s\-]?\d{3,4}
         [\s\-]?\d{4,5})
    )
    """,
    re.VERBOSE,
)

# Standard email pattern — permissive but practical
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# WhatsApp link (wa.me, api.whatsapp.com, chat.whatsapp.com)
_WHATSAPP_RE = re.compile(
    r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com/send|chat\.whatsapp\.com)/[\w+\-?=&%]+"
)

# Telegram handle (@username or t.me/username)
_TELEGRAM_RE = re.compile(
    r"(?:https?://)?(?:t(?:elegram)?\.me/)(\w+)|@(\w{5,})"
)


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

def extract_phones(text: str) -> list[str]:
    """
    Extract Egyptian mobile phone numbers from text.

    Returns a deduplicated list of normalized 11-digit strings (e.g. '01012345678').
    Handles Arabic-Indic numerals, spaces, dashes, and international prefixes.
    """
    if not text:
        return []

    text = _normalize_arabic(text)
    found = set()

    for match in _PHONE_RE.finditer(text):
        # Concatenate all 3 capture groups (only one is ever non-empty)
        raw = "".join(g for g in match.groups() if g)
        # Strip all separators and normalize to 11 digits
        digits = re.sub(r"[\s\-]", "", raw)
        # If international format, prepend 0
        if digits.startswith("1") and len(digits) == 10:
            digits = "0" + digits
        # Validate final length and prefix
        if len(digits) == 11 and digits[:3] in ("010", "011", "012", "015"):
            found.add(digits)

    return sorted(found)


def extract_emails(text: str) -> list[str]:
    """
    Extract email addresses from text.

    Returns a deduplicated list of lowercase emails.
    """
    if not text:
        return []
    found = set(_EMAIL_RE.findall(text))
    return sorted(e.lower() for e in found)


def extract_whatsapp(text: str) -> list[str]:
    """Extract WhatsApp links from text."""
    if not text:
        return []
    return sorted(set(_WHATSAPP_RE.findall(text)))


def extract_telegram(text: str) -> list[str]:
    """
    Extract Telegram handles from text.

    Returns @username strings.
    """
    if not text:
        return []
    found = set()
    for match in _TELEGRAM_RE.finditer(text):
        handle = match.group(1) or match.group(2)
        if handle:
            found.add(f"@{handle}")
    return sorted(found)


def extract_all(text: str) -> dict:
    """
    Run all extractors on the given text.

    Returns:
        {
            "phones": ["01012345678", ...],
            "emails": ["hr@company.com", ...],
            "whatsapp": ["https://wa.me/...", ...],
            "telegram": ["@channel", ...],
        }
    """
    return {
        "phones": extract_phones(text),
        "emails": extract_emails(text),
        "whatsapp": extract_whatsapp(text),
        "telegram": extract_telegram(text),
    }


def primary_contact(extracted: dict) -> str | None:
    """
    Return the single strongest contact signal for fingerprinting.

    Priority: email > phone > whatsapp > telegram > None
    """
    if extracted.get("emails"):
        return extracted["emails"][0]
    if extracted.get("phones"):
        return extracted["phones"][0]
    if extracted.get("whatsapp"):
        return extracted["whatsapp"][0]
    if extracted.get("telegram"):
        return extracted["telegram"][0]
    return None
