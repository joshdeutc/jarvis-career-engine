import os
import sys
import yaml
from collections import Counter
from dotenv import load_dotenv

# Ensure utf-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.ats import get_connector
from src.extractor import LLMExtractor
from src.telegram_bot import TelegramNotifier
from src.report_generator import generate_html_dashboard, send_discord_notification
from src.mailer import GmailAutomator
from src.storage import StorageManager
from src.models import PROFILE_LABELS


def load_config(config_path: str = "config/companies.yaml") -> dict:
    if not os.path.exists(config_path):
        print(f"[Error] Configuration file '{config_path}' not found.")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run():
    load_dotenv()
    print("==================================================")
    print("🚀 Démarrage du Copilote Carrière — Joshua Nancey (UTC)")
    print("🎓 Profil : Ingénieur Diplômé GI / Mod'Math (Hors Stages/Alternances)")
    print("==================================================")

    config = load_config()
    companies = config.get("companies", [])

    storage = StorageManager("seen_jobs.json")
    extractor = LLMExtractor()
    notifier = TelegramNotifier()
    mailer = GmailAutomator()
    discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")

    print(f"📁 Base d'état : {len(storage.data)} offres déjà enregistrées.")
    print(f"🤖 LLM configuré : {f'Oui (Groq {extractor.model})' if extractor.is_configured() else 'Non (Fallback Heuristique actif)'}")
    print(f"🌐 Dashboard HTML : Actif (offres_retenues.html)")
    print(f"✉️  Gmail Automator : {'Actif (' + mailer.gmail_user + ')' if mailer.is_configured() else 'Non configuré (GMAIL_APP_PASSWORD optionnel)'}")
    print(f"💬 Discord Webhook : {'Actif' if discord_url else 'Non configuré (Optionnel)'}")
    print(f"📢 Telegram Bot : {'Actif' if notifier.is_configured() else 'Non configuré (Optionnel)'}\n")

    total_scanned = 0
    total_new = 0
    total_relevant = 0
    total_notified = 0
    profile_counts = Counter()
    retained_jobs = []

    for comp_cfg in companies:
        if not comp_cfg.get("enabled", True):
            continue

        comp_name = comp_cfg.get("name", "Inconnue")
        ats_type = comp_cfg.get("ats", "unknown")
        print(f"🔍 Exploration de {comp_name} ({ats_type})...")

        connector = get_connector(comp_cfg)
        if not connector:
            continue

        raw_jobs = connector.fetch_jobs()
        total_scanned += len(raw_jobs)
        print(f"   -> {len(raw_jobs)} offres récupérées au total.")

        new_jobs = [j for j in raw_jobs if not storage.is_seen(j.id)]
        # Pre-filter out obvious stages/senior titles before capping per-company LLM calls
        candidates = [j for j in new_jobs if extractor._fast_pre_reject(j) is None][:6]
        print(f"   -> {len(new_jobs)} nouvelles offres ({len(candidates)} pré-qualifiées Junior/Intermédiaire à analyser par le LLM).")

        for job in candidates:
            total_new += 1
            processed = extractor.extract_job(job)
            ext = processed.extraction

            # Store in persistent state
            storage.mark_seen(job.id, {
                "company": job.company,
                "title": job.title,
                "url": job.url,
                "ats_type": job.ats_type,
                "matched_profile": ext.matched_profile.value,
                "is_relevant": ext.is_relevant,
                "match_score": ext.match_score,
            })

            if ext.is_relevant:
                total_relevant += 1
                retained_jobs.append(processed)
                profile_counts[ext.matched_profile] += 1
                label = PROFILE_LABELS.get(ext.matched_profile, ext.matched_profile.value)
                stack_str = ", ".join(ext.tech_stack) if ext.tech_stack else "N/A"
                print(
                    f"   ✨ [{ext.match_score}%] {label}\n"
                    f"      🏢 {job.company} — {job.title} [{ext.contract_type.value}] (Exp: {ext.years_of_experience}a)\n"
                    f"      📌 Réf: {job.id} | 📍 {job.location or 'N/A'} | 🛠️ Stack: {stack_str}\n"
                    f"      💡 {ext.relevance_reason}\n"
                    f"      🎓 Conseil CV : {ext.cv_pitch or 'N/A'}\n"
                    f"      🔗 {job.url}"
                )
                if mailer.is_configured():
                    mailer.create_application_draft_in_gmail(processed)
                if discord_url:
                    if send_discord_notification(processed, discord_url):
                        total_notified += 1
                if notifier.is_configured():
                    if notifier.notify_job(processed):
                        total_notified += 1

    # Save state and generate interactive HTML dashboard if new relevant jobs found
    storage.save()
    if retained_jobs:
        dash_path = generate_html_dashboard(retained_jobs, "offres_retenues.html")
        print(f"\n🌐 Dashboard interactif généré : {dash_path}")
        if mailer.is_configured():
            if mailer.send_daily_digest(retained_jobs):
                total_notified += len(retained_jobs)

    print("\n==================================================")
    print("📊 Bilan de l'exécution :")
    print(f"   • Offres scannées            : {total_scanned}")
    print(f"   • Nouvelles offres analysées : {total_new}")
    print(f"   • Offres retenues (Junior)   : {total_relevant}")
    if profile_counts:
        print("   • Répartition par profil :")
        for prof, count in profile_counts.items():
            print(f"     - {PROFILE_LABELS.get(prof, prof.value)} : {count}")
    print(f"   • Alertes envoyées           : {total_notified}")
    print(f"   • Total dans la base         : {len(storage.data)}")
    print("==================================================")


if __name__ == "__main__":
    run()
