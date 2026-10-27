import re
import html
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw
from src.screening import title_prefilter


class OracleHCMConnector(BaseATSConnector):
    """
    Connector for Oracle HCM Cloud Recruiting Candidate Experience API.
    Used by Hermès (talents.hermes.com), etc.
    Fetches full ExternalDescriptionStr + ExternalQualificationsStr from recruitingCEJobRequisitionDetails.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.instance = config["instance"]
        self.site_number = config.get("site_number", "CX_12001")
        self.portal_url = config.get("portal_url", "https://talents.hermes.com/en/sites/CX/job")
        self.api_url = f"https://{self.instance}.fa.ocs.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        self.detail_url = f"https://{self.instance}.fa.ocs.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "application/json",
        }

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        return " ".join(text.split())

    def _fetch_detail_text(self, job_id: str) -> str:
        params = {
            "onlyData": "true",
            "expand": "all",
            "finder": f'ById;Id="{job_id}",siteNumber={self.site_number}',
        }
        try:
            resp = self._request("GET", self.detail_url, params=params, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return ""
            items = resp.json().get("items", [])
            if not items:
                return ""
            d = items[0]
            parts = [
                d.get("ExternalDescriptionStr") or "",
                d.get("ExternalResponsibilitiesStr") or "",
                d.get("ExternalQualificationsStr") or "",
                d.get("ShortDescriptionStr") or "",
            ]
            return self._clean_html(" ".join(p for p in parts if p))[:MAX_DESC_CHARS]
        except Exception:
            return ""

    def fetch_jobs(self) -> List[JobRaw]:
        raw_reqs: Dict[str, Dict[str, Any]] = {}
        search_terms = self.keywords if self.keywords else [""]

        for term in search_terms:
            finder_param = f"findReqs;siteNumber={self.site_number}"
            if term:
                finder_param += f",keyword={term}"

            params = {
                "onlyData": "true",
                "expand": "requisitionList",
                "finder": finder_param,
                "limit": 25,
            }

            try:
                resp = self._request("GET", self.api_url, params=params, headers=self.headers, timeout=12)
                if not resp or resp.status_code != 200:
                    continue

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    continue

                for req in items[0].get("requisitionList", []):
                    job_id = str(req.get("Id", ""))
                    if job_id and job_id not in raw_reqs:
                        raw_reqs[job_id] = req
            except Exception as e:
                print(f"[OracleHCMConnector] Error fetching for {self.name} (term: '{term}'): {e}")

        jobs: List[JobRaw] = []
        for job_id, req in raw_reqs.items():
            title = req.get("Title", "")
            location = req.get("PrimaryLocation", "")
            date_posted = req.get("PostingStartDate", "")
            job_url = f"{self.portal_url}/{job_id}"

            stub = JobRaw(
                id=f"oracle_hcm_{self.name.lower()}_{job_id}",
                company=self.name,
                title=title,
                url=job_url,
                location=location,
                description_text="",
                date_posted=date_posted,
                ats_type="oracle_hcm",
            )
            if title_prefilter(stub) is not None:
                continue

            detail_desc = self._fetch_detail_text(job_id)
            if not detail_desc:
                detail_desc = self._clean_html(req.get("ShortDescription", "") or "")[:MAX_DESC_CHARS]

            stub.description_text = detail_desc
            jobs.append(stub)

        return jobs
