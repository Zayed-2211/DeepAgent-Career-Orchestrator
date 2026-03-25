# Data Schema Documentation

This folder is the **single source of truth** for all data fields, parameters, API variables, and their connections used in the DeepAgent Career Orchestrator.

## Contents

| File | Scope |
|------|-------|
| [agent_state.md](agent_state.md) | `AgentState` TypedDict — all fields flowing through the LangGraph pipeline |
| [intelligence_schemas.md](intelligence_schemas.md) | `ScoutData`, `IntelligenceData`, `ParsedJob`, `GeminiJobResponse` Pydantic models |
| [generator_schemas.md](generator_schemas.md) | `TailoredCV`, `TailoredCoverLetter` Pydantic models |
| [database_tables.md](database_tables.md) | SQLite tables: `seen_post_ids`, `seen_fingerprints`, `raw_jobs`, `processed_jobs`, `db_meta` |
| [config_variables.md](config_variables.md) | All config files, env vars, and settings |
| [field_flow_map.md](field_flow_map.md) | How fields flow between nodes and where inconsistencies exist |

## How To Use

1. **Before writing any code**, check this folder for the canonical field names.
2. **After adding a new field**, update the relevant doc + `field_flow_map.md`.
3. **When debugging**, cross-reference `field_flow_map.md` to trace data through the pipeline.
