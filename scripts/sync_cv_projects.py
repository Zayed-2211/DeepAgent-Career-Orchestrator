"""
Sync non-GitHub projects from your LaTeX CV → data/profile/my_projects.json

Usage:
    python scripts/sync_cv_projects.py           # Normal run
    python scripts/sync_cv_projects.py --dry-run  # Preview only (no file written)
    python scripts/sync_cv_projects.py --force    # Add even if name looks similar

What it does:
  1. Reads data/profile/my_cv.tex
  2. Uses Gemini to extract all projects from the Projects section
  3. Skips projects that link to a REAL GitHub repo (the GitHub indexer handles those)
     A real repo URL has the form: github.com/username/repo-name (2+ path segments)
     A profile/fake URL like github.com/username/ does NOT count as a real repo
  4. Skips projects whose name closely matches one already in my_projects.json
  5. Appends new non-GitHub projects to my_projects.json
     (profile/fake GitHub URLs are set to null in the output)

Run this whenever you update your CV and want the changes reflected automatically.
"""

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

# ---------------------------------------------------------------------------
# Ensure project root is on the path so local imports work
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.projects_config import CV_FILE, MANUAL_PROJECTS_FILE
from src.profile.cv_extractor import extract_projects_from_cv
from src.profile.schemas import ParsedCVProject


# ---------------------------------------------------------------------------
# Duplicate detection threshold
# ---------------------------------------------------------------------------
_SIMILARITY_THRESHOLD = 0.85  # SequenceMatcher ratio — 0.85 = very close name match


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_real_repo_url(url: str | None) -> bool:
    """
    Return True only if the URL points to a specific GitHub repository.

    A real repo URL has the pattern: github.com/{username}/{repo-name}
    where {repo-name} is a non-empty string (2+ path segments after the domain).

    Examples:
      https://github.com/Zayed-2211/Secure-Agentic-CRAG  → True  (real repo)
      https://github.com/Zayed-2211/                     → False (profile root)
      https://github.com/Zayed-2211                      → False (profile root)
      None                                               → False (no URL at all)
    """
    if not url:
        return False
    parsed = urlparse(url)
    if "github.com" not in (parsed.netloc or ""):
        return False
    # Strip leading/trailing slashes and split; need at least username + repo-name
    segments = [s for s in parsed.path.strip("/").split("/") if s]
    return len(segments) >= 2

def _is_placeholder_entry(entry: dict) -> bool:
    """Return True if this JSON entry is a comment/instructions block, not a real project."""
    return "_comment" in entry or "_instructions" in entry


def _load_existing_projects(path: Path) -> tuple[list[dict], list[str]]:
    """
    Load my_projects.json. Returns:
      - raw_entries : the full list including the metadata entry at index 0
      - existing_names : lowercased project names of real (non-metadata) entries
    """
    if not path.exists():
        return [], []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"Could not read {path}: {exc}")
        return [], []

    if not isinstance(raw, list):
        logger.error(f"{path} is not a JSON array — cannot parse.")
        return [], []

    existing_names = [
        entry["name"].lower()
        for entry in raw
        if not _is_placeholder_entry(entry) and isinstance(entry.get("name"), str)
    ]

    return raw, existing_names


def _names_are_similar(a: str, b: str, threshold: float = _SIMILARITY_THRESHOLD) -> bool:
    """Return True if two project names are close enough to consider duplicates."""
    ratio = SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
    return ratio >= threshold


def _is_duplicate(name: str, existing_names: list[str]) -> bool:
    return any(_names_are_similar(name, existing) for existing in existing_names)


