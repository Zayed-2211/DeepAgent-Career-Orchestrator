# AgentState — LangGraph Pipeline State

> Source: `src/agent/state.py` | Schema Version: `2`

The `AgentState` TypedDict is the **single shared state object** that flows between all 11 LangGraph nodes.

## Fields

| Field | Type | Set By | Read By | Description |
|-------|------|--------|---------|-------------|
| `schema_version` | `int` | `initial_state()` | `build_pipeline_graph` | Version guard — must equal `CURRENT_SCHEMA_VERSION (2)` or graph refuses to run |
| `run_id` | `str` | `initial_state()` | Intelligence artifacts | UUID for the current run |
| `mode` | `str` | `initial_state()` | `loop_controller_node` | `"pipeline"` or `"single_job"` |
| `raw_records` | `list[dict]` | `scout_node` | `dedup_node` | Raw scraped records from all platforms |
| `job_queue` | `list[dict]` | `dedup_node`, or `run_file()` | `loop_controller_node` | Queue of clean records to process |
| `current_job` | `dict \| None` | `loop_controller_node` | All per-job nodes | The record currently being processed |
| `job_uid` | `str \| None` | `intake_node` | `dispatch_node`, `research_node`, `generator_node` | Unique ID for the current job |
| `matched_projects` | `list[dict]` | `matching_node` | `planning_node`, `review_node`, `dispatch_node`, `generator_node` | Top-K matched projects with `_match_score` |
| `match_score` | `float` | `matching_node` | `planning_node`, `review_node`, `dispatch_node` | Overall match score (weighted avg) |
| `todo_list` | `list[str]` | `planning_node` | `review_node`, `dispatch_node` | In-memory task list with ✓/⬜ prefixes |
| `human_decision` | `str` | `review_node` | `dispatch_node` | `"approve"` or `"reject"` (currently always `"approve"`) |
| `routing` | `str` | `review_node`, `dispatch_node` | Graph conditional edges | Controls graph flow: `"approve"`, `"loop"`, `"generate"`, `"done"` |
| `generated_docs` | `dict[str, str]` | `dispatch_node`, `generator_node` | Post-run consumers | Paths to generated outputs (dispatch.json, CV, cover letter) |
| `company_research` | `dict \| None` | `research_node` | `generator_node` | Company research data (Glassdoor, LinkedIn) |
| `pipeline_stats` | `dict` | `loop_controller_node`, `dispatch_node` | `run_agent.py` | Running totals: `total`, `approved`, `rejected`, `skipped`, `errors` |
| `error` | `str \| None` | Any node on failure | Graph error handling | Error message if a node fails |

## Initial State Builders

- **`pipeline_initial_state()`** — For `--pipeline` mode. Sets `mode="pipeline"`, empty `raw_records`.
- **`initial_state(raw_record=None)`** — For `--job-file` mode. Optionally pre-populates `current_job` and `job_queue`.

## Version Guard

If `state["schema_version"] != CURRENT_SCHEMA_VERSION`, the graph aborts with an error asking the user to clear checkpoints. Bump the version when adding/removing any AgentState field.
