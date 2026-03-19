"""
Profile Indexer - Phase 5.

Builds the ChromaDB vector index from:
  1. GitHub repositories (cloned and parsed)
  2. Manual projects from my_projects.json
  
Usage:
    python scripts/run_indexer.py               # Index all sources
    python scripts/run_indexer.py --github-only # Only GitHub repos
    python scripts/run_indexer.py --rebuild     # Clear index and rebuild
"""

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.projects_config import MANUAL_PROJECTS_FILE
from src.profile.github_parser import GitHubParser
from src.profile.vector_store import VectorStore


def index_all_projects(rebuild: bool = False, github_only: bool = False) -> None:
    """
    Index all projects into ChromaDB.
    
    Args:
        rebuild: Clear existing index before indexing
        github_only: Only index GitHub repos, skip my_projects.json
    """
    store = VectorStore()
    
    # Clear if rebuild requested
    if rebuild:
        logger.info("[indexer] Clearing existing index...")
        store.clear_all()
    
    all_projects = []
    
    # --- Index GitHub repos ---
    logger.info("[indexer] Parsing GitHub repositories...")
    parser = GitHubParser()
    github_projects = parser.parse_repos()
    
    if github_projects:
        all_projects.extend(github_projects)
        logger.info(f"[indexer] Found {len(github_projects)} GitHub repos")
    else:
        logger.warning("[indexer] No GitHub repos found. Check data/profile/my_github.py")
    
    # --- Index manual projects ---
    if not github_only:
        logger.info("[indexer] Loading manual projects from my_projects.json...")
        manual_projects = _load_manual_projects()
        
        if manual_projects:
            all_projects.extend(manual_projects)
            logger.info(f"[indexer] Found {len(manual_projects)} manual projects")
    
    # --- Index into ChromaDB ---
    if not all_projects:
        logger.error("[indexer] No projects to index!")
        return
    
    logger.info(f"[indexer] Indexing {len(all_projects)} total projects into ChromaDB...")
    count = store.index_projects(all_projects)
    
    # Show stats
    stats = store.get_stats()
    logger.info("[indexer] ✅ Indexing complete!")
    logger.info(f"[indexer] Collections: {stats}")
    
    print("\n" + "─" * 60)
    print("  Profile Indexing Summary")
    print("─" * 60)
    print(f"  GitHub repos         : {len(github_projects)}")
    if not github_only:
        print(f"  Manual projects      : {len(manual_projects)}")
    print(f"  Total indexed        : {count}")
    print(f"  ChromaDB collections : {stats}")
    print("─" * 60 + "\n")


def _load_manual_projects() -> list[dict]:
    """Load projects from my_projects.json."""
    if not MANUAL_PROJECTS_FILE.exists():
        logger.warning(f"[indexer] {MANUAL_PROJECTS_FILE} not found")
        return []
    
    try:
        raw = json.loads(MANUAL_PROJECTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"[indexer] Failed to read {MANUAL_PROJECTS_FILE}: {e}")
        return []
    
    if not isinstance(raw, list):
        return []
    
    # Filter out metadata entries
    projects = [
        entry for entry in raw
        if isinstance(entry, dict)
        and "name" in entry
        and "_comment" not in entry
        and "_instructions" not in entry
    ]
    
    return projects


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Index user profile (GitHub + manual projects) into ChromaDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_indexer.py              # Index all sources
  python scripts/run_indexer.py --rebuild    # Clear and rebuild index
  python scripts/run_indexer.py --github-only # Only GitHub repos
        """,
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear existing index before indexing",
    )
    parser.add_argument(
        "--github-only",
        action="store_true",
        help="Only index GitHub repos (skip my_projects.json)",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    index_all_projects(rebuild=args.rebuild, github_only=args.github_only)
