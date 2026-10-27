import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import requests

from src.models import JobRaw

# Longueur max conservée par offre : les exigences (années, outils, « new grads exclus »)
# sont souvent en fin d'annonce, au-delà de 4000 caractères.
MAX_DESC_CHARS = 12000


class BaseATSConnector(ABC):
    """Abstract base connector for Applicant Tracking Systems."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "Unknown Company")
        self.keywords = config.get("keywords", [])

    def _request(self, method: str, url: str, retries: int = 3, timeout: int = 20, **kwargs) -> Optional[requests.Response]:
        """Requête HTTP avec réessais (erreurs SSL/réseau ponctuelles, 429/5xx)."""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)", "Accept": "application/json"}
        headers.update(kwargs.pop("headers", {}) or {})
        last: Optional[requests.Response] = None
        for attempt in range(retries):
            try:
                last = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
                if last.status_code == 429 or last.status_code >= 500:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return last
            except requests.RequestException:
                time.sleep(1.0 * (attempt + 1))
        return last

    @abstractmethod
    def fetch_jobs(self) -> List[JobRaw]:
        """Fetch and return normalized list of raw jobs."""
        pass
