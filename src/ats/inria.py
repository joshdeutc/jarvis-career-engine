import re
import html
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw
from src.screening import title_prefilter


class InriaConnector(BaseATSConnector):
    """
    Connector for Inria public job portal (https://jobs.inria.fr/public/classic/fr/offres).
    Filters out internships (Stage) and Post-Docs to keep only PhD (Thèse) and R&D Engineer roles,
    and fetches full detail pages for candidates passing title_prefilter.
    """

    BASE_URL = "https://jobs.inria.fr"
    LIST_URL = "https://jobs.inria.fr/public/classic/fr/offres"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        }

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        return " ".join(text.split())

    def _fetch_detail(self, url: str, fallback_title: str) -> tuple[str, str]:
        try:
            resp = self._request("GET", url, headers=self.headers, timeout=8)
            if not resp or resp.status_code != 200:
                return "Inria (France)", fallback_title
            raw = resp.text
            loc_m = re.search(
                r"(Paris|Saclay|Grenoble|Sophia[- ]Antipolis|Rennes|Lyon|Nancy|Bordeaux|Lille|Montpellier|Strasbourg)",
                raw,
                flags=re.I,
            )
            loc = f"Inria {loc_m.group(1)} (France)" if loc_m else "Inria (France)"
            main_idx = raw.find("<main")
            chunk = raw[main_idx:] if main_idx != -1 else raw
            desc = self._clean_html(chunk)[:MAX_DESC_CHARS]
            return loc, desc or fallback_title
        except Exception:
            return "Inria (France)", fallback_title

    def fetch_jobs(self) -> List[JobRaw]:
        stubs: List[JobRaw] = []
        seen = set()
        try:
            resp = self._request("GET", self.LIST_URL, headers=self.headers, timeout=12)
            if not resp or resp.status_code != 200:
                return []

            link_pattern = re.compile(
                r'href="(/public/classic/fr/offres/(202\d-\d+))"[^>]*>(.*?)</a>',
                re.S,
            )
            for href, ref, raw_title in link_pattern.findall(resp.text):
                job_id = f"inria_{ref}"
                if job_id in seen:
                    continue
                seen.add(job_id)

                clean_title = html.unescape(re.sub(r"<[^>]+>", " ", raw_title))
                clean_title = " ".join(clean_title.split())

                low_t = clean_title.lower()
                if any(w in low_t for w in ["post-doc", "postdoc", "stage ", "intern", "apprenti"]):
                    continue

                if self.keywords:
                    if not any(kw.lower() in low_t for kw in self.keywords):
                        continue

                full_url = f"{self.BASE_URL}{href}"
                stub = JobRaw(
                    id=job_id,
                    company="Inria",
                    title=clean_title,
                    url=full_url,
                    location="Inria (France)",
                    description_text=clean_title,
                    date_posted="Récent (2026)",
                    ats_type="inria",
                )
                if title_prefilter(stub) is None:
                    stubs.append(stub)
        except Exception as e:
            print(f"[InriaConnector] Erreur : {e}")

        kept = stubs[:20]
        from concurrent.futures import ThreadPoolExecutor

        def _enrich(s: JobRaw) -> JobRaw:
            loc, desc = self._fetch_detail(s.url, s.title)
            s.location = loc
            s.description_text = desc
            return s

        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_enrich, kept))

        return kept
