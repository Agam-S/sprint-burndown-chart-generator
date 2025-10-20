import os
import json
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go

CONFIG_PATH = "config.json"

class GitHubProjectsBurndownChart:
    def __init__(self, config_path=CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        # token from config
        self.token = self.config.get("github_token")
        if not self.token:
            raise RuntimeError("GitHub token not provided in config.json")

        self.graphql_headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _build_query(self, project_type):
        selection = """
          projectV2(number: $number) {
            id
            title
            items(first: 250) {
              nodes {
                id
                content {
                  ... on Issue {
                    id
                    title
                    state
                    createdAt
                    closedAt
                    updatedAt
                    labels(first: 50) { nodes { name } }
                  }
                  ... on PullRequest {
                    id
                    title
                    state
                    createdAt
                    closedAt
                    updatedAt
                  }
                }
                fieldValues(first: 50) {
                  nodes {
                    ... on ProjectV2ItemFieldSingleSelectValue {
                      name
                      field { ... on ProjectV2SingleSelectField { name } }
                    }
                    ... on ProjectV2ItemFieldTextValue {
                      text
                      field { ... on ProjectV2Field { name } }
                    }
                    ... on ProjectV2ItemFieldNumberValue {
                      number
                      field { ... on ProjectV2Field { name } }
                    }
                  }
                }
              }
            }
          }
        """
        if project_type == "organization":
            return f"query($org:String!, $number:Int!) {{ organization(login:$org) {{ {selection} }} }}"
        else:
            return f"query($owner:String!, $repo:String!, $number:Int!) {{ repository(owner:$owner, name:$repo) {{ {selection} }} }}"

    def get_project_data(self):
        cfg = self.config
        project_number = int(cfg["project_number"])
        project_type = cfg.get("project_type", "organization")  # 'organization' or 'repository'

        query = self._build_query(project_type)
        variables = {"number": project_number}
        if project_type == "organization":
            variables["org"] = cfg["owner"]
        else:
            variables["owner"] = cfg["owner"]
            variables["repo"] = cfg["repo"]

        resp = requests.post("https://api.github.com/graphql", headers=self.graphql_headers,
                             json={"query": query, "variables": variables})
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
        if resp.status_code != 200 or "errors" in data:
            print("GraphQL response error:", data.get("errors") or resp.text)
            return None
        return data

    def _extract_story_points(self, item, points_field_name=None):
        fv = item.get("fieldValues", {}).get("nodes", [])
        if points_field_name:
            for v in fv:
                field = v.get("field", {}) or {}
                fname = field.get("name", "")
                if fname and fname.lower() == points_field_name.lower():
                    if "number" in v and v["number"] is not None:
                        return float(v["number"])
                    if "text" in v and v["text"]:
                        try:
                            return float(v["text"])
                        except Exception:
                            pass
        for v in fv:
            if "number" in v and v["number"] is not None:
                return float(v["number"])
            if "text" in v and v["text"]:
                try:
                    return float(v["text"])
                except Exception:
                    pass
        content = item.get("content", {}) or {}
        labels = content.get("labels", {}).get("nodes", [])
        for lbl in labels:
            name = lbl.get("name", "")
            import re
            m = re.search(r"(\d+(\.\d+)?)", name)
            if m:
                return float(m.group(1))
        return 1.0

    def _get_item_sprint(self, item, sprint_field_name=None):
        # check field values for sprint assignment
        fv = item.get("fieldValues", {}).get("nodes", [])
        for v in fv:
            field = v.get("field", {}) or {}
            fname = field.get("name", "")
            if sprint_field_name and fname and fname.lower() == sprint_field_name.lower():
                # match text or single select name
                if "name" in v and v["name"]:
                    return v["name"]
                if "text" in v and v["text"]:
                    return v["text"]
        # fallback labels
        content = item.get("content", {}) or {}
        labels = content.get("labels", {}).get("nodes", [])
        return [lbl.get("name", "") for lbl in labels]

    def process_project_data(self, raw, sprint_start, sprint_end):
        if not raw or "data" not in raw:
            print("No valid project data found")
            return None

        cfg = self.config
        project_type = cfg.get("project_type", "organization")
        project = None
        if project_type == "organization":
            project = raw["data"].get("organization", {}).get("projectV2")
        else:
            project = raw["data"].get("repository", {}).get("projectV2")
        if not project:
            print("Project not found in response")
            return None

        items = project.get("items", {}).get("nodes", [])
        sprint_label = cfg.get("sprint_label")  # e.g. "Sprint 3"
        sprint_field = cfg.get("sprint_field")  # e.g. "Sprint"
        points_field = cfg.get("points_field")  # optional
        filtered = []
        total_points = 0.0

        for it in items:
            content = it.get("content") or {}
            if not content:
                continue
            # sprint filter
            item_sprint = self._get_item_sprint(it, sprint_field)
            include = False
            if sprint_field:
                # field-based
                if isinstance(item_sprint, str) and sprint_label and sprint_label.lower() in str(item_sprint).lower():
                    include = True
            else:
                # label-based: item_sprint is list
                if isinstance(item_sprint, list):
                    if sprint_label:
                        include = any(sprint_label.lower() == lbl.lower() for lbl in item_sprint)
                    else:
                        include = True  # no sprint filter specified -> include all
            if not include:
                continue

            sp = self._extract_story_points(it, points_field)
            created = content.get("createdAt")
            closed = content.get("closedAt")
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None
                closed_dt = datetime.fromisoformat(closed.replace("Z", "+00:00")) if closed else None
            except Exception:
                created_dt = None
                closed_dt = None

            entry = {
                "title": content.get("title") or "",
                "story_points": float(sp),
                "created_at": created_dt,
                "closed_at": closed_dt,
                "state": content.get("state")
            }
            filtered.append(entry)
            total_points += float(sp)

        return {
            "project_name": project.get("title"),
            "items": filtered,
            "total_points": total_points,
            "sprint_start": sprint_start,
            "sprint_end": sprint_end
        }

    def calculate_burndown_data(self, pdata, planned_points=None):
        sprint_start = pdata["sprint_start"]
        sprint_end = pdata["sprint_end"]
        total_points = planned_points if planned_points is not None else pdata["total_points"]
        items = pdata["items"]

        dates = []
        remaining = []
        ideal = []
        current = sprint_start
        days = max(1, (sprint_end - sprint_start).days)
        daily = total_points / days
        while current <= sprint_end:
            dates.append(current)
            done = sum(i["story_points"] for i in items if i["closed_at"] and i["closed_at"].date() <= current.date())
            rem = max(0.0, total_points - done)
            remaining.append(rem)
            elapsed = (current - sprint_start).days
            ideal_rem = max(0.0, total_points - daily * elapsed)
            ideal.append(ideal_rem)
            current += timedelta(days=1)
        return {"dates": dates, "remaining": remaining, "ideal": ideal, "total_points": total_points}

    def create_matplotlib_chart(self, data, project_name, save_path=None):
        fig, ax = plt.subplots(figsize=(12,6))
        ax.plot(data["dates"], data["remaining"], marker="o", label="Actual", color="#ff6b6b")
        ax.plot(data["dates"], data["ideal"], linestyle="--", label="Ideal", color="#4ecdc4")
        ax.set_title(f"{project_name} - Sprint Burndown")
        ax.set_xlabel("Date")
        ax.set_ylabel("Story Points Remaining")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.xticks(rotation=45)
        ax.legend()
        ax.grid(alpha=0.3)
        ax.set_ylim(bottom=0)
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches="tight")
            print("Saved matplotlib chart to", save_path)
        plt.show()

    def create_plotly_chart(self, data, project_name, save_path=None):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["dates"], y=data["remaining"], mode="lines+markers", name="Actual",
                                 line=dict(color="#ff6b6b")))
        fig.add_trace(go.Scatter(x=data["dates"], y=data["ideal"], mode="lines", name="Ideal",
                                 line=dict(color="#4ecdc4", dash="dash")))
        fig.update_layout(title=f"{project_name} - Sprint Burndown", xaxis_title="Date", yaxis_title="Story Points")
        if save_path:
            html_path = save_path.replace(".png", ".html")
            fig.write_html(html_path)
            try:
                fig.write_image(save_path) # requires kaleido
            except Exception:
                print("plotly.write_image failed (kaleido may be missing). HTML saved at", html_path)
            print("Saved plotly chart to", html_path)
        fig.show()

    def run(self):
        cfg = self.config
        sprint_start = datetime.fromisoformat(cfg["sprint_start"])
        sprint_end = datetime.fromisoformat(cfg["sprint_end"])
        planned = cfg.get("planned_points")
        raw = self.get_project_data()
        if not raw:
            raise RuntimeError("Failed to fetch project data from GitHub API. See printed error above.")
        pdata = self.process_project_data(raw, sprint_start, sprint_end)
        if not pdata:
            raise RuntimeError("No project items matched the sprint filter or project response unexpected.")
        burndown = self.calculate_burndown_data(pdata, planned_points=planned)
        save_path = cfg.get("save_path")
        if cfg.get("chart_type", "both") in ("matplotlib","both"):
            self.create_matplotlib_chart(burndown, pdata["project_name"], save_path)
        if cfg.get("chart_type", "both") in ("plotly","both"):
            self.create_plotly_chart(burndown, pdata["project_name"], save_path)
        return {"project": pdata, "burndown": burndown}

if __name__ == "__main__":
    chart = GitHubProjectsBurndownChart()
    result = chart.run()
    print("Done. Project:", result["project"]["project_name"], "Total points:", result["project"]["total_points"])