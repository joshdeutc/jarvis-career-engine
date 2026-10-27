import imaplib
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional
from src.models import ProcessedJob, PROFILE_LABELS


CANDIDATURES_ROOT = Path(r"C:\Users\jo\Documents\rapport_final\Candidatures")


class GmailAutomator:
    """
    100% free Gmail automation using standard Python libraries (smtplib + imaplib).
    Supports:
    1. Sending an HTML email digest of fresh matched offers directly to Joshua's inbox.
    2. Creating ready-to-send Gmail Drafts (in [Gmail]/Brouillons) with the tailored
       approach message and the recommended CV from Candidatures/ attached.
    """

    def __init__(
        self,
        gmail_user: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
    ):
        self.gmail_user = gmail_user or os.getenv("GMAIL_USER", "joshuanancey@gmail.com")
        self.gmail_app_password = gmail_app_password or os.getenv("GMAIL_APP_PASSWORD", "")

    def is_configured(self) -> bool:
        return bool(self.gmail_user and self.gmail_app_password)

    def send_daily_digest(self, jobs: List[ProcessedJob], recipient: Optional[str] = None) -> bool:
        """Sends an email digest of the newly retained jobs to Joshua's email address."""
        if not self.is_configured() or not jobs:
            return False

        to_addr = recipient or self.gmail_user
        msg = EmailMessage()
        msg["Subject"] = f"🎯 {len(jobs)} nouvelle(s) offre(s) fraîche(s) pour toi — Copilote UTC"
        msg["From"] = self.gmail_user
        msg["To"] = to_addr

        lines = [
            "Bonjour Joshua,\n",
            f"Voici les {len(jobs)} nouvelle(s) offre(s) fraîche(s) (hors stages/alternances, < 14 jours) retenues aujourd'hui :\n",
        ]
        for j in jobs:
            raw = j.raw
            ext = j.extraction
            prof = PROFILE_LABELS.get(ext.matched_profile, ext.matched_profile.value)
            lines.append(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏢 [{raw.company}] {raw.title} (Match {ext.match_score}%)\n"
                f"📌 Référence : {raw.id} | 🕒 {raw.date_posted or 'Récent'} | 📍 {raw.location or 'N/A'}\n"
                f"🎯 Profil : {prof} | 📎 CV conseillé : Candidatures/{ext.recommended_cv_folder or '5_Data_IA_Engineering'}\n"
                f"🔗 Lien direct : {raw.url}\n"
                f"🎓 Pitch CV : {ext.cv_pitch or ''}\n\n"
                f"✉️ Brouillon de message prêt à envoyer :\n{ext.cold_email_draft or ''}\n"
            )

        msg.set_content("\n".join(lines))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
                smtp.login(self.gmail_user, self.gmail_app_password)
                smtp.send_message(msg)
            print(f"[GmailAutomator] Digest envoyé avec succès à {to_addr} ({len(jobs)} offres).")
            return True
        except Exception as e:
            print(f"[GmailAutomator] Erreur d'envoi SMTP : {e}")
            return False

    def create_application_draft_in_gmail(
        self,
        job: ProcessedJob,
        recipient_email: str = "",
    ) -> bool:
        """
        Creates a ready-to-send Draft directly inside Joshua's Gmail 'Brouillons' folder
        via IMAP, pre-populated with the cold email text and the recommended CV attached.
        """
        if not self.is_configured():
            return False

        raw = job.raw
        ext = job.extraction

        msg = EmailMessage()
        msg["Subject"] = f"Candidature — {raw.title} (Réf: {raw.id}) — Joshua Nancey (Ingénieur UTC)"
        msg["From"] = self.gmail_user
        if recipient_email:
            msg["To"] = recipient_email

        body = ext.cold_email_draft or (
            f"Bonjour,\n\n"
            f"Je vous contacte au sujet de l'offre « {raw.title} » (Réf: {raw.id}) chez {raw.company}.\n"
            f"Ingénieur diplômé de l'UTC Compiègne (Génie Informatique, filière IAD & Label Mod'Math), "
            f"vous trouverez mon CV ci-joint.\n\n"
            f"Bien cordialement,\nJoshua Nancey\n+33 7 49 15 69 60"
        )
        msg.set_content(body)

        # Attach matching CV PDF if compiled, or .tex source info
        cv_folder = ext.recommended_cv_folder or "5_Data_IA_Engineering"
        folder_path = CANDIDATURES_ROOT / cv_folder
        if folder_path.exists():
            pdfs = list(folder_path.glob("*.pdf"))
            if pdfs:
                pdf_file = pdfs[0]
                msg.add_attachment(
                    pdf_file.read_bytes(),
                    maintype="application",
                    subtype="pdf",
                    filename="CV_Joshua_NANCEY_Ingenieur_UTC.pdf",
                )

        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
                imap.login(self.gmail_user, self.gmail_app_password)
                # Try French and English Gmail Drafts folder names
                for draft_box in ['"[Gmail]/Brouillons"', '"[Gmail]/Drafts"', "Drafts"]:
                    status, _ = imap.append(
                        draft_box,
                        "\\Draft",
                        imaplib.Time2Internaldate(time.time()),
                        msg.as_bytes(),
                    )
                    if status == "OK":
                        print(f"[GmailAutomator] Brouillon créé dans Gmail pour {raw.company} ({raw.id}).")
                        return True
            return False
        except Exception as e:
            print(f"[GmailAutomator] Erreur IMAP création brouillon : {e}")
            return False
