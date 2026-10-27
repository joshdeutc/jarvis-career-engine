import re
import html
from datetime import datetime, timezone
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw


class LeverConnector(BaseATSConnector):
    """
    Connector for the Lever public postings API (api.lever.co, instance EU : api.eu.lever.co).
    Utilisé par de nombreuses scale-ups européennes (DE/CH/NL/UK/Nordics).
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.slug = config.get("slug") or config.get("board") or config.get("company_id") or ""
        self.location_keywords = config.get("location_keywords", [])
        self.instances = [
            f"https://api.lever.co/v0/postings/{self.slug}?mode=json",
            f"https://api.eu.lever.co/v0/postings/{self.slug}?mode=json",
        ]

    @staticmethod
    def _clean_html(raw_html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw_html or "")
        return " ".join(html.unescape(text).split())

    def fetch_jobs(self) -> List[JobRaw]:
        postings = None
        for url in self.instances:
            resp = self._request("GET", url)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    postings = data
                    break
        if postings is None:
            return []

        jobs: List[JobRaw] = []
        for p in postings:
            cats = p.get("categories") or {}
            locs = cats.get("allLocations") or [cats.get("location") or ""]
            location = "; ".join(l for l in locs if l)
            if self.location_keywords and not any(k.lower() in location.lower() for k in self.location_keywords):
                continue

            title = p.get("text", "")
            if self.keywords and not any(k.lower() in f"{title} {location}".lower() for k in self.keywords):
                continue

            parts = [p.get("descriptionPlain") or self._clean_html(p.get("description", ""))]
            for lst in p.get("lists") or []:
                parts.append(f"{lst.get('text', '')}: {self._clean_html(lst.get('content', ''))}")
            parts.append(p.get("additionalPlain") or self._clean_html(p.get("additional", "")))
            desc = "\n".join(x for x in parts if x)[:MAX_DESC_CHARS]

            created = p.get("createdAt")
            date_posted = ""
            if isinstance(created, (int, float)):
                date_posted = datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

            jobs.append(JobRaw(
                id=f"lever_{self.slug}_{p.get('id', '')}",
                company=self.name,
                title=title,
                url=p.get("hostedUrl") or p.get("applyUrl") or f"https://jobs.lever.co/{self.slug}/{p.get('id', '')}",
                location=location,
                description_text=desc,
                date_posted=date_posted,
                ats_type="lever",
            ))
        return jobs
