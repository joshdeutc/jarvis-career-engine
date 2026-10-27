import re
import html
import requests
from typing import List, Dict, Any
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw
from src.screening import title_prefilter


class CEAConnector(BaseATSConnector):
    """
    Connector for CEA (Commissariat à l'énergie atomique et aux énergies alternatives)
    TalentSoft career portal (https://www.emploi.cea.fr).
    Deduplicates and applies title_prefilter before fetching detail pages.
    """

    BASE_URL = "https://www.emploi.cea.fr"
    LIST_URL = "https://www.emploi.cea.fr/offre-de-emploi/liste-offres.aspx"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.profile_facets = config.get("profile_facets", [1898, 1918])
        self.contract_facets = config.get("contract_facets", [577, 578])
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

    def _fetch_detail(self, url: str) -> tuple[str, str, str]:
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code != 200:
                return "CEA (France)", "Récent (2026)", ""
            raw = resp.text
            idx = raw.find("composantDetailOffre")
            detail_chunk = raw[idx : idx + 20000] if idx != -1 else raw

            date_m = re.search(r"Date de parution\s*.*?\b(\d{2}/\d{2}/\d{4})\b", detail_chunk, flags=re.S | re.I)
            date_posted = date_m.group(1) if date_m else "Récent (2026)"

            loc_m = re.search(
                r"(Paris-Saclay|Saclay|Fontenay-aux-Roses|Grenoble|Cadarache|Bruyères-le-Châtel|Marcoule|Cesta|Gramat|Le Ripault|Évry)",
                detail_chunk,
                flags=re.I,
            )
            location = f"CEA {loc_m.group(1)} (France)" if loc_m else "CEA (France)"

            clean_desc = self._clean_html(detail_chunk)[:MAX_DESC_CHARS]
            return location, date_posted, clean_desc
        except Exception:
            return "CEA (France)", "Récent (2026)", ""

    def fetch_jobs(self) -> List[JobRaw]:
        stubs: List[JobRaw] = []
        seen_ids = set()
        card_pattern = re.compile(
            r'<a\s+class="ts-offer-card__title-link[^"]*"\s+href="([^"]+)"\s+title="([^"]+)">\s*(.*?)\s*</a>',
            re.S,
        )

        for prof_id in self.profile_facets:
            for contract_id in self.contract_facets:
                contract_label = "CDI" if contract_id == 577 else "CDD / Recherche"
                try:
                    s = requests.Session()
                    s.headers.update(self.headers)
                    s.get(f"{self.LIST_URL}?lcid=1036", timeout=8)
                    s.get(f"{self.LIST_URL}?changefacet=1&facet_Profile={prof_id}", timeout=8)
                    resp = s.get(f"{self.LIST_URL}?changefacet=1&facet_Contract={contract_id}", timeout=8)
                    if resp.status_code != 200:
                        continue

                    for href, full_title_attr, title_txt in card_pattern.findall(resp.text):
                        clean_title = html.unescape(re.sub(r"\s+", " ", title_txt).strip())
                        clean_attr = html.unescape(full_title_attr)
                        ref_m = re.search(r"202\d-\d+", clean_attr)
                        ref = ref_m.group(0) if ref_m else href.split("_")[-1].replace(".aspx", "")

                        if ref.startswith("2025-"):
                            continue
                        job_id = f"cea_{ref}"
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        if self.keywords:
                            haystack = f"{clean_title} {clean_attr}".lower()
                            if not any(kw.lower() in haystack for kw in self.keywords):
                                continue

                        full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                        stub = JobRaw(
                            id=job_id,
                            company=f"CEA ({contract_label})",
                            title=clean_title,
                            url=full_url,
                            location="CEA (France)",
                            description_text=clean_attr,
                            date_posted="Récent (2026)",
                            ats_type="cea_talentsoft",
                        )
                        if title_prefilter(stub) is None:
                            stubs.append(stub)
                except Exception as e:
                    print(f"[CEAConnector] Erreur CEA (prof={prof_id}, contrat={contract_id}): {e}")

        kept = stubs[:20]
        from concurrent.futures import ThreadPoolExecutor

        def _enrich(s: JobRaw) -> JobRaw:
            loc, date_posted, desc = self._fetch_detail(s.url)
            s.location = loc
            s.date_posted = date_posted
            if desc:
                s.description_text = desc
            return s

        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_enrich, kept))
        return kept