def _project_to_dict(p: ParsedCVProject) -> dict:
    """
    Convert a ParsedCVProject to the JSON dict format used in my_projects.json.
    If the project's github_url is not a real repo URL (e.g. a profile root),
    it is written as null so it doesn't pollute the projects file.
    """
    return {
        "name": p.name,
        "description": p.description,
        "tech_stack": p.tech_stack,
        "domains": p.domains,
        "highlights": p.highlights,
        # Only write a github_url if it actually points to a specific repo
        "github_url": p.github_url if is_real_repo_url(p.github_url) else None,
        "period": p.period,
    }


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def sync_cv_projects(dry_run: bool = False, force: bool = False) -> None:
    # --- 1. Read the CV ---
    if not CV_FILE.exists():
        logger.error(f"CV file not found: {CV_FILE}")
        logger.info("Run: copy data\\profile.example\\my_cv.tex data\\profile\\my_cv.tex")
        sys.exit(1)

    cv_content = CV_FILE.read_text(encoding="utf-8").strip()

    # Guard: if the file only contains the placeholder comment header (no real LaTeX CV),
    # the first non-comment content would be very short.
    real_content = "\n".join(
        line for line in cv_content.splitlines()
        if not line.strip().startswith("%")
    ).strip()

    if len(real_content) < 100:
        logger.warning(
            "CV file appears to contain only placeholder comments and no real content.\n"
            "Paste your LaTeX CV into data/profile/my_cv.tex and re-run."
        )
        sys.exit(0)

    # --- 2. Load existing projects ---
    raw_entries, existing_names = _load_existing_projects(MANUAL_PROJECTS_FILE)

    logger.info(
        f"Loaded {MANUAL_PROJECTS_FILE.name} — "
        f"{len(existing_names)} existing project(s)."
    )

    # --- 3. Extract projects from CV ---
    logger.info("Extracting projects from CV using Gemini...")
    extracted: list[ParsedCVProject] = extract_projects_from_cv(cv_content)

    if not extracted:
        logger.info("No projects found in the CV's Projects section. Nothing to do.")
        return

    logger.info(f"Gemini found {len(extracted)} project(s) in the CV.")

    # --- 4. Filter ---
    to_add: list[ParsedCVProject] = []
    skipped_github: list[str] = []
    skipped_duplicate: list[str] = []

    for project in extracted:
        # Skip only if the URL points to a REAL specific repo (not a profile root or fake link)
        if is_real_repo_url(project.github_url) and not force:
            skipped_github.append(project.name)
            continue

        if not force and _is_duplicate(project.name, existing_names):
            skipped_duplicate.append(project.name)
            continue

        to_add.append(project)

    # --- 5. Report ---
    print("\n" + "─" * 60)
    print(f"  CV Projects Sync Summary")
    print("─" * 60)
    print(f"  Extracted from CV        : {len(extracted)}")
    print(f"  Skipped (real repo on GitHub): {len(skipped_github)}")
    if skipped_github:
        for name in skipped_github:
            print(f"    • {name}")
    print(f"  Skipped (already in JSON): {len(skipped_duplicate)}")
    if skipped_duplicate:
        for name in skipped_duplicate:
            print(f"    • {name}")
    print(f"  To be added              : {len(to_add)}")
    if to_add:
        for p in to_add:
            print(f"    • {p.name}")
    print("─" * 60)

    if not to_add:
        print("  ✅ Nothing new to add.")
        print("─" * 60 + "\n")
        return

    if dry_run:
        print("  🔍 Dry run — no changes written.")
        print("─" * 60 + "\n")
        return

    # --- 6. Write ---
    # If the JSON file doesn't exist yet, create it with the standard metadata header
    if not raw_entries:
        raw_entries = [
            {
                "_comment": "=== MANUAL PROJECTS FILE ===",
                "_instructions": [
                    "Add any project here that is NOT on GitHub (or that you want to describe manually).",
                    "Projects with a GitHub URL will be handled by the GitHub indexer automatically.",
                    "Fields: name, description, tech_stack, domains, highlights, github_url, period.",
                ]
            }
        ]

    new_names = []
    for p in to_add:
        raw_entries.append(_project_to_dict(p))
        new_names.append(p.name)

    MANUAL_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_PROJECTS_FILE.write_text(
        json.dumps(raw_entries, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"  ✅ Added {len(to_add)} project(s) to {MANUAL_PROJECTS_FILE}:")
    for name in new_names:
        print(f"    • {name}")
    print("─" * 60 + "\n")
    logger.info(f"my_projects.json updated — {len(to_add)} project(s) added.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync non-GitHub projects from your LaTeX CV to my_projects.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/sync_cv_projects.py            # Normal run
  python scripts/sync_cv_projects.py --dry-run  # Preview only, no changes
  python scripts/sync_cv_projects.py --force    # Add even if names look similar
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be added without writing anything",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Add projects even if they appear to already exist (bypasses duplicate check and GitHub filter)",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    sync_cv_projects(dry_run=args.dry_run, force=args.force)
