import html
import os
import urllib.parse
from datetime import datetime
from typing import List, Optional
import requests
from src.models import ProcessedJob, PROFILE_LABELS, ProfileCategory


PROFILE_COLORS = {
    ProfileCategory.RO_MODELISATION_QUANT: "#eab308",  # Gold (Tier S: RO / Modélisation / Quant / Safe AI)
    ProfileCategory.ARCHITECTE_AI_DATA: "#a855f7",     # Purple (Tier S: Solutions Architect / Application Engineer)
    ProfileCategory.CHEF_DE_PROJET_PM: "#06b6d4",      # Cyan (Tier A: Chef de Projet R&D / Product Owner)
    ProfileCategory.RECHERCHE_RD_CIFRE: "#10b981",     # Emerald (Tier A: Recherche R&D / CEA / Inria)
    ProfileCategory.VIE_INTERNATIONAL: "#ec4899",      # Pink (Tier A: V.I.E & International)
    ProfileCategory.DATA_SCIENCE_ENGINEER: "#3b82f6",  # Blue (Tier B: ML Engineer / Data Science classique)
    ProfileCategory.TECH_SALES_PRESALES: "#f97316",    # Orange (Tier B: Pre-Sales / Sales Engineer)
    ProfileCategory.CONSULTANT_DATA_IA: "#f59e0b",     # Amber (Tier C: Consulting Data & IA - Filet de sécurité)
    ProfileCategory.SOFTWARE_DATA_ENG: "#64748b",      # Slate (Tier C: Data / Software Engineer - Filet de sécurité)
    ProfileCategory.HORS_CIBLE: "#6b7280",             # Gray
}


def send_discord_notification(job: ProcessedJob, webhook_url: Optional[str] = None) -> bool:
    """Sends a rich Discord Embed with clickable link, job reference, and personalized UTC CV pitch."""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        return False

    raw = job.raw
    ext = job.extraction
    profile_label = PROFILE_LABELS.get(ext.matched_profile, ext.matched_profile.value)
    color_hex = PROFILE_COLORS.get(ext.matched_profile, "#3b82f6").lstrip("#")
    color_int = int(color_hex, 16)

    stack_str = ", ".join(ext.tech_stack) if ext.tech_stack else "Non spécifiée"

    embed = {
        "title": f"[{raw.company}] {raw.title} ({ext.match_score}%)",
        "url": raw.url,
        "color": color_int,
        "description": (
            f"**Profil :** {profile_label}\n"
            f"**Pondération :** `{ext.score_breakdown or 'Standard'}`\n"
            f"**Justification :** {ext.relevance_reason}"
        ),
        "fields": [
            {"name": "📌 Référence", "value": f"`{raw.id}`", "inline": True},
            {"name": "📄 Contrat", "value": f"`{ext.contract_type.value}`", "inline": True},
            {"name": "📍 Lieu", "value": raw.location or "Non spécifié", "inline": True},
            {"name": "🛠️ Stack Technique", "value": stack_str, "inline": False},
        ],
        "footer": {"text": f"Source ATS : {raw.ats_type} • Copilote Carrière Joshua Nancey (UTC)"},
    }

    if ext.cv_pitch:
        embed["fields"].append({
            "name": "🎓 Quoi mettre en avant (CV UTC / Stages)",
            "value": ext.cv_pitch[:1024],
            "inline": False,
        })

    try:
        resp = requests.post(url, json={"embeds": [embed]}, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"[DiscordNotifier] Erreur : {e}")
        return False


