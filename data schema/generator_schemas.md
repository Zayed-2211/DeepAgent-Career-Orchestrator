# Generator Schemas

> Source: `src/generators/schemas.py`

## TailoredCV

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `professional_summary` | `str` | max 500 chars | 2-3 sentence summary tailored to the job |
| `experience` | `list[TailoredExperience]` | max 3 items | Work experience entries (most recent first) |
| `projects` | `list[TailoredProject]` | max 3 items | Top matched projects tailored to job requirements |
| `technical_skills` | `list[str]` | max 15 items | Technical skills relevant to the job |
| `soft_skills` | `list[str]` | max 5 items | Soft skills from job description |

### TailoredExperience

| Field | Type | Description |
|-------|------|-------------|
| `company` | `str` | Company name |
| `position` | `str` | Job title |
| `period` | `str` | Time period |
| `bullets` | `list[str]` | Max 5 tailored achievement bullets |

### TailoredProject

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Project name |
| `tech_stack` | `list[str]` | Technologies used |
| `bullets` | `list[str]` | Max 3 tailored bullets |
| `github_url` | `str \| None` | GitHub repo URL |

## TailoredCoverLetter

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `opening` | `str` | max 400 chars | Opening paragraph |
| `body_paragraph_1` | `str` | max 600 chars | Relevant experience/projects |
| `body_paragraph_2` | `str` | max 600 chars | Why you're a great fit |
| `closing` | `str` | max 300 chars | Call to action and thanks |
| `tone` | `str` | default "professional" | Overall tone |

## CoverLetterSection (Unused)

> ⚠️ Defined but never referenced by any code. Candidate for removal.
