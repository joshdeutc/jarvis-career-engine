import re
import html
import requests
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw


class AshbyConnector(BaseATSConnector):
    """
    Connector for Ashby public job board API.
    Used by Mistral AI (mistral.ai), etc.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.board = config["board"]
        self.location_keywords = config.get("location_keywords", ["Paris", "France", "London", "Europe", "EMEA"])
        self.api_url = f"https://api.ashbyhq.com/posting-api/job-board/{self.board}?includeCompensation=true"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "application/json"
        }

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        return " ".join(text.split())

    def fetch_jobs(self) -> List[JobRaw]:
        jobs: List[JobRaw] = []
        try:
            resp = self._request("GET", self.api_url, headers=self.headers)
            if resp is None or resp.status_code != 200:
                print(f"[AshbyConnector] Failed with status {getattr(resp, 'status_code', 'n/a')} for board {self.board}")
                return []

            data = resp.json()
            postings = data.get("jobs", [])

            for p in postings:
                job_id = str(p.get("id", ""))
                title = p.get("title", "")
                location = p.get("location", "")
                date_posted = p.get("publishedAt", "")
                job_url = p.get("jobUrl", f"https://jobs.ashbyhq.com/{self.board}/{job_id}")

                desc = p.get("descriptionPlain", "")
                if not desc:
                    desc = self._clean_html(p.get("descriptionHtml", ""))
                clean_desc = desc[:MAX_DESC_CHARS]

                # Location filter if specified
                if self.location_keywords:
                    if not any(loc_kw.lower() in location.lower() for loc_kw in self.location_keywords):
                        continue

                # Keyword pre-filter if keywords specified
                if self.keywords:
                    combined = f"{title} {location}".lower()
                    if not any(kw.lower() in combined for kw in self.keywords):
                        continue

                jobs.append(JobRaw(
                    id=f"ashby_{self.board}_{job_id}",
                    company=self.name,
                    title=title,
                    url=job_url,
                    location=location,
                    description_text=clean_desc,
                    date_posted=date_posted,
                    ats_type="ashby"
                ))

        except Exception as e:
            print(f"[AshbyConnector] Error fetching for {self.name}: {e}")

        return jobs
