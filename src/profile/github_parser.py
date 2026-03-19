"""
GitHub repository parser - Phase 5.

Extracts project metadata from GitHub repos:
- README content
- Tech stack detection from files
- Stars, last updated, description
"""

import re
from pathlib import Path
from typing import Any

import git
from loguru import logger

from config.projects_config import load_github_profile, MAX_README_CHARS


class GitHubParser:
    """
    Parse GitHub repositories and extract project metadata.
    
    Uses GitPython to clone/pull repos locally and extract:
    - README content
    - Tech stack (from file extensions + README)
    - Description, stars, last commit
    
    Usage:
        parser = GitHubParser()
        projects = parser.parse_repos()
    """

    def __init__(self, cache_dir: Path | None = None):
        """
        Args:
            cache_dir: Where to clone repos. Defaults to data/profile/.github_cache/
        """
        from config.settings import DATA_DIR
        
        self.config = load_github_profile()
        self.github_url = self.config.get("github_url", "")
        self.include_repos = self.config.get("include_repos", [])
        self.exclude_repos = self.config.get("exclude_repos", [])
        
        self.cache_dir = cache_dir or (DATA_DIR / "profile" / ".github_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def parse_repos(self) -> list[dict]:
        """
        Parse all repos according to include/exclude rules.
        
        Returns:
            List of project dicts with keys:
                - name
                - description
                - tech_stack
                - domains
                - highlights (empty for GitHub - filled by LLM later)
                - github_url
                - stars
                - last_updated
        """
        if not self.github_url:
            logger.warning("[github_parser] No GitHub URL configured")
            return []

        username = self._extract_username(self.github_url)
        if not username:
            logger.error(f"[github_parser] Invalid GitHub URL: {self.github_url}")
            return []

        # Get repo list from GitHub API
        repos = self._fetch_repo_list(username)
        
        if not repos:
            logger.warning(f"[github_parser] No repos found for {username}")
            return []

        # Apply include/exclude filters
        filtered = self._apply_filters(repos)
        
        logger.info(f"[github_parser] Processing {len(filtered)} repos...")
        
        projects = []
        for repo_data in filtered:
            try:
                project = self._parse_single_repo(repo_data)
                if project:
                    projects.append(project)
            except Exception as e:
                logger.error(f"[github_parser] Failed to parse {repo_data['name']}: {e}")
        
        logger.info(f"[github_parser] Parsed {len(projects)} projects")
        return projects

    def _fetch_repo_list(self, username: str) -> list[dict]:
        """Fetch repo list from GitHub API."""
        import httpx
        
        url = f"https://api.github.com/users/{username}/repos"
        params = {"per_page": 100, "sort": "updated"}
        
        try:
            response = httpx.get(url, params=params, timeout=30)
            response.raise_for_status()
            repos = response.json()
            logger.info(f"[github_parser] Found {len(repos)} repos for {username}")
            return repos
        except Exception as e:
            logger.error(f"[github_parser] GitHub API error: {e}")
            return []

    def _apply_filters(self, repos: list[dict]) -> list[dict]:
        """Apply include/exclude filters to repo list."""
        if self.include_repos:
            # Whitelist mode: only include specified repos
            filtered = [r for r in repos if r["name"] in self.include_repos]
            logger.info(f"[github_parser] Include filter: {len(repos)} → {len(filtered)}")
            return filtered
        
        if self.exclude_repos:
            # Blacklist mode: exclude specified repos
            filtered = [r for r in repos if r["name"] not in self.exclude_repos]
            logger.info(f"[github_parser] Exclude filter: {len(repos)} → {len(filtered)}")
            return filtered
        
        # No filters: return all non-forked repos
        filtered = [r for r in repos if not r.get("fork", False)]
        logger.info(f"[github_parser] Fork filter: {len(repos)} → {len(filtered)}")
        return filtered

    def _parse_single_repo(self, repo_data: dict) -> dict | None:
        """Parse a single GitHub repo."""
        name = repo_data["name"]
        clone_url = repo_data["clone_url"]
        
        # Clone or pull repo
        repo_path = self.cache_dir / name
        try:
            if repo_path.exists():
                logger.debug(f"[github_parser] Pulling {name}...")
                repo = git.Repo(repo_path)
                repo.remotes.origin.pull()
            else:
                logger.debug(f"[github_parser] Cloning {name}...")
                repo = git.Repo.clone_from(clone_url, repo_path, depth=1)
        except Exception as e:
            logger.warning(f"[github_parser] Git operation failed for {name}: {e}")
            return None

        # Extract README
        readme_content = self._read_readme(repo_path)
        
        # Detect tech stack
        tech_stack = self._detect_tech_stack(repo_path, readme_content)
        
        # Infer domains from description + README
        domains = self._infer_domains(repo_data.get("description", ""), readme_content)
        
        return {
            "name": name,
            "description": repo_data.get("description") or f"GitHub repository: {name}",
            "tech_stack": tech_stack,
            "domains": domains,
            "highlights": [],  # Filled later by LLM or manual entry
            "github_url": repo_data["html_url"],
            "stars": repo_data.get("stargazers_count", 0),
            "last_updated": repo_data.get("updated_at", ""),
        }

    def _read_readme(self, repo_path: Path) -> str:
        """Find and read README file."""
        for pattern in ["README.md", "README.MD", "readme.md", "README", "README.txt"]:
            readme_path = repo_path / pattern
            if readme_path.exists():
                try:
                    content = readme_path.read_text(encoding="utf-8", errors="ignore")
                    # Truncate to MAX_README_CHARS
                    if len(content) > MAX_README_CHARS:
                        content = content[:MAX_README_CHARS] + "..."
                    return content
                except Exception:
                    pass
        return ""

    def _detect_tech_stack(self, repo_path: Path, readme: str) -> list[str]:
        """Detect tech stack from file extensions and README."""
        tech = set()
        
        # File extension mapping
        ext_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "React",
            ".jsx": "React",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".cs": "C#",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".sql": "SQL",
            ".sh": "Bash",
        }
        
        # Scan files
        for file in repo_path.rglob("*"):
            if file.is_file() and file.suffix in ext_map:
                tech.add(ext_map[file.suffix])
        
        # Check for framework-specific files
        if (repo_path / "package.json").exists():
            tech.add("Node.js")
        if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
            tech.add("Python")
        if (repo_path / "Cargo.toml").exists():
            tech.add("Rust")
        if (repo_path / "go.mod").exists():
            tech.add("Go")
        if (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists():
            tech.add("Java")
        
        # Extract from README (look for badges, headers)
        if readme:
            readme_lower = readme.lower()
            framework_patterns = {
                "langgraph": "LangGraph",
                "langchain": "LangChain",
                "fastapi": "FastAPI",
                "django": "Django",
                "flask": "Flask",
                "react": "React",
                "vue": "Vue.js",
                "angular": "Angular",
                "tensorflow": "TensorFlow",
                "pytorch": "PyTorch",
                "docker": "Docker",
                "kubernetes": "Kubernetes",
                "postgresql": "PostgreSQL",
                "mongodb": "MongoDB",
                "redis": "Redis",
            }
            
            for pattern, name in framework_patterns.items():
                if pattern in readme_lower:
                    tech.add(name)
        
        return sorted(list(tech))

    def _infer_domains(self, description: str, readme: str) -> list[str]:
        """Infer project domains from description and README."""
        text = (description + " " + readme).lower()
        domains = set()
        
        domain_keywords = {
            "AI": ["ai", "artificial intelligence", "machine learning", "deep learning", "llm", "gpt"],
            "NLP": ["nlp", "natural language", "text processing", "sentiment"],
            "Computer Vision": ["computer vision", "image processing", "object detection", "yolo"],
            "Web": ["web", "website", "web app", "frontend", "backend"],
            "Backend": ["api", "backend", "server", "microservice"],
            "RAG": ["rag", "retrieval", "vector", "embedding"],
            "Chatbot": ["chatbot", "chat", "conversational"],
            "Automation": ["automation", "bot", "scraper"],
            "Data": ["data", "analytics", "visualization"],
        }
        
        for domain, keywords in domain_keywords.items():
            if any(kw in text for kw in keywords):
                domains.add(domain)
        
        return sorted(list(domains))

    @staticmethod
    def _extract_username(github_url: str) -> str | None:
        """Extract username from GitHub URL."""
        match = re.search(r"github\.com/([^/]+)", github_url)
        return match.group(1) if match else None
