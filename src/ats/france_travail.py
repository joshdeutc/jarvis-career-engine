import os
import requests
from typing import List, Dict, Any, Optional
from src.ats.base import BaseATSConnector, MAX_DESC_CHARS
from src.models import JobRaw


class FranceTravailConnector(BaseATSConnector):
    """
    Connector for the official France Travail (ex Pôle Emploi) 'Offres d'emploi v2' API.
    Used for companies whose career websites are protected by anti-bot systems (e.g. BNP Paribas).
    """

    AUTH_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.company_query = config.get("company_query", self.name)
        self.client_id = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "")
        self.client_secret = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "")
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> Optional[str]:
        if not self.client_id or not self.client_secret:
            return None

        if self._access_token:
            return self._access_token

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "o2dsoffre api_offresdemploiv2"
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            resp = requests.post(self.AUTH_URL, data=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                self._access_token = resp.json().get("access_token")
                return self._access_token
            else:
                print(f"[FranceTravail] Auth failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"[FranceTravail] Auth error: {e}")

        return None

    def fetch_jobs(self) -> List[JobRaw]:
        token = self._get_access_token()
        if not token:
            print(f"[FranceTravail] Credentials non configurés (FRANCE_TRAVAIL_CLIENT_ID / SECRET manquants). "
                  f"Saut de la recherche France Travail pour '{self.name}'.")
            return []

        jobs: List[JobRaw] = []
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        # Filtres STRUCTURÉS de l'API (bien plus fiables que des regex sur le texte) :
        #   experienceExige = D (débutant accepté) | S (souhaitée) | E (exigée)
        #   publieeDepuis   = nombre de jours (1, 3, 7, 14, 31)
        #   typeContrat     = CDI, CDD, MIS...
        experience_exige = self.config.get("experience_exige", "D")
        published_since = self.config.get("published_since", 31)
        contract_type = self.config.get("type_contrat", "")
        pages = int(self.config.get("pages", 2))  # 150 résultats par page

        search_terms = self.config.get("queries") or self.keywords or [""]

        for term in search_terms:
            mots_cles = f"{self.company_query} {term}".strip() if self.config.get("company_query") else term
            for page in range(pages):
                params = {
                    "motsCles": mots_cles,
                    "range": f"{page * 150}-{page * 150 + 149}",
                }
                if experience_exige:
                    params["experienceExige"] = experience_exige
                if published_since:
                    params["publieeDepuis"] = published_since
                if contract_type:
                    params["typeContrat"] = contract_type

                try:
                    resp = self._request("GET", self.SEARCH_URL, params=params, headers=headers)
                    # France Travail returns 200 (ou 206 si partiel) with list or 204 if no results
                    if resp is None or resp.status_code not in (200, 206):
                        break

                    data = resp.json()
                    results = data.get("resultats", [])
                    if not results:
                        break

                    for item in results:
                        job_id = item.get("id", "")
                        title = item.get("intitule", "")
                        description = item.get("description", "")
                        exp_label = item.get("experienceLibelle", "")
                        if exp_label:
                            description = f"Expérience: {exp_label}. {description}"
                        origin = item.get("origineOffre", {})
                        url = origin.get("urlOrigine", f"https://candidat.francetravail.fr/offres/recherche/detail/{job_id}")

                        lieu = item.get("lieuTravail", {})
                        location = lieu.get("libelle", "")
                        date_posted = item.get("dateCreation", "")
                        company_name = (item.get("entreprise") or {}).get("nom") or self.name

                        jobs.append(JobRaw(
                            id=f"ft_{job_id}",
                            company=company_name,
                            title=title,
                            url=url,
                            location=f"{location}, France",
                            description_text=description[:MAX_DESC_CHARS],
                            date_posted=date_posted,
                            ats_type="france_travail"
                        ))

                    if len(results) < 150:
                        break

                except Exception as e:
                    print(f"[FranceTravail] Error fetching for '{mots_cles}': {e}")
                    break

        seen = set()
        unique = []
        for j in jobs:
            if j.id not in seen:
                seen.add(j.id)
                unique.append(j)

        return unique
