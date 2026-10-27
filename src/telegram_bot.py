import os
import time
import html
import requests
from typing import Optional
from src.models import ProcessedJob, PROFILE_LABELS


class TelegramNotifier:
    """
    Asynchronous and rate-limited Telegram notification engine.
    Implements Token Bucket delay, 429 circuit breaker and HTML sanitization.
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.last_sent_time = 0.0

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def _sanitize(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return html.escape(str(text))

    def format_job_message(self, job: ProcessedJob) -> str:
        raw = job.raw
        ext = job.extraction

        profile_label = PROFILE_LABELS.get(ext.matched_profile, ext.matched_profile.value)
        contract_badge = f" [<code>{self._sanitize(ext.contract_type.value)}</code>]" if ext.contract_type else ""
        abroad_badge = " 🌍 <b>(International / V.I.E)</b>" if ext.is_abroad_or_vie else ""
        location_badge = f"📍 <b>Lieu :</b> {self._sanitize(raw.location)}{abroad_badge}\n" if raw.location else ""

        stack_str = ", ".join([f"<code>{self._sanitize(t)}</code>" for t in ext.tech_stack]) if ext.tech_stack else "Non spécifiée"
        salary_str = f"💰 <b>Salaire min :</b> {ext.salary_min_eur:,.0f} € / an\n" if ext.salary_min_eur else ""
        exp_str = (
            f"⏳ <b>Expérience :</b> {ext.years_of_experience} an(s) min\n"
            if ext.years_of_experience > 0
            else "⏳ <b>Expérience :</b> Jeune Diplômé / Junior (0 an)\n"
        )
        reason_str = f"💡 <i>{self._sanitize(ext.relevance_reason)}</i>\n" if ext.relevance_reason else ""

        message = (
            f"{profile_label} — <b>Match {ext.match_score}%</b>\n\n"
            f"🏢 <b>Entreprise :</b> {self._sanitize(raw.company)}\n"
            f"💼 <b>Poste :</b> {self._sanitize(raw.title)}{contract_badge}\n"
            f"{location_badge}"
            f"{exp_str}"
            f"{salary_str}"
            f"🛠️ <b>Stack :</b> {stack_str}\n"
            f"{reason_str}\n"
            f"👉 <a href=\"{raw.url}\">Consulter l'offre &amp; Postuler</a>"
        )
        return message

    def send_message(self, text: str, retries: int = 3) -> bool:
        if not self.is_configured():
            print("[TelegramNotifier] Clés TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquantes. Message non envoyé.")
            return False

        # Granular rate limiting: 1 message per second per chat
        elapsed = time.time() - self.last_sent_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            resp = requests.post(api_url, json=payload, timeout=10)

            # Circuit breaker on 429 Too Many Requests
            if resp.status_code == 429 and retries > 0:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                print(f"[TelegramNotifier] Rate limited (429). Pause de {retry_after} secondes.")
                time.sleep(retry_after)
                return self.send_message(text, retries=retries - 1)

            if resp.status_code == 200:
                self.last_sent_time = time.time()
                return True
            else:
                print(f"[TelegramNotifier] Erreur d'envoi ({resp.status_code}): {resp.text}")
                return False

        except Exception as e:
            print(f"[TelegramNotifier] Exception réseau : {e}")
            return False

    def notify_job(self, job: ProcessedJob) -> bool:
        msg = self.format_job_message(job)
        return self.send_message(msg)
