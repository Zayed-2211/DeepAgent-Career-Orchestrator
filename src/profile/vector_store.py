"""
ChromaDB vector store wrapper - Phase 5.

Provides semantic search over user profile (GitHub repos + CV projects).
Hybrid approach: keyword matching (fast) + vector similarity (semantic).
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from config.projects_config import PROFILE_INDEX_DIR
from config.settings import get_settings


class VectorStore:
    """
    Thin wrapper around ChromaDB for profile indexing.
    
    Collections:
      - projects: GitHub repos + manual projects from my_projects.json
      - cv_sections: Skills, experience, education chunks from CV
    
    Usage:
        store = VectorStore()
        store.index_projects(projects)
        results = store.search_projects("AI agent framework", top_k=3)
    """

    def __init__(self, persist_dir: Path = PROFILE_INDEX_DIR):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        
        # Use Google's embedding model (matches Gemini ecosystem)
        self._embedding_function = chromadb.utils.embedding_functions.GoogleGenerativeAiEmbeddingFunction(
            api_key=get_settings().gemini_api_key,
            model_name="models/text-embedding-004",
        )

    # -------------------------------------------------------------------------
    # Projects collection
    # -------------------------------------------------------------------------

    def index_projects(self, projects: list[dict]) -> int:
        """
        Index or re-index all projects.
        
        Args:
            projects: List of project dicts with keys:
                - name (str)
                - description (str)
                - tech_stack (list[str])
                - domains (list[str])
                - highlights (list[dict with 'text' key])
                - github_url (str | None)
        
        Returns:
            Number of projects indexed.
        """
        if not projects:
            logger.warning("[vector_store] No projects to index.")
            return 0

        collection = self._get_or_create_collection("projects")
        
        # Clear existing data
        collection.delete(where={"source": {"$ne": ""}})  # Delete all
        
        documents = []
        metadatas = []
        ids = []
        
        for idx, project in enumerate(projects):
            # Build searchable text from project
            doc_text = self._build_project_document(project)
            
            documents.append(doc_text)
            metadatas.append({
                "name": project.get("name", "Unknown"),
                "source": "project",
                "tech_stack": ", ".join(project.get("tech_stack", [])),
                "domains": ", ".join(project.get("domains", [])),
                "github_url": project.get("github_url") or "",
            })
            ids.append(f"project_{idx}")
        
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        
        logger.info(f"[vector_store] Indexed {len(projects)} projects")
        return len(projects)

    def search_projects(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Semantic search for projects matching the query.
        
        Args:
            query: Search text (job description, tech stack, etc.)
            top_k: Number of results to return
        
        Returns:
            List of dicts with keys: name, distance, metadata
        """
        collection = self._get_or_create_collection("projects")
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
            )
        except Exception as e:
            logger.error(f"[vector_store] Search failed: {e}")
            return []
        
        if not results or not results["ids"]:
            return []
        
        # Flatten results
        matches = []
        for i in range(len(results["ids"][0])):
            matches.append({
                "name": results["metadatas"][0][i].get("name", "Unknown"),
                "distance": results["distances"][0][i],
                "tech_stack": results["metadatas"][0][i].get("tech_stack", ""),
                "domains": results["metadatas"][0][i].get("domains", ""),
                "github_url": results["metadatas"][0][i].get("github_url", ""),
                "document": results["documents"][0][i],
            })
        
        return matches

    # -------------------------------------------------------------------------
    # CV sections collection (future enhancement)
    # -------------------------------------------------------------------------

    def index_cv_sections(self, sections: list[dict]) -> int:
        """
        Index CV sections for semantic search.
        
        Args:
            sections: List of dicts with keys:
                - title (str): "Experience", "Education", "Skills"
                - content (str): Section text
        
        Returns:
            Number of sections indexed.
        """
        if not sections:
            return 0

        collection = self._get_or_create_collection("cv_sections")
        collection.delete(where={"source": {"$ne": ""}})
        
        documents = []
        metadatas = []
        ids = []
        
        for idx, section in enumerate(sections):
            documents.append(section.get("content", ""))
            metadatas.append({
                "title": section.get("title", "Unknown"),
                "source": "cv",
            })
            ids.append(f"cv_{idx}")
        
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        
        logger.info(f"[vector_store] Indexed {len(sections)} CV sections")
        return len(sections)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return collection statistics."""
        stats = {}
        for name in ["projects", "cv_sections"]:
            try:
                collection = self._client.get_collection(name)
                stats[name] = collection.count()
            except Exception:
                stats[name] = 0
        return stats

    def clear_all(self) -> None:
        """Delete all collections. Use with caution."""
        for name in ["projects", "cv_sections"]:
            try:
                self._client.delete_collection(name)
                logger.info(f"[vector_store] Deleted collection: {name}")
            except Exception:
                pass

    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        try:
            return self._client.get_collection(
                name=name,
                embedding_function=self._embedding_function,
            )
        except Exception:
            return self._client.create_collection(
                name=name,
                embedding_function=self._embedding_function,
                metadata={"hnsw:space": "cosine"},  # Cosine similarity
            )

    @staticmethod
    def _build_project_document(project: dict) -> str:
        """
        Build a searchable document from a project dict.
        
        Combines name, description, tech stack, domains, and highlights
        into a single text blob for embedding.
        """
        parts = [
            f"Project: {project.get('name', 'Unknown')}",
            f"Description: {project.get('description', '')}",
        ]
        
        tech = project.get("tech_stack", [])
        if tech:
            parts.append(f"Technologies: {', '.join(tech)}")
        
        domains = project.get("domains", [])
        if domains:
            parts.append(f"Domains: {', '.join(domains)}")
        
        highlights = project.get("highlights", [])
        if highlights:
            highlight_texts = []
            for h in highlights:
                if isinstance(h, dict):
                    highlight_texts.append(h.get("text", ""))
                elif isinstance(h, str):
                    highlight_texts.append(h)
            if highlight_texts:
                parts.append("Highlights: " + " | ".join(highlight_texts))
        
        return "\n".join(parts)
