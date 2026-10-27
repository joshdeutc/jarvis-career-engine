import json
import os
import time
from typing import Dict, Any, Set


class StorageManager:
    """
    Manages persistent state of previously processed jobs in seen_jobs.json.
    Enables zero-cost asymmetric state persistence through Git commits.
    """

    def __init__(self, filepath: str = "seen_jobs.json"):
        self.filepath = filepath
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[StorageManager] Error reading {self.filepath}: {e}, initializing empty state.")
                return {}
        return {}

    def is_seen(self, job_id: str) -> bool:
        return job_id in self.data

    def filter_unseen(self, job_ids: Set[str]) -> Set[str]:
        return {jid for jid in job_ids if jid not in self.data}

    def mark_seen(self, job_id: str, metadata: Dict[str, Any] = None):
        self.data[job_id] = {
            "first_seen": metadata.get("first_seen", int(time.time())) if metadata else int(time.time()),
            "company": metadata.get("company", "") if metadata else "",
            "title": metadata.get("title", "") if metadata else "",
            "ats_type": metadata.get("ats_type", "") if metadata else "",
            "matched_profile": metadata.get("matched_profile", "") if metadata else "",
            "is_relevant": metadata.get("is_relevant", False) if metadata else False,
        }

    def save(self):
        # Limit to the most recent 10,000 entries to maintain lightweight Git commits
        if len(self.data) > 10000:
            sorted_items = sorted(
                self.data.items(),
                key=lambda x: x[1].get("first_seen", 0) if isinstance(x[1], dict) else 0,
                reverse=True
            )
            self.data = dict(sorted_items[:10000])

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
