"""
Harvest Global & Europe (FR, DE, CH, NL, UK, SE, ES, IT) — Screening v2 :
  1. Collecte parallèle rapide sur 42 boards ATS (CEA, Inria, CERN Genève, Mistral, Helsing, Isomorphic Labs,
     DeepL, Black Forest Labs, Palantir, Jane Street, IMC, Celonis, Databricks, Datadog, Doctolib, Dataiku, Thales, Bosch, etc.).
  2. Pré-filtre déterministe gratuit (title_prefilter + hard_regex_findings) sur 100 % des offres collectées :
     - Rejette Stages/Alternances/Post-docs, Titres Seniors/Leads/Managers, Sécurité info classique, DevOps/Infra, BI/Data Analyst.
     - Rejette toute offre exigeant >= 2 ans d'expérience dans le texte, ou excluant explicitement les New Grads, ou hors UE sans sponsoring.
  3. Double Juge IA Groq multi-modèles (openai/gpt-oss-120b + qwen/qwen3.8-27b + openai/gpt-oss-20b) avec citations vérifiées
     mot pour mot dans l'annonce (`evidence_is_grounded`) + Cache persistant (`eval_cache.json`).
  4. Pondération Multi-Critères Jarvis (Tier S/A/B/C × Bonus Entreprise + Bonus 0-1 an) et génération de `offres_retenues.html`.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import sys
import time
from typing import Dict, List, Tuple
import yaml
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.ats import get_connector
from src.models import JobRaw, ProcessedJob
from src.report_generator import generate_html_dashboard
from src.screening import (
    JUNIOR_SIGNAL,
    Decision,
    EvalCache,
    Screener,
    decision_to_processed_job,
    find_years_requirement,
    hard_regex_findings,
    title_prefilter,
)
from src.storage import StorageManager

PRIORITY_ROLES_RX = re.compile(
    r"\b(operations research|recherche opérationnelle|optimisation|optimization|stochastic|stochastique|quant\w*|"
    r"model validation|model risk|decision science|value engineer|solutions? architect|application engineer|forward deployed|"
    r"deployment strategist|ai safety|alignment|trustworthy|ingénieur[- ]chercheur|research engineer|research scientist|"
    r"data scientist|machine learning|ai engineer|ml engineer|chef de projet|product manager|product owner)\b",
    re.I,
)

FR_CH_DE_LOC_RX = re.compile(
    r"\b(france|paris|saclay|grenoble|lyon|toulouse|nantes|bordeaux|lille|rennes|sophia|annecy|montpellier|"
    r"switzerland|suisse|schweiz|zurich|zürich|geneva|genève|lausanne|basel|cern|"
    r"germany|deutschland|munich|münchen|berlin|freiburg|cologne|köln|frankfurt|stuttgart|hamburg)\b",
    re.I,
)


def _fetch_company(comp: Dict) -> Tuple[str, List[JobRaw], float]:
    cname = comp.get("name", "Inconnue")
    t0 = time.time()
    try:
        conn = get_connector(comp)
        if not conn:
            return cname, [], 0.0
        jobs = conn.fetch_jobs()
        return cname, jobs, time.time() - t0
    except Exception as e:
        print(f"  [Erreur ATS] {cname}: {e}", flush=True)
        return cname, [], time.time() - t0


def main() -> None:
    t_start = time.time()
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY absente du fichier .env")

    with open("config/companies.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    enabled_companies = [c for c in cfg.get("companies", []) if c.get("enabled", True)]
    print("====================================================================================")
    print(f"🌍 JARVIS HARVEST v2 — {len(enabled_companies)} sources ATS (France, Allemagne, Suisse, NL, UK & Europe)")
    print("🛡️ Garde-fous : >= 2 ans = REJETÉ | New Grads exclus = REJETÉ | Citations vérifiées mot pour mot")
    print("🤖 Juges IA Groq : openai/gpt-oss-120b + qwen/qwen3.8-27b + openai/gpt-oss-20b (Passe A + Passe B)")
    print("====================================================================================\n", flush=True)

    # 1. Collecte parallèle de toutes les entreprises
    raw_by_company: Dict[str, List[JobRaw]] = {}
    total_raw = 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(_fetch_company, comp): comp.get("name", "?") for comp in enabled_companies}
        for fut in as_completed(futs):
            cname, jobs, dt = fut.result()
            raw_by_company[cname] = jobs
            total_raw += len(jobs)
            if jobs:
                print(f"  📡 {cname:58s} : {len(jobs):3d} offre(s) ({dt:.1f}s)", flush=True)

    print(f"\n📥 Total brut collecté : {total_raw} offres sur {len(enabled_companies)} sources.", flush=True)

    # 2. Pré-filtrage déterministe gratuit sur 100 % des offres
    rejected_title = 0
    rejected_hard_regex = 0
    audit_log: List[Dict] = []
    survivors_by_company: Dict[str, List[JobRaw]] = {}

    for cname, jobs in raw_by_company.items():
        comp_survivors: List[JobRaw] = []
        for j in jobs:
            tp = title_prefilter(j)
            if tp is not None:
                rejected_title += 1
                continue
            hr = hard_regex_findings(j)
            if hr:
                rejected_hard_regex += 1
                audit_log.append(
                    {
                        "id": j.id,
                        "company": j.company,
                        "title": j.title,
                        "location": j.location,
                        "stage": "hard_regex",
                        "accepted": False,
                        "reasons": [f"{code}: {ev}" for code, ev in hr],
                    }
                )
                continue
            comp_survivors.append(j)
        if comp_survivors:
            survivors_by_company[cname] = comp_survivors

    # 3. Construction du pool candidat sans le plafond aveugle [:2]
    #    - Toute offre Junior/Graduate/New Grad/VIE/PhD ou issue de CEA/Inria/CERN est conservée.
    #    - Pour les autres offres d'un même board, on garde jusqu'à 3 offres les plus pertinentes par entreprise.
    candidates_pool: List[JobRaw] = []
    seen_ids = set()

    for cname, survs in survivors_by_company.items():
        is_research_board = any(w in cname.lower() for w in ["cea", "inria", "cern"])
        survs.sort(
            key=lambda j: (
                0 if (JUNIOR_SIGNAL.search(j.title or "") or is_research_board) else 1,
                0 if FR_CH_DE_LOC_RX.search(j.location or "") else 1,
                0 if PRIORITY_ROLES_RX.search(j.title or "") else 1,
                find_years_requirement(j.description_text or "")[0],
            )
        )
        non_junior_count = 0
        for j in survs:
            if j.id in seen_ids:
                continue
            is_jr = bool(JUNIOR_SIGNAL.search(j.title or ""))
            if not is_research_board and not is_jr:
                if non_junior_count >= 3:
                    continue
                non_junior_count += 1
            seen_ids.add(j.id)
            candidates_pool.append(j)

    # Tri global : priorité aux postes Junior/Graduate + CEA/Inria/CERN + zone France / Suisse / Allemagne
    candidates_pool.sort(
        key=lambda j: (
            0 if (JUNIOR_SIGNAL.search(j.title or "") or any(w in (j.company or "").lower() for w in ["cea", "inria", "cern"])) else 1,
            0 if FR_CH_DE_LOC_RX.search(j.location or "") else 1,
            0 if PRIORITY_ROLES_RX.search(j.title or "") else 1,
        )
    )

    print(
        f"🧹 Filtre Déterministe Gratuit : {rejected_title} écartées sur titre | "
        f"{rejected_hard_regex} écartées par Regex stricte (>=2 ans, New Grads exclus, hors UE sans sponsor).\n"
        f"⚖️ {len(candidates_pool)} offres candidates passent devant les Juges IA Groq (Cache + Passe A + Passe B)...\n",
        flush=True,
    )

    # 4. Vérification du cache + Jugement multi-modèles Groq (plafonné à 45 nouvelles offres hors cache par run pour rester < 60s)
    cache = EvalCache("eval_cache.json")
    screener = Screener(
        api_key=api_key,
        models=["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
        tpm=8000,
    )

    decisions: Dict[str, Decision] = {}
    to_judge: List[JobRaw] = []
    for j in candidates_pool:
        cached = cache.get(j)
        if cached and "decision" in cached:
            d_dict = cached["decision"]
            decisions[j.id] = Decision(**d_dict)
        else:
            if len(to_judge) < 40:
                to_judge.append(j)

    # Ne garder dans candidates_pool que celles qui ont une décision (en cache ou jugées sur ce run)
    active_ids = set(decisions.keys()) | {j.id for j in to_judge}
    candidates_pool = [j for j in candidates_pool if j.id in active_ids]

    if to_judge:
        print(f"   🔄 {len(to_judge)} offres nouvelles à évaluer par Groq ({len(decisions)} déjà en cache)...", flush=True)
        fresh_decisions = screener.screen(to_judge)
        for j in to_judge:
            d = fresh_decisions[j.id]
            decisions[j.id] = d
            if "no-cache" not in d.notes:
                cache.put(j, d)
        cache.save()
    else:
        print(f"   ⚡ 100 % des {len(decisions)} offres candidates étaient déjà en cache (`eval_cache.json`).", flush=True)

    # 5. Assemblage des résultats, stockage et rapport HTML
    storage = StorageManager("seen_jobs.json")
    all_retained: List[ProcessedJob] = []
    llm_rejected = 0

    print("\n--- RÉSULTATS DÉTAILLÉS DU JUGEMENT IA ---", flush=True)
    for j in candidates_pool:
        d = decisions[j.id]
        proc = decision_to_processed_job(j, d)
        ext = proc.extraction

        audit_log.append(
            {
                "id": j.id,
                "company": j.company,
                "title": j.title,
                "location": j.location,
                "url": j.url,
                "stage": "groq_multi_judge",
                "accepted": d.accepted,
                "family": d.family,
                "years": d.years,
                "judged_by": d.judged_by,
                "reasons": d.reasons,
                "notes": d.notes,
            }
        )

        storage.mark_seen(
            j.id,
            {
                "company": j.company,
                "title": j.title,
                "url": j.url,
                "location": j.location,
                "ats_type": j.ats_type,
                "matched_profile": ext.matched_profile.value,
                "is_relevant": ext.is_relevant,
                "match_score": ext.match_score,
                "years_of_experience": ext.years_of_experience,
            },
        )

        if d.accepted and ext.is_relevant:
            all_retained.append(proc)
            print(
                f"  ✅ [RETENU | {ext.match_score:2d}% | {ext.tier_label} | Exp={d.years}a | {d.family}] "
                f"{j.company} — {j.title} ({j.location})",
                flush=True,
            )
        else:
            llm_rejected += 1
            reason_short = " ; ".join(d.reasons)[:110] if d.reasons else "Hors cible"
            print(
                f"  ❌ [REJETÉ | Exp={d.years}a | {d.family}] "
                f"{j.company} — {j.title} ({j.location}) -> {reason_short}",
                flush=True,
            )

    storage.save()
    with open("audit_rejets_detaille.json", "w", encoding="utf-8") as f:
        json.dump(audit_log, f, ensure_ascii=False, indent=2)

    all_retained.sort(key=lambda x: x.extraction.match_score, reverse=True)
    dash_path = generate_html_dashboard(all_retained, "offres_retenues.html")

    total_time = time.time() - t_start
    print("\n====================================================================================")
    print(f"📊 BILAN COMPLET EN {total_time:.1f} SECONDES :")
    print(f"   • Offres brutes scannées (FR, DE, CH, NL, UK, EU) : {total_raw}")
    print(f"   • Écartées gratuitement (Titre / Regex stricte)   : {rejected_title + rejected_hard_regex}")
    print(f"   • Écartées par les Juges IA Groq (citations)      : {llm_rejected}")
    print(f"   • Offres RETENUES et vérifiées (0 à 1 an max)     : {len(all_retained)}")
    print(f"   • Dashboard mis à jour                            : {dash_path}")
    print("====================================================================================")


if __name__ == "__main__":
    main()
