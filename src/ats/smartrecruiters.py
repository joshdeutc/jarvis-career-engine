import re
import html
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw


class SmartRecruitersConnector(BaseATSConnector):
    """Connector for SmartRecruiters Job Board API (CERN, Ubisoft, Devoteam, Bosch, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.company_id = config["company_id"]
        cf = config.get("country_filter", "fr")
        self.country_filter = [c.lower() for c in cf] if isinstance(cf, list) else ([cf.lower()] if cf else [])
        self.max_postings = int(config.get("max_postings", 100))
        self.max_details = int(config.get("max_details", 20))
        self.api_url = f"https://api.smartrecruiters.com/v1/companies/{self.company_id}/postings"

    @staticmethod
    def _clean_html(raw_html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw_html or "")
        return " ".join(html.unescape(text).split())

    def _fetch_description(self, posting_id: str) -> str:
        resp = self._request("GET", f"{self.api_url}/{posting_id}", retries=2, timeout=8)
        if resp is None or resp.status_code != 200:
            return ""
        sections = ((resp.json().get("jobAd") or {}).get("sections") or {})
        parts = []
        for key in ("jobDescription", "qualifications", "additionalInformation"):
            sec = sections.get(key) or {}
            if sec.get("text"):
                parts.append(f"{sec.get('title', '')}: {self._clean_html(sec['text'])}")
        return "\n".join(parts)[:MAX_DESC_CHARS]

    def fetch_jobs(self) -> List[JobRaw]:
        from src.screening import title_prefilter, JUNIOR_SIGNAL

        stubs: List[JobRaw] = []
        seen_ids = set()
        search_terms = self.keywords if self.keywords else [""]

        for term in search_terms[:6]:
            try:
                params = {"limit": min(100, self.max_postings), "offset": 0}
                if term:
                    params["q"] = term
                resp = self._request("GET", self.api_url, params=params, retries=2, timeout=10)
                if resp is None or resp.status_code != 200:
                    continue

                postings = resp.json().get("content", [])
                for p in postings:
                    job_id = str(p.get("id", ""))
                    if not job_id or job_id in seen_ids:
                        continue
                    loc = p.get("location", {}) or {}
                    country = (loc.get("country") or "").lower()
                    if self.country_filter and country and country not in self.country_filter:
                        continue

                    seen_ids.add(job_id)
                    title = p.get("name", "")
                    location_str = f"{loc.get('city', '')}, {(loc.get('country') or '').upper()}".strip(", ")
                    job_url = f"https://jobs.smartrecruiters.com/{self.company_id}/{job_id}"
                    date_posted = (p.get("releasedDate") or "")[:10]

                    stub = JobRaw(
                        id=f"sr_{self.company_id}_{job_id}",
                        company=self.name,
                        title=title,
                        url=job_url,
                        location=location_str,
                        description_text=title,
                        date_posted=date_posted,
                        ats_type="smartrecruiters",
                    )
                    if title_prefilter(stub) is None:
                        stubs.append(stub)
            except Exception as e:
                print(f"[SmartRecruitersConnector] Error fetching for {self.name} (term '{term}'): {e}")

        stubs.sort(key=lambda s: 0 if JUNIOR_SIGNAL.search(s.title or "") else 1)
        kept = stubs[: self.max_details]
        from concurrent.futures import ThreadPoolExecutor

        def _enrich(s: JobRaw) -> JobRaw:
            raw_id = s.id.split(f"sr_{self.company_id}_", 1)[-1]
            s.description_text = self._fetch_description(raw_id) or s.title
            return s

        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_enrich, kept))
        return kept
