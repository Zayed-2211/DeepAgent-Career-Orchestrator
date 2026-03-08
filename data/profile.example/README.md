# Profile Setup — `data/profile/`

This folder is a ready-to-use starter for `data/profile/`.
`data/profile/` is gitignored — your personal data stays private.

## One-step setup

```bash
# Rename this folder → profile/  (files inside are already named correctly)
mv data/profile.example data/profile        # macOS / Linux
Rename-Item data\profile.example data\profile  # Windows PowerShell
```

Then edit the three files inside:

| File | What to change |
|------|---------------|
| `my_cv.tex` | Paste your full LaTeX CV (or leave empty to use `templates/cv_template.tex`) |
| `my_github.py` | Set `GITHUB_URL` and optionally fill `INCLUDE_REPOS` or `EXCLUDE_REPOS` |
| `my_projects.json` | Add your projects not on GitHub |

## CV Template (`templates/cv_template.tex`)

A default ATS-friendly LaTeX CV template is committed at `templates/cv_template.tex`.
It is used automatically when `my_cv.tex` is missing or when you turn on the toggle in `config/projects_config.py`:

```python
USE_DEFAULT_CV_TEMPLATE = True  # always use the template
USE_DEFAULT_CV_TEMPLATE = False  # use my_cv.tex (default)
```

## GitHub Repo Selection (`my_github.py`)

```python
GITHUB_URL = "https://github.com/YOUR_USERNAME"  # no token needed

INCLUDE_REPOS = ["my-rag-chatbot"]   # whitelist — checked first
EXCLUDE_REPOS = ["old-uni-project"]  # blacklist — if include is empty
# both empty → use ALL public repos
```
