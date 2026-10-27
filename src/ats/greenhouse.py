import re
import html
import requests
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw


class GreenhouseConnector(BaseATSConnector):
    """Connector for Greenhouse Job Board API."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.board_token = config["board_token"]
        self.location_keywords = config.get("location_keywords", ["Paris", "France", "London", "Europe", "EMEA"])
        self.api_url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs?content=true"

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        return " ".join(text.split())

    def fetch_jobs(self) -> List[JobRaw]:
        jobs: List[JobRaw] = []
        try:
            resp = self._request("GET", self.api_url)
            if resp is None or resp.status_code != 200:
                return []

            data = resp.json()
            postings = data.get("jobs", [])

            for p in postings:
                job_id = str(p.get("id", ""))
                title = p.get("title", "")
                location = p.get("location", {}).get("name", "")
                job_url = p.get("absolute_url", "")
                date_posted = p.get("updated_at", "")
                desc = self._clean_html(p.get("content", ""))[:MAX_DESC_CHARS]

                if self.location_keywords:
                    if not any(loc_kw.lower() in location.lower() for loc_kw in self.location_keywords):
                        continue

                if self.keywords:
                    combined = f"{title} {location}".lower()
                    if not any(kw.lower() in combined for kw in self.keywords):
                        continue

                jobs.append(JobRaw(
                    id=f"greenhouse_{self.board_token}_{job_id}",
                    company=self.name,
                    title=title,
                    url=job_url,
                    location=location,
                    description_text=desc,
                    date_posted=date_posted,
                    ats_type="greenhouse"
                ))
        except Exception as e:
            print(f"[GreenhouseConnector] Error fetching for {self.name}: {e}")

        return jobs
