"""
LaTeX rendering engine with Jinja2 templates and PDF compilation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from config.settings import CONFIG_DIR, DATA_DIR


class LaTeXEngine:
    """
    Jinja2 → LaTeX → PDF pipeline.
    
    Uses custom delimiters to avoid conflicts with LaTeX syntax:
    - \VAR{variable} instead of {{ variable }}
    - \BLOCK{for x in y} instead of {% for x in y %}
    """
    
    def __init__(self, config_path: Path | None = None):
        """Initialize LaTeX engine with config."""
        self.config = self._load_config(config_path)
        self.templates_dir = Path(__file__).parent / "templates"
        self.templates_dir.mkdir(exist_ok=True)
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(),
            block_start_string=r"\BLOCK{",
            block_end_string="}",
            variable_start_string=r"\VAR{",
            variable_end_string="}",
            comment_start_string=r"\#{",
            comment_end_string="}",
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        self._check_pdflatex()
    
    def _load_config(self, config_path: Path | None) -> dict:
        """Load generators config."""
        if config_path is None:
            config_path = CONFIG_DIR / "generators.json"
        
        if not config_path.exists():
            logger.warning(f"[latex] Config not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        return config
    
    def _default_config(self) -> dict:
        """Default config if file not found."""
        return {
            "latex_compilation": {
                "enabled": True,
                "pdflatex_path": "pdflatex",
                "compile_timeout": 30,
                "keep_tex_files": True,
                "cleanup_aux_files": True,
            },
            "dev_mode": {
                "skip_pdf_compilation": False,
            },
        }
    
    def _check_pdflatex(self) -> None:
        """Check if pdflatex is installed and accessible."""
        pdflatex_path = self.config.get("latex_compilation", {}).get("pdflatex_path", "pdflatex")
        
        if shutil.which(pdflatex_path) is None:
            logger.warning(
                f"[latex] pdflatex not found in PATH. PDF compilation will fail. "
                f"Install MiKTeX (Windows) or TeX Live (Linux/Mac)."
            )
    
    def render_template(
        self,
        template_name: str,
        context: dict,
        output_path: Path,
    ) -> Path:
        """
        Render a Jinja2 LaTeX template with context data.
        
        Args:
            template_name: Name of template file (e.g., 'cv_template.tex')
            context: Dictionary of variables for template
            output_path: Where to save rendered .tex file
        
        Returns:
            Path to rendered .tex file
        """
        try:
            template = self.env.get_template(template_name)
        except Exception as exc:
            logger.error(f"[latex] Template not found: {template_name} - {exc}")
            raise
        
        try:
            rendered = template.render(**context)
        except Exception as exc:
            logger.error(f"[latex] Template rendering failed: {exc}")
            raise
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        
        logger.info(f"[latex] Rendered template → {output_path}")
        return output_path
    
    def compile_to_pdf(
        self,
        tex_path: Path,
        output_dir: Path | None = None,
    ) -> Path | None:
        """
        Compile .tex file to PDF using pdflatex.
        
        Args:
            tex_path: Path to .tex file
            output_dir: Directory for output (default: same as .tex file)
        
        Returns:
            Path to compiled .pdf file, or None if compilation failed
        """
        if not self.config.get("latex_compilation", {}).get("enabled", True):
            logger.info("[latex] PDF compilation disabled in config")
            return None
        
        if self.config.get("dev_mode", {}).get("skip_pdf_compilation", False):
            logger.info("[latex] Skipping PDF compilation (dev mode)")
            return None
        
        if not tex_path.exists():
            logger.error(f"[latex] .tex file not found: {tex_path}")
            return None
        
        output_dir = output_dir or tex_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pdflatex_path = self.config.get("latex_compilation", {}).get("pdflatex_path", "pdflatex")
        timeout = self.config.get("latex_compilation", {}).get("compile_timeout", 30)
        
        cmd = [
            pdflatex_path,
            "-interaction=nonstopmode",
            "-output-directory", str(output_dir),
            str(tex_path),
        ]
        
        try:
            logger.info(f"[latex] Compiling {tex_path.name} to PDF...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(output_dir),
            )
            
            pdf_path = output_dir / tex_path.with_suffix(".pdf").name
            
            if result.returncode != 0:
                logger.error(f"[latex] Compilation failed:\n{result.stdout}\n{result.stderr}")
                return None
            
            if not pdf_path.exists():
                logger.error(f"[latex] PDF not created: {pdf_path}")
                return None
            
            logger.info(f"[latex] PDF compiled → {pdf_path}")
            
            if self.config.get("latex_compilation", {}).get("cleanup_aux_files", True):
                self._cleanup_aux_files(output_dir, tex_path.stem)
            
            return pdf_path
        
        except subprocess.TimeoutExpired:
            logger.error(f"[latex] Compilation timeout after {timeout}s")
            return None
        except Exception as exc:
            logger.error(f"[latex] Compilation error: {exc}")
            return None
    
    def _cleanup_aux_files(self, output_dir: Path, base_name: str) -> None:
        """Remove auxiliary LaTeX files (.aux, .log, .out, etc.)."""
        aux_extensions = [".aux", ".log", ".out", ".toc", ".lof", ".lot"]
        
        for ext in aux_extensions:
            aux_file = output_dir / f"{base_name}{ext}"
            if aux_file.exists():
                try:
                    aux_file.unlink()
                    logger.debug(f"[latex] Cleaned up {aux_file.name}")
                except Exception as exc:
                    logger.warning(f"[latex] Could not delete {aux_file.name}: {exc}")
    
    def render_and_compile(
        self,
        template_name: str,
        context: dict,
        output_dir: Path,
        base_name: str = "document",
    ) -> dict[str, Path | None]:
        """
        Render template and compile to PDF in one step.
        
        Args:
            template_name: Template file name
            context: Template variables
            output_dir: Output directory
            base_name: Base name for output files (without extension)
        
        Returns:
            Dictionary with 'tex' and 'pdf' paths
        """
        tex_path = output_dir / f"{base_name}.tex"
        
        self.render_template(template_name, context, tex_path)
        
        pdf_path = self.compile_to_pdf(tex_path, output_dir)
        
        if not self.config.get("latex_compilation", {}).get("keep_tex_files", True):
            try:
                tex_path.unlink()
                logger.debug(f"[latex] Removed .tex file: {tex_path}")
            except Exception as exc:
                logger.warning(f"[latex] Could not delete .tex file: {exc}")
        
        return {
            "tex": tex_path if tex_path.exists() else None,
            "pdf": pdf_path,
        }
    
    @staticmethod
    def sanitize_latex(text: str) -> str:
        """
        Escape special LaTeX characters in text.
        
        Args:
            text: Raw text that may contain LaTeX special chars
        
        Returns:
            Escaped text safe for LaTeX
        """
        if not text:
            return ""
        
        replacements = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
            "\\": r"\textbackslash{}",
        }
        
        for char, escaped in replacements.items():
            text = text.replace(char, escaped)
        
        return text
