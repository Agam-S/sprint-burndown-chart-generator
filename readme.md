# GitHub Projects Burndown Chart

Generate a sprint burndown chart from a GitHub Projects (Projects V2) board.  
Reads configuration from `config.json`, fetches project items via the GitHub GraphQL API, filters items by sprint (label or project field), computes remaining and ideal story points per day, and outputs static matplotlib and/or Plotly charts.

<!-- table of contents -->
## Table of Contents
- [Requirements](#requirements)
- [Quick usage](#quick-usage)
- [Example config.json](#example-configjson)
- [Config field descriptions](#config-field-descriptions)
- [Required GitHub token scopes](#required-github-token-scopes)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Requirements
- Python 3.8+
- The following packages:
  - requests
  - matplotlib
  - plotly
  - pandas (optional for extra processing)
  - python-dateutil
  - kaleido (optional, for plotly static image export)

Install:
```powershell
pip install requests matplotlib plotly pandas python-dateutil kaleido
```
OR via `requirements.txt`:
```powershell
pip install -r requirements.txt
```

## Quick usage
1. Edit `config.json` with the repo, date info, etc (do NOT commit `config.json` with secrets).
2. Provide a GitHub token either in `config.json` (`github_token`).
3. Run:
```powershell
python chart.py
```
Charts will be shown and saved according to `config.json.save_path`.

## Example config.json
Use the repository sample as a template. Example fields:

```json
{
  "project_type": "organization",
  "owner": "owner-name",
  "repo": "repo-name",  
  "project_number": 15,
  "sprint_start": "2025-09-29T00:00:00",
  "sprint_end": "2025-10-12T23:59:59",
  "sprint_label": "Sprint X",
  "sprint_field": null,
  "points_field": null,
  "planned_points": 200,
  "chart_type": "both",
  "save_path": "sprint3_burndown.png",
  "github_token": ""
}
```

## Config field descriptions
- `project_type` — "organization" or "repository". Choose based on your Projects V2 scope.
- `owner` — organization name (for `organization`) or repo owner (for `repository`).
- `repo` — repository name (required only when `project_type` is `repository`).
- `project_number` — Projects V2 number from the URL (e.g. `15`).
- `sprint_start` — sprint start datetime in ISO format (e.g. `2025-09-29T00:00:00`).
- `sprint_end` — sprint end datetime in ISO format (e.g. `2025-10-12T23:59:59`).
- `sprint_label` — optional label text used to mark items in this sprint (case-insensitive). If provided and `sprint_field` is null, items with this label are included.
- `sprint_field` — optional project field name used to assign sprint (e.g. `"Sprint"`). If set, the script will match the field value to `sprint_label`.
- `points_field` — optional project field name that contains story points (numeric or text). If not set, the script tries numeric/text fields and label fallback.
- `planned_points` — optional numeric override for total planned points. When set, ideal and actual series start at this value (useful when actual item sum differs from planned).
- `chart_type` — `"matplotlib"`, `"plotly"`, or `"both"`.
- `save_path` — output filename (PNG). Plotly also writes an HTML file next to the PNG (if enabled).
- `github_token` — personal access token.

## Required GitHub token scopes
- For organization Projects V2: `read:org` and `read:project` (and `repo` if you need access to private repository content).
- For repository Projects V2: `repo` (for private repos) and `read:project`.
Create a token at GitHub → Settings → Developer settings → Personal access tokens.

## Security notes
- Do NOT commit `config.json` with a token to a public repository.
- a .gitignore is provided to exclude `config.json`.

## Troubleshooting
- "No valid project data found": print raw GraphQL response (the script may already show it) — check token permissions, `project_number`, and `owner`.
- Plotly `write_image` fails: install `kaleido` (`pip install kaleido`) or rely on the generated HTML.
- If items appear missing, confirm the sprint label or sprint field matches exactly what is in the project.

## License
GPL-3.0 https://www.gnu.org/licenses/gpl-3.0.txt


