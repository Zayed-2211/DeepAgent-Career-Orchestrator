"""
EXAMPLE — data/profile/my_github.py

Copy this to data/profile/my_github.py and fill in your details.
data/profile/ is gitignored — your settings stay private.

──────────────────────────────────────────────
HOW REPO SELECTION WORKS (priority order)
──────────────────────────────────────────────

  1. INCLUDE_REPOS   → If non-empty: ONLY these repos are used.
  2. EXCLUDE_REPOS   → If INCLUDE is empty: all repos EXCEPT these.
  3. Both empty      → Use ALL public repos (agent picks best per job).
"""

# Your GitHub profile URL (public API — no token needed).
GITHUB_URL: str = "https://github.com/YOUR_USERNAME"

# Whitelist — only these repos will be indexed (exact repo names).
INCLUDE_REPOS: list[str] = [
    # "my-rag-chatbot",
    # "arabic-nlp-api",
]

# Blacklist — skip these repos (used only when INCLUDE_REPOS is empty).
EXCLUDE_REPOS: list[str] = [
    # "old-uni-assignments",
    # "test-repo",
]
