"""
Fuzzy near-duplicate detection using MinHash + LSH.

Used as the LAST dedup layer — after Tier 1 (job_uid) and Tier 2 (fingerprint).
Catches copy-paste job descriptions that differ slightly between posts
(e.g. same JD posted by two different recruiters with minor edits).

Algorithm:
  1. Tokenize post description into character 3-grams
  2. Compute MinHash signature (128 permutations)
  3. Use MinHashLSH index to find similar posts (threshold: 0.75)
  4. If similar AND same company → mark as near-duplicate

Threshold guidance:
  - 0.75 (default): Good balance. Catches copy-paste with minor edits.
  - 0.60: More aggressive. May flag different jobs at same company.
  - 0.90: Conservative. Only catches nearly identical posts.

Dependency: datasketch>=1.6.0
"""

import re
from typing import Iterable

from datasketch import MinHash, MinHashLSH
from loguru import logger


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Number of MinHash permutations — higher = more accurate, slower
_NUM_PERM = 128

# Default Jaccard similarity threshold for near-duplicate detection
_DEFAULT_THRESHOLD = 0.75

# Min text length to bother hashing (very short posts can't be meaningfully compared)
_MIN_TEXT_LENGTH = 50


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------

def _tokenize(text: str, ngram: int = 3) -> set[bytes]:
    """
    Convert text to a set of character n-grams for MinHash.

    Character 3-grams are robust to minor word-order changes and typos.
    Returns bytes (required by datasketch).
    """
    text = re.sub(r"\s+", " ", text.lower().strip())
    if len(text) < ngram:
        return {text.encode("utf-8")}
    return {text[i : i + ngram].encode("utf-8") for i in range(len(text) - ngram + 1)}


def _build_minhash(text: str) -> MinHash | None:
    """Build a MinHash object from post text. Returns None for empty/short text."""
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        return None
    tokens = _tokenize(text)
    mh = MinHash(num_perm=_NUM_PERM)
    for token in tokens:
        mh.update(token)
    return mh


# ---------------------------------------------------------------------------
# In-memory LSH index
# ---------------------------------------------------------------------------

class FuzzyDedup:
    """
    In-memory MinHash LSH index for near-duplicate detection.

    Built fresh per pipeline run (not persisted — dedup state is in SQLite).
    The LSH index only needs to exist for the duration of one dedup run
    to detect cross-post similarities within that batch.

    Usage:
        dedup = FuzzyDedup(threshold=0.75)
        for record in records:
            if dedup.is_near_duplicate(record):
                skip the record
            else:
                dedup.add(record)
                process the record
    """

    def __init__(self, threshold: float = _DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._lsh = MinHashLSH(threshold=threshold, num_perm=_NUM_PERM)
        self._added: dict[str, dict] = {}  # key → record

    def _record_key(self, record: dict) -> str:
        """Stable unique key for a record within this run."""
        return record.get("job_uid") or record.get("job_url") or record.get("title", "")

    def is_near_duplicate(self, record: dict) -> bool:
        """
        Check if a record is a near-duplicate of something already in the index.

        Returns True if a similar post from the same company was already added.
        """
        text = record.get("description") or ""
        mh = _build_minhash(text)
        if mh is None:
            return False   # Can't compare — pass it through

        try:
            candidates = self._lsh.query(mh)
        except Exception:
            return False

        if not candidates:
            return False

        # Extra check: same company (reduces false positives across companies)
        company = (record.get("company") or record.get("author_name") or "").lower().strip()
        for key in candidates:
            candidate = self._added.get(key, {})
            cand_company = (
                candidate.get("company") or candidate.get("author_name") or ""
            ).lower().strip()
            if company and cand_company and company == cand_company:
                logger.debug(
                    f"[fuzzy_dedup] Near-duplicate found: "
                    f"'{record.get('title', '')[:50]}' ≈ '{candidate.get('title', '')[:50]}'"
                )
                return True

        return False

    def add(self, record: dict) -> bool:
        """
        Add a record to the LSH index.

        Returns True if successfully added, False if text is too short to hash.
        """
        text = record.get("description") or ""
        mh = _build_minhash(text)
        if mh is None:
            return False

        key = self._record_key(record)
        if not key or key in self._added:
            return False

        try:
            self._lsh.insert(key, mh)
            self._added[key] = record
            return True
        except ValueError:
            # datasketch raises ValueError if key already in index
            return False

    @property
    def size(self) -> int:
        """Number of records currently indexed."""
        return len(self._added)