def generate_html_dashboard(jobs: List[ProcessedJob], output_path: str = "offres_retenues.html") -> str:
    """
    Generates a standalone, interactive HTML dashboard with filters by Tier & Profile,
    transparent weighted score breakdown, clickable links, and personalized UTC CV pitches.
    """
    for j in jobs:
        if not j.extraction.score_breakdown:
            j.extraction.apply_weighted_coefficients(j.raw.company)

    sorted_jobs = sorted(jobs, key=lambda j: j.extraction.match_score, reverse=True)
    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")

    cards_html = []
    for idx, item in enumerate(sorted_jobs):
        raw = item.raw
        ext = item.extraction
        prof_label = PROFILE_LABELS.get(ext.matched_profile, ext.matched_profile.value)
        badge_color = PROFILE_COLORS.get(ext.matched_profile, "#3b82f6")
        tier_str = ext.tier_label or "Tier B"
        stack_badges = "".join(
            f'<span class="tech-tag">{html.escape(t)}</span>' for t in ext.tech_stack
        ) or '<span class="tech-tag muted">Non spécifiée</span>'

        cv_folder = ext.recommended_cv_folder or "5_Data_IA_Engineering"
        pitch_html = (
            f'<div class="cv-pitch">'
            f'<strong>🎓 Stratégie CV (Dossier conseillé : <code>Candidatures/{html.escape(cv_folder)}</code>) :</strong><br>'
            f'{html.escape(ext.cv_pitch)}</div>'
            if ext.cv_pitch
            else ""
        )

        breakdown_html = (
            f'<div class="score-formula">⚖️ <strong>Pondération Jarvis :</strong> <code>{html.escape(ext.score_breakdown)}</code></div>'
            if ext.score_breakdown
            else ""
        )

        email_draft = ext.cold_email_draft or (
            f"Objet : Candidature — {raw.title} (Réf: {raw.id}) — Joshua Nancey (Ingénieur UTC)\n\n"
            f"Bonjour,\n\nJe vous contacte au sujet de l'offre « {raw.title} » (Réf: {raw.id}) chez {raw.company}.\n"
            f"Jeune diplômé Ingénieur de l'UTC Compiègne (Génie Informatique, filière IAD & Label Mod'Math), "
            f"j'ai récemment mené deux projets R&D chez Epiconcept (Deep Learning Vision GMIC avec garanties statistiques d'abstention SGR & extraction clinique par LLMs sous contrainte VRAM 40 Go) "
            f"ainsi qu'un stage R&D chez Aubay Innov' (détection d'anomalies contextuelles sur tableaux mixtes via PyTorch Tabular et Isolation Forest).\n\n"
            f"Vous trouverez mon CV ci-joint. Seriez-vous disponible pour un court échange cette semaine ?\n\n"
            f"Bien cordialement,\nJoshua Nancey\n+33 7 49 15 69 60"
        )
        subject_str = f"Candidature — {raw.title} (Réf: {raw.id}) — Joshua Nancey (Ingénieur UTC)"
        gmail_compose_url = (
            "https://mail.google.com/mail/?view=cm&fs=1"
            f"&su={urllib.parse.quote(subject_str)}"
            f"&body={urllib.parse.quote(email_draft)}"
        )

        email_box_html = f"""
        <div class="email-draft-box">
            <div class="email-draft-header">
                <strong>✉️ Brouillon de Mail / Message d'approche (prêt à envoyer) :</strong>
                <div class="email-draft-btns">
                    <button class="copy-btn" onclick="copyDraft('draft-{idx}', this)">📋 Copier le message</button>
                    <a class="gmail-btn" href="{html.escape(gmail_compose_url)}" target="_blank" rel="noopener noreferrer">
                        📨 Ouvrir pré-rempli dans Gmail ↗
                    </a>
                </div>
            </div>
            <pre id="draft-{idx}" class="email-pre">{html.escape(email_draft)}</pre>
        </div>
        """

        abroad_tag = '<span class="abroad-tag">🌍 International / V.I.E</span>' if ext.is_abroad_or_vie else ""
        date_str = raw.date_posted or "Récent"

        card = f"""
        <div class="job-card" data-profile="{ext.matched_profile.value}" data-tier="{html.escape(tier_str)}">
            <div class="card-header">
                <span class="profile-badge" style="background:{badge_color}20; color:{badge_color}; border:1px solid {badge_color}50;">
                    {html.escape(prof_label)}
                </span>
                <span class="score-badge">Score Pondéré : {ext.match_score}%</span>
            </div>
            <h2 class="job-title">
                <a href="{html.escape(raw.url)}" target="_blank" rel="noopener noreferrer">
                    {html.escape(raw.title)} ↗
                </a>
            </h2>
            <div class="meta-row">
                <span>🏢 <strong>{html.escape(raw.company)}</strong></span>
                <span>📍 {html.escape(raw.location or 'Non spécifié')}</span>
                <span>🕒 <strong>{html.escape(date_str)}</strong></span>
                <span>📄 <code>{html.escape(ext.contract_type.value)}</code></span>
                <span>⏳ Exp: {ext.years_of_experience} an(s)</span>
                <span>📌 Réf: <code>{html.escape(raw.id)}</code></span>
                {abroad_tag}
            </div>
            {breakdown_html}
            <p class="reason">💡 {html.escape(ext.relevance_reason)}</p>
            <div class="tech-row">{stack_badges}</div>
            {pitch_html}
            {email_box_html}
            <div class="card-actions">
                <a class="apply-btn" href="{html.escape(raw.url)}" target="_blank" rel="noopener noreferrer">
                    Consulter l'offre &amp; Postuler sur le site officiel ({html.escape(raw.company)}) →
                </a>
            </div>
        </div>
        """
        cards_html.append(card)

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Copilote Carrière Jarvis — Joshua Nancey (Ingénieur UTC)</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --border: #334155;
        }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
        }}
        .container {{ max-width: 1080px; margin: 0 auto; }}
        header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
        }}
        h1 {{ margin: 0 0 0.4rem 0; font-size: 1.6rem; }}
        .subtitle {{ color: var(--muted); font-size: 0.95rem; margin: 0; }}
        .legend-box {{
            background: #0f172a90;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.9rem 1.2rem;
            margin-top: 1rem;
            font-size: 0.86rem;
            color: #cbd5e1;
        }}
        .filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }}
        .filter-btn {{
            background: var(--card);
            color: var(--text);
            border: 1px solid var(--border);
            padding: 0.5rem 1rem;
            border-radius: 999px;
            cursor: pointer;
            font-size: 0.86rem;
            transition: all 0.15s;
        }}
        .filter-btn.active, .filter-btn:hover {{
            background: var(--accent);
            color: #0f172a;
            border-color: var(--accent);
            font-weight: 600;
        }}
        .job-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.4rem;
            margin-bottom: 1.2rem;
            transition: transform 0.15s, border-color 0.15s;
        }}
        .job-card:hover {{ border-color: var(--accent); }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 0.6rem;
        }}
        .profile-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
        }}
        .score-badge {{
            background: #10b98125;
            color: #34d399;
            border: 1px solid #10b98150;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.85rem;
        }}
        .score-formula {{
            font-size: 0.84rem;
            color: #e2e8f0;
            background: #0f172a80;
            padding: 0.4rem 0.75rem;
            border-radius: 6px;
            margin-bottom: 0.6rem;
            border-left: 3px solid #eab308;
        }}
        .job-title {{ margin: 0.3rem 0 0.6rem 0; font-size: 1.25rem; }}
        .job-title a {{ color: var(--text); text-decoration: none; }}
        .job-title a:hover {{ color: var(--accent); text-decoration: underline; }}
        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            color: var(--muted);
            font-size: 0.88rem;
            margin-bottom: 0.7rem;
        }}
        code {{
            background: #0f172a;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            color: #38bdf8;
        }}
        .reason {{ margin: 0.6rem 0; font-size: 0.95rem; }}
        .tech-row {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.8rem 0; }}
        .tech-tag {{
            background: #0f172a;
            border: 1px solid var(--border);
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-size: 0.8rem;
            color: #e2e8f0;
        }}
        .cv-pitch {{
            background: #0f172a90;
            border-left: 3px solid #38bdf8;
            padding: 0.8rem 1rem;
            border-radius: 0 8px 8px 0;
            font-size: 0.9rem;
            color: #cbd5e1;
            margin: 0.9rem 0;
        }}
        .card-actions {{ margin-top: 1rem; }}
        .apply-btn {{
            display: inline-block;
            background: #38bdf8;
            color: #0f172a;
            font-weight: 600;
            text-decoration: none;
            padding: 0.55rem 1.1rem;
            border-radius: 8px;
            font-size: 0.9rem;
        }}
        .apply-btn:hover {{ background: #7dd3fc; }}
        .abroad-tag {{
            background: #ec489925;
            color: #f472b6;
            padding: 0.1rem 0.5rem;
            border-radius: 4px;
            font-weight: 600;
        }}
        .email-draft-box {{
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.85rem 1rem;
            margin: 0.9rem 0;
        }}
        .email-draft-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 0.6rem;
            font-size: 0.9rem;
        }}
        .email-draft-btns {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}
        .copy-btn, .gmail-btn {{
            background: #1e293b;
            color: #e2e8f0;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 0.3rem 0.7rem;
            font-size: 0.82rem;
            cursor: pointer;
            text-decoration: none;
            font-weight: 500;
        }}
        .copy-btn:hover, .gmail-btn:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}
        .email-pre {{
            margin: 0;
            white-space: pre-wrap;
            font-family: inherit;
            font-size: 0.88rem;
            color: #cbd5e1;
            line-height: 1.45;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 Copilote Carrière Jarvis — Joshua Nancey</h1>
            <p class="subtitle">
                Ingénieur UTC (Génie Informatique • Mod'Math) • R&amp;D Modélisation, Vision &amp; LLMs (Epiconcept, Aubay, BMBI)<br>
                Dernière mise à jour : {now_str} • <strong>{len(sorted_jobs)} offre(s) qualifiée(s) et classées par Score Pondéré</strong>
            </p>
            <div class="legend-box">
                <strong>⚖️ Barème des Coefficients Jarvis (On garde tout ce qui est viable, on classe du Graal au Filet de sécurité) :</strong><br>
                • <strong>Mission :</strong> <code>Tier S (×1.25)</code> RO / Modélisation Stochastique / Quant Risk / Validation IA &amp; Solutions Architect • <code>Tier A (×1.12)</code> Chef de Projet R&amp;D / Ingénieur-Chercheur / V.I.E • <code>Tier B (×0.95)</code> Data Scientist / ML Engineer &amp; Pre-Sales Tech • <code>Tier C (×0.80 - Filet de sécurité)</code> Consulting ESN &amp; Data/Software Engineering.<br>
                • <strong>Entreprise (Congés/RTT &amp; Salaire) :</strong> <code>+10 pts</code> Grands Groupes Royaux / Banques / Centres R&amp;D (42–48j RTT/Congés) • <code>+7 pts</code> Éditeurs Tech &amp; Pépites RO • <code>0 pt</code> Standard • <code>-12 pts</code> ESN / Presta (conservées en bas de liste).
            </div>
        </header>

        <div class="filters">
            <button class="filter-btn active" onclick="filterJobs('ALL', this)">Toutes ({len(sorted_jobs)})</button>
            <button class="filter-btn" onclick="filterTier('Tier S', this)">⭐ Tier S (×1.25 — Graal RO/Quant &amp; Archi)</button>
            <button class="filter-btn" onclick="filterTier('Tier A', this)">🔥 Tier A (×1.12 — PM R&amp;D / CEA / V.I.E)</button>
            <button class="filter-btn" onclick="filterTier('Tier B', this)">✅ Tier B (×0.95 — Data Scientist &amp; Pre-Sales)</button>
            <button class="filter-btn" onclick="filterTier('Tier C', this)">🛡️ Tier C (×0.80 — Filet ESN / Data Eng)</button>
            <button class="filter-btn" onclick="filterJobs('RO_MODELISATION_QUANT', this)">📐 RO / Stochastique / Quant</button>
            <button class="filter-btn" onclick="filterJobs('ARCHITECTE_AI_DATA', this)">🏗️ Solutions Architect / App Eng</button>
            <button class="filter-btn" onclick="filterJobs('CHEF_DE_PROJET_PM', this)">📋 Chef de Projet R&amp;D / PO</button>
            <button class="filter-btn" onclick="filterJobs('RECHERCHE_RD_CIFRE', this)">🧪 Recherche R&amp;D (CEA, Inria)</button>
        </div>

        <div id="jobs-list">
            {''.join(cards_html) if cards_html else '<p>Aucune nouvelle offre retenue sur cette exécution.</p>'}
        </div>
    </div>

    <script>
        function filterJobs(profile, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.job-card').forEach(card => {{
                if (profile === 'ALL' || card.dataset.profile === profile) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
        function filterTier(tier, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.job-card').forEach(card => {{
                if (card.dataset.tier === tier) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
        function copyDraft(id, btn) {{
            const text = document.getElementById(id).innerText;
            navigator.clipboard.writeText(text).then(() => {{
                const orig = btn.innerText;
                btn.innerText = '✅ Copié !';
                setTimeout(() => {{ btn.innerText = orig; }}, 2000);
            }});
        }}
    </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return os.path.abspath(output_path)
