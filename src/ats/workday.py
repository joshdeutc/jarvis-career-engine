import re
import html
import requests
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw


class WorkdayConnector(BaseATSConnector):
    """
    Connector for Workday CXS public JSON API.
    Used by Thales, Sanofi, Airbus, etc.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.tenant = config["tenant"]
        self.site = config.get("site", "Careers")
        self.domain = config.get("domain", f"{self.tenant}.wd3.myworkdayjobs.com")
        self.max_age_days = int(config.get("max_age_days", 14))
        self.api_url = f"https://{self.domain}/wday/cxs/{self.tenant}/{self.site}/jobs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _is_recent_posting(self, posted_on: str) -> bool:
        """Returns False if Workday indicates the offer is '30+ Days Ago' or older than max_age_days."""
        if not posted_on:
            return True
        lower = posted_on.lower()
        if "30+" in lower or "plus de 30" in lower:
            return False
        if "today" in lower or "aujourd" in lower or "yesterday" in lower or "hier" in lower:
            return True
        m = re.search(r"(\d+)", lower)
        if m:
            days = int(m.group(1))
            return days <= self.max_age_days
        return True

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        return " ".join(text.split())

    def fetch_jobs(self) -> List[JobRaw]:
        from src.screening import title_prefilter  # import local : évite tout import circulaire

        jobs: List[JobRaw] = []
        seen_ids = set()
        search_terms = self.keywords if self.keywords else [""]
        max_pages = int(self.config.get("max_pages", 2))
        page_size = 20

        for term in search_terms[:6]:
            for page in range(max_pages):
                payload = {
                    "appliedFacets": {},
                    "limit": page_size,
                    "offset": page * page_size,
                    "searchText": term
                }
                try:
                    resp = self._request("POST", self.api_url, json=payload, headers=self.headers, retries=2, timeout=10)
                    if resp is None or resp.status_code != 200:
                        break

                    data = resp.json()
                    postings = data.get("jobPostings", [])
                    if not postings:
                        break

                    for item in postings:
                        date_posted = item.get("postedOn", "")
                        if not self._is_recent_posting(date_posted):
                            continue

                        ext_path = item.get("externalPath", "")
                        # Extract official requisition ID (e.g. R0329769-1) from externalPath or bulletFields
                        req_match = re.search(r"(R\d+(?:-\d+)?)$", ext_path)
                        if req_match:
                            job_id = req_match.group(1)
                        else:
                            bullets = item.get("bulletFields", [])
                            r_bullets = [b for b in bullets if re.match(r"^R\d+", str(b))]
                            job_id = r_bullets[0] if r_bullets else ext_path.split("/")[-1]

                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        title = item.get("title", "")
                        location = item.get("locationsText", "")

                        full_url = f"https://{self.domain}/fr-FR/{self.site}{ext_path}"

                        # Détail (description complète) : seulement pour les titres qui passent le pré-filtre gratuit
                        description_text = ""
                        probe = JobRaw(id="p", company=self.name, title=title, url=full_url, ats_type="workday")
                        if title_prefilter(probe) is None:
                            try:
                                detail_url = f"https://{self.domain}/wday/cxs/{self.tenant}/{self.site}{ext_path}"
                                det_resp = self._request("GET", detail_url, headers=self.headers, timeout=15)
                                if det_resp is not None and det_resp.status_code == 200:
                                    det_data = det_resp.json().get("jobPostingInfo", {})
                                    raw_desc = det_data.get("jobDescription", "")
                                    description_text = self._clean_html(raw_desc)[:MAX_DESC_CHARS]
                            except Exception:
                                pass

                        jobs.append(JobRaw(
                            id=f"workday_{self.tenant}_{job_id}",
                            company=self.name,
                            title=title,
                            url=full_url,
                            location=location,
                            description_text=description_text,
                            date_posted=date_posted,
                            ats_type="workday"
                        ))

                    if len(postings) < page_size:
                        break

                except Exception as e:
                    print(f"[WorkdayConnector] Error fetching for {self.name} (term: '{term}'): {e}")
                    break

        # Deduplicate within batch
        seen = set()
        unique_jobs = []
        for j in jobs:
            if j.id not in seen:
                seen.add(j.id)
                unique_jobs.append(j)

        return unique_jobs
