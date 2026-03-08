# Profile Setup — `data/profile/`

This folder shows the structure of `data/profile/`, which is gitignored to keep your personal data private.

## Setup Steps

```bash
# 1. Create your private profile folder
mkdir data\profile

# 2. Copy and rename the example files
copy data\profile.example\my_cv.example.tex          data\profile\my_cv.tex
copy data\profile.example\my_github.example.py       data\profile\my_github.py
copy data\profile.example\my_projects.example.json   data\profile\my_projects.json
```

Then edit each file:

| File | What to edit |
|------|-------------|
| `data/profile/my_cv.tex` | Paste your full LaTeX CV (or leave empty to use `cv_template.tex`) |
| `data/profile/my_github.py` | Set `GITHUB_URL` and optionally fill `INCLUDE_REPOS` or `EXCLUDE_REPOS` |
| `data/profile/my_projects.json` | Add projects not on GitHub or projects you want to describe manually |

## Files in This Folder

| File | Purpose |
|------|---------|
| `my_cv.example.tex` | LaTeX CV structure — copy to `data/profile/my_cv.tex` |
| `my_github.example.py` | GitHub settings — copy to `data/profile/my_github.py` |
| `my_projects.example.json` | Manual projects schema — copy to `data/profile/my_projects.json` |
| `cv_template.tex` | Default CV template used when `my_cv.tex` is absent or toggle is on |

## GitHub Repo Selection (`data/profile/my_github.py`)

```python
GITHUB_URL = "https://github.com/YOUR_USERNAME"  # no token needed

# Option A — whitelist (only these repos used):
INCLUDE_REPOS = ["my-rag-chatbot", "my-api"]

# Option B — blacklist (all public repos except these):
EXCLUDE_REPOS = ["old-uni-project", "test-repo"]

# Option C — leave both empty → use ALL public repos
```

Priority: `INCLUDE_REPOS` → `EXCLUDE_REPOS` → all public repos

## CV Template Toggle (`config/projects_config.py`)

```python
USE_DEFAULT_CV_TEMPLATE = False  # default: use your my_cv.tex
USE_DEFAULT_CV_TEMPLATE = True   # force: always use cv_template.tex
```

If `my_cv.tex` doesn't exist, `cv_template.tex` is used automatically.
