# Profile Setup — `data/profile/`

This folder shows the **structure** of `data/profile/`, which is gitignored to keep your personal data private.

## Setup Steps

```bash
# 1. Create your private profile folder
mkdir data/profile

# 2. Copy the example files
copy data\profile.example\my_cv.example.tex     data\profile\my_cv.tex
copy data\profile.example\my_projects.example.json  data\profile\my_projects.json
```

Then:
- **`data/profile/my_cv.tex`** → Replace the placeholder with your real LaTeX CV
- **`data/profile/my_projects.json`** → Add your real projects (see schema below)
- **`config/projects_config.py`** → Set your GitHub URL and include/exclude repo lists

## GitHub Repo Selection (`config/projects_config.py`)

```python
GITHUB_PROFILE_URL = "https://github.com/YOUR_USERNAME"  # no token needed

# Option A — whitelist (only these repos used):
GITHUB_INCLUDE_REPOS = ["my-rag-chatbot", "my-api"]

# Option B — blacklist (all public repos except these):
GITHUB_EXCLUDE_REPOS = ["old-uni-project", "test-repo"]

# Option C — leave both empty → use ALL public repos
```

Priority: `INCLUDE_REPOS` → `EXCLUDE_REPOS` → all public repos

## Files in This Example Folder

| File | Purpose |
|------|---------|
| `my_cv.example.tex` | LaTeX CV structure — copy to `data/profile/my_cv.tex` |
| `my_projects.example.json` | Manual projects schema — copy to `data/profile/my_projects.json` |
