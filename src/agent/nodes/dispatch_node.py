"""
Dispatch Node — Phase 6.

Routes the approved job to the next phase (CV generation, research).
On rejection, archives the job with a reason.

For now this acts as the handshake to Phases 7 and 8:
  - Approved → writes `data/outputs/{job_uid}/dispatch.json`
              (Phase 7 consumes this to generate tailored CV)
  - Rejected  → writes `data/outputs/{job_uid}/archived.json`

State in:  current_job, matched_projects, match_score, human_decision, todo_list
State out: generated_docs (paths to created JSON files), todo_list (updated)
"""

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from config.settings import DATA_DIR
from src.agent.state import AgentState
from src.agent.tools.disk_tool import write_json
from src.agent.tools.todo_tool import mark_done


# Root output folder — one sub-folder per job_uid
_OUTPUTS_DIR = DATA_DIR / "outputs"


def dispatch_node(state: AgentState) -> AgentState:
    """
    Route the job based on the human's decision.

    Approved jobs: write a dispatch manifest for Phase 7.
    Rejected jobs: archive the record with a timestamp.

    State in:  current_job, matched_projects, match_score, human_decision, todo_list
    State out: generated_docs, todo_list (updated), routing
    """
    record = state.get("current_job") or {}
    job_uid = state.get("job_uid") or record.get("job_uid") or "unknown"
    decision = state.get("human_decision", "reject")
    matched = state.get("matched_projects") or []
    score = state.get("match_score", 0.0)
    todo = list(state.get("todo_list") or [])
    now = datetime.now(timezone.utc).isoformat()

    # Create the output directory for this job
    safe_uid = job_uid.replace(":", "_").replace("/", "_")[:80]
    job_dir = _OUTPUTS_DIR / safe_uid
    job_dir.mkdir(parents=True, exist_ok=True)

    generated_docs: dict[str, str] = {}

    # -------------------------------------------------------------------------
    # APPROVED — write dispatch manifest for Phase 7 + 8
    # -------------------------------------------------------------------------
    if decision == "approve":
        scout = record.get("scout") or {}
        intel = record.get("intelligence") or {}

        dispatch_data = {
            "job_uid": job_uid,
            "dispatched_at": now,
            "status": "approved",
            "job": {
                "title": record.get("raw_title") or record.get("title"),
                "company": scout.get("company_name"),
                "city": scout.get("city"),
                "country": scout.get("country"),
                "is_remote": scout.get("is_remote"),
                "salary_min": scout.get("salary_min"),
                "salary_max": scout.get("salary_max"),
                "currency": scout.get("currency"),
                "contact_info": scout.get("contact_info"),
                "source_url": record.get("job_url") or record.get("source_url"),
                "tech_stack": intel.get("tech_stack") or [],
                "must_haves": intel.get("must_haves") or [],
                "nice_to_haves": intel.get("nice_to_haves") or [],
                "role_summary": intel.get("role_summary"),
                "seniority": scout.get("seniority"),
                "job_type": scout.get("job_type"),
                "extra_notes": scout.get("extra_notes"),
            },
            "matched_projects": [
                {
                    "name": p.get("name"),
                    "match_score": p.get("_match_score"),
                    "tech_stack": p.get("tech_stack"),
                    "highlights": p.get("highlights"),
                    "github_url": p.get("github_url"),
                    "period": p.get("period"),
                }
                for p in matched[:3]
            ],
            "overall_match_score": score,
            "todo_list": todo,
            # Placeholders for Phase 7 to fill in
            "outputs": {
                "cv_tex": str(job_dir / "cv_tailored.tex"),
                "cv_pdf": str(job_dir / "cv_tailored.pdf"),
                "cover_letter_tex": str(job_dir / "cover_letter.tex"),
                "research_pack": str(job_dir / "research_pack.json"),
            },
        }

        dispatch_path = job_dir / "dispatch.json"
        write_json(dispatch_path, dispatch_data)
        generated_docs["dispatch"] = str(dispatch_path)

        todo = mark_done(todo, "Human review")
        logger.info(f"[dispatch] ✅ APPROVED → {dispatch_path}")

    # -------------------------------------------------------------------------
    # REJECTED — archive with metadata
    # -------------------------------------------------------------------------
    else:
        archive_data = {
            "job_uid": job_uid,
            "archived_at": now,
            "status": "rejected",
            "title": record.get("raw_title") or record.get("title"),
            "company": (record.get("scout") or {}).get("company_name"),
            "match_score": score,
            "source_url": record.get("job_url") or record.get("source_url"),
        }

        archive_path = job_dir / "archived.json"
        write_json(archive_path, archive_data)
        generated_docs["archived"] = str(archive_path)

        logger.info(f"[dispatch] ❌ REJECTED → archived at {archive_path}")

    return {
        **state,
        "generated_docs": generated_docs,
        "todo_list": todo,
    }
