import os
import re
from typing import Optional
from groq import Groq
import instructor
from src.models import (
    JobRaw,
    JobExtraction,
    ProcessedJob,
    ProfileCategory,
    ContractType,
)


EXCLUDED_TITLE_PATTERNS = re.compile(
    r"\b(stage|stagiaire|intern|internship|intership|alternance|alternant|apprentissage|apprenti|apprentice|co-op|coop|post-doc|postdoc|post-doctoral|postdoctoral)\b",
    re.IGNORECASE,
)

# Titres trop seniors pour un jeune diplômé UTC (Senior, Staff, Principal, Lead, Leadership, Director, Manager, niveaux III/IV)
TOO_SENIOR_TITLE_PATTERNS = re.compile(
    r"\b(senior|sénior|sr\.?|director|directeur|directrice|head of|vp|vice president|principal|staff|distinguished|lead|leader|leadership|engineering manager|manager,|solutions architecture manager|architect manager|regional manager|country manager|iii|iv)\b",
    re.IGNORECASE,
)

# Mots-clés dans le titre qui signalent un poste explicitement pensé pour Jeune Diplômé / Junior (0-2 ans)
JUNIOR_FRIENDLY_TITLE_PATTERNS = re.compile(
    r"\b(junior|graduate|new grad|early career|entry level|entry-level|associate|jeune diplômé|jeune diplome|débutant|debutant|v\.i\.e|vie|fellow|fellows|resident|phd|doctorat|thèse|cifre)\b",
    re.IGNORECASE,
)

# Missions "Vraiment Horribles" ou Hors-Métier à dégager d'office (Support N1/N2, Marketing, Design, Légal, RH, etc.)
HORRIBLE_JOB_TITLE_PATTERNS = re.compile(
    r"\b(helpdesk|support n1|support n2|technicien support|technicien informatique|testeur manuel|recetteur fonctionnel|téléprospecteur|teleprospecteur|comptable|accountant|tax|payroll|juriste|legal|counsel|paralegal|rh|ressources humaines|recruiter|recruiting|talent acquisition|people partner|assistant administratif|executive assistant|office manager|secrétaire|manutentionnaire|salesforce|servicenow|product designer|brand designer|graphic designer|ux designer|ui designer|product marketing|field marketing|content marketing|events marketing|communications|public relations|copywriter|facilities|workplace)\b",
    re.IGNORECASE,
)

# Regex d'extraction du nombre d'années d'expérience exigées dans la description (EN + FR, chiffres + lettres)
EXP_RANGE_REGEX = re.compile(
    r"\b(\d{1,2})\s*(?:-|–|to|à)\s*(\d{1,2})\s*\+?\s*(?:years?|ans?)\s+(?:of\s+)?(?:[\w\-]+\s+){0,5}?(?:experience|expérience|expériences)\b",
    re.IGNORECASE,
)
EXP_PLUS_REGEX = re.compile(
    r"\b(\d{1,2})\s*\+?\s*(?:years?|ans?)\s+(?:of\s+|d['’]|in\s+)?(?:[\w\-,/]+\s+){0,6}?(?:experience|expérience|expériences|background|track record|role|roles)\b",
    re.IGNORECASE,
)
EXP_MIN_REGEX = re.compile(
    r"\b(?:minimum|at least|min\.?|au moins|justifiant de)\s+(?:of\s+)?(\d{1,2})\s*\+?\s*(?:years?|ans?)\b",
    re.IGNORECASE,
)
EXP_WORDS_SENIOR_REGEX = re.compile(
    r"\b(three|four|five|six|seven|eight|nine|ten|trois|quatre|cinq|six|sept|huit|dix)\s*\+?\s*(?:or more\s+)?(?:years?|ans?)\s+(?:of\s+|d['’])?(?:[\w\-]+\s+){0,5}?(?:experience|expérience|expériences)\b",
    re.IGNORECASE,
)


def extract_required_years_from_text(title: str, description: str) -> int:
    """
    Extrait de manière déterministe le nombre minimum d'années d'expérience exigées
    dans la description de l'offre (en anglais et en français).
    Retourne 0 si aucune exigence chiffrée n'est trouvée ou si le titre est explicitement Junior/Graduate.
    """
    if JUNIOR_FRIENDLY_TITLE_PATTERNS.search(title):
        return 0

    text = (description or "")[:5000]
    if not text:
        return 0

    candidates: list[int] = []

    if EXP_WORDS_SENIOR_REGEX.search(text):
        candidates.append(3)

    for m in EXP_RANGE_REGEX.finditer(text):
        low = int(m.group(1))
        if 1 <= low <= 15:
            candidates.append(low)

    for m in EXP_PLUS_REGEX.finditer(text):
        val = int(m.group(1))
        if 1 <= val <= 15:
            candidates.append(val)

    for m in EXP_MIN_REGEX.finditer(text):
        val = int(m.group(1))
        if 1 <= val <= 15:
            candidates.append(val)

    if not candidates:
        return 0

    # On prend la borne basse des exigences d'expérience mentionnées dans l'offre
    return min(candidates)


JOSHUA_BIO_CONTEXT = """
IDENTITÉ & FORMATION DE JOSHUA NANCEY :
- Ingénieur diplômé en Génie Informatique (GI) de l'UTC (Université de Technologie de Compiègne, 2023-2026), filière IAD (Intelligence Artificielle et Science des Données), après CPGE PTSI-PT (Lycée Raspail, Paris).
- Label Mod'Math (Modélisation Mathématique) : MT09 (Analyse numérique matricielle, Fourier, Scilab), RO04 (Optimisation linéaire/non-linéaire, Simplexe, Lagrangien, Graphes), RO05 (Processus stochastiques, Chaînes de Markov, Processus de Poisson, Files d'attente M/M/1), SY02 (Statistiques de l'ingénieur, Monte-Carlo, tests d'hypothèses).
- UVs clés UTC : SY09 (Data Mining & ML), SY32 (Vision & Apprentissage pour systèmes autonomes), NF26 (Data Warehouse, ETL & Big Data), IA02 (Logique & Prolog/SAT), IA04 (Systèmes multi-agents & distribués), AOS2 (Deep Learning, CNN, RNN, Attention), LO21 (C++17 & Qt 6 GUI : 7 Wonders Duel), SR01/SR04/SR07 (Systèmes Unix, Réseaux, Cybersécurité).
- Langues : Français (natif), Anglais B2 courant professionnel (Linguaskill 179/167).

EXPÉRIENCES PROFESSIONNELLES (12 MOIS DE R&D DATA SCIENCE / IA & MODÉLISATION) :
1. Stage Fin d'Études TN10 chez Epiconcept (Mars - Sept 2026, Paris) — R&D Apprentissage Automatique en Santé (Vision & LLMs) :
   - Projet 1 (deep.piste - Mammographies & Garanties Statistiques) : Fine-tuning du réseau de vision interprétable GMIC (ResNet-22 global + saillance L1 + ResNet-18 local + fusion par attention, 14M paramètres) sur 300+ Go de mammographies haute résolution (RSNA, AUC = 0,889). Implémentation de la classification sélective (abstention) avec contrôle garanti du risque (cadre SGR, inversion exacte de la queue binomiale, bornes de Hoeffding, MC Dropout) et démonstration mathématique de la limite de garantie sur le FNR conditionnel à faible prévalence (2 %). Création d'une capsule pédagogique interactive de 8 chapitres exécutables sous Docker.
   - Projet 2 (ECDC / CATH-LLM - Bactériémies) : Détection de cathéters veineux centraux (CVC : IJ, PICC, portacath) sur 249 comptes rendus MIMIC-IV en 3 versions (Anglais -> Croate via MiLMMT -> Retour Anglais). Découverte et résolution de la perte de 40 % à la traduction par découpage par paragraphe et protection des caviardages `___`. Inférence de 6 à 20 configurations de LLMs ouverts 4-bit (MedGemma-27B, Gemma-3 27B, Mistral, Qwen3, Llama-3.3-70B) sous plafond strict VRAM A100 40 Go avec fenêtre de 16 384 tokens et calcul exact du KV cache en bf16 (GQA). Outil de vérification automatique anti-hallucination (`evidence_is_grounded`, `verify.csv`, F1 = 0,88) ayant même détecté une erreur dans le gold standard. Documentation exécutable Quarto (6 chapitres).
2. Stage Assistant Ingénieur TN09 chez Aubay Innov' (Sept 2024 - Fév 2025, Boulogne-Billancourt) — R&D Data Science ("Cohérence des données") :
   - Détection automatique d'anomalies contextuelles dans un tableau de données mixtes (colonnes numériques et catégorielles, jeux de données Automobile UCI et Salaire).
   - Vectorisation contextuelle des lignes via PyTorch Tabular (TabTransformer, FT-Transformer, GANDALF) couplée à Isolation Forest (IF) et Deep Isolation Forest (DIF, 2023). Étude de l'effet de la normalisation et de la transformation de Yeo-Johnson sous TensorBoard (F1 = 0,91 avec GANDALF sur Automobile).
   - Développement du back-end Flask (API REST JSON) connecté au front-end React, isolation multi-environnements Conda et stockage Amazon S3.

PROJETS ACADÉMIQUES & PERSONNELS MAJEURS :
- TZ2 (Laboratoire BMBI, UTC — encadré par Florian De Vuyst) : Méthodes neuronales pour surfaces implicites 3D et 4D espace-temps f(x,y,z,t)=0 (réseaux IGR/SIREN, perte Eikonal sur le gradient spatial, Marching Cubes) appliquées au globule rouge (quartique analytique de Kuchel retrouvée en 10 coefficients vs 197 886 poids, calcul des courbures gaussienne et moyenne par autograd d'ordre 2 sur la Hessienne, théorème de Gauss-Bonnet vérifié à 0,025 %) et aux vraies capsules bio-inspirées déformables en canal du BMBI (20 001 pas de temps Éléments Finis, preuve de déformation non affine, 93 % de glissement tangentiel tank-treading, IoU = 99,65 %, échantillonnage temporel adaptatif réduisant l'erreur de vitesse membranaire de 18 % à 4,6 %).
- SY32 (Vision par ordinateur, UTC) : Détection d'écocups (filtre bilatéral, correction gamma, fenêtre glissante + pyramide multi-échelles, HOG + LBP + HSV, SVM RBF / Random Forest / AdaBoost, Hard Negative Mining pondéré, joblib, NMS).
- SY09 (Data Mining, UTC) : Prédiction de maladies cardiaques (ACP, MDS distance de Gower, CAH, K-means adaptatif de Mahalanobis, K-means Gower, régression logistique avec test de Wald, LightGBM).
- NF26 (Big Data & ETL, UTC) : Pipeline ETL en schéma en étoile (Python, Pandas, PySpark, Geopy, Streamlit) pour le Bilan Carbone BGES de ~20 600 missions.
- Écosystème Personnel (Custos Android Device Owner en Kotlin, PDF Live Notes collaboratif stylet + IA en temps réel SSE, Self-System Linux mitmproxy/systemd, MonLycée Auth Relay FastAPI/Playwright/Edge Extension).
"""


class LLMExtractor:
    """
    Semantic extractor using Instructor and Groq (openai/gpt-oss-120b).
    Classifies offers into Joshua's graduated tiers (Tier S -> Tier C), enforces strict
    graduate experience limits (<= 3 years), and applies weighted coefficients.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "openai/gpt-oss-120b"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.client = None

        if self.api_key:
            try:
                self.client = instructor.from_groq(
                    Groq(api_key=self.api_key),
                    mode=instructor.Mode.JSON,
                )
            except Exception as e:
                print(f"[LLMExtractor] Erreur d'initialisation du client Groq : {e}")

    def is_configured(self) -> bool:
        return bool(self.client)

    def _fast_pre_reject(self, job: JobRaw) -> Optional[ProcessedJob]:
        """
        Fast deterministic pre-filter on job title AND required years of experience in description.
        Rejects internships, executive/senior roles, horrible jobs, and roles requiring >= 4 years of experience.
        """
        if EXCLUDED_TITLE_PATTERNS.search(job.title):
            ext = JobExtraction(
                matched_profile=ProfileCategory.HORS_CIBLE,
                is_relevant=False,
                match_score=0,
                contract_type=ContractType.STAGE_ALTERNANCE,
                years_of_experience=0,
                is_abroad_or_vie=False,
                tech_stack=[],
                salary_min_eur=None,
                relevance_reason="Exclu automatiquement : Stage / Alternance / Post-doc détecté dans le titre.",
                cv_pitch=None,
            )
            ext.apply_weighted_coefficients(job.company)
            return ProcessedJob(raw=job, extraction=ext)

        if TOO_SENIOR_TITLE_PATTERNS.search(job.title) and not JUNIOR_FRIENDLY_TITLE_PATTERNS.search(job.title):
            ext = JobExtraction(
                matched_profile=ProfileCategory.HORS_CIBLE,
                is_relevant=False,
                match_score=0,
                contract_type=ContractType.CDI,
                years_of_experience=6,
                is_abroad_or_vie=False,
                tech_stack=[],
                salary_min_eur=None,
                relevance_reason="Exclu automatiquement : Titre trop senior (Senior / Lead / Staff / Principal / Manager).",
                cv_pitch=None,
            )
            ext.apply_weighted_coefficients(job.company)
            return ProcessedJob(raw=job, extraction=ext)

        if HORRIBLE_JOB_TITLE_PATTERNS.search(job.title):
            ext = JobExtraction(
                matched_profile=ProfileCategory.HORS_CIBLE,
                is_relevant=False,
                match_score=0,
                contract_type=ContractType.CDI,
                years_of_experience=0,
                is_abroad_or_vie=False,
                tech_stack=[],
                salary_min_eur=None,
                relevance_reason="Exclu automatiquement : Poste hors-métier d'ingénieur (Support, Marketing, Design, RH, Légal).",
                cv_pitch=None,
            )
            ext.apply_weighted_coefficients(job.company)
            return ProcessedJob(raw=job, extraction=ext)

        req_years = extract_required_years_from_text(job.title, job.description_text or "")
        if req_years >= 3:
            ext = JobExtraction(
                matched_profile=ProfileCategory.HORS_CIBLE,
                is_relevant=False,
                match_score=0,
                contract_type=ContractType.CDI,
                years_of_experience=req_years,
                is_abroad_or_vie=False,
                tech_stack=[],
                salary_min_eur=None,
                relevance_reason=f"Exclu par Filtre 1 (Regex) : L'annonce exige {req_years}+ ans d'expérience (> 2 ans).",
                cv_pitch=None,
            )
            ext.apply_weighted_coefficients(job.company)
            return ProcessedJob(raw=job, extraction=ext)

        return None

    def extract_job(self, job: JobRaw) -> ProcessedJob:
        """
        Extracts structured entities, classifies into the graduated profiles (Tier S -> Tier C),
        and applies deterministic mission & company coefficients.
        """
        pre_rejected = self._fast_pre_reject(job)
        if pre_rejected is not None:
            return pre_rejected

        if not self.is_configured():
            return self._heuristic_fallback(job)

        desc_excerpt = (job.description_text or job.title)[:3500]
        prompt = f"""
Tu es le copilote carrière personnel ("Jarvis") de Joshua Nancey.

{JOSHUA_BIO_CONTEXT}

PHILOSOPHIE DE CLASSEMENT & DOUBLE FILTRE D'EXPÉRIENCE DE JOSHUA :
- Joshua VIENT D'ÊTRE DIPLÔMÉ de l'UTC. En combinant ses 2 stages R&D de 6 mois (Epiconcept + Aubay), il peut justifier **1 an d'expérience R&D** (et tenter jusqu'à **2 ans max**).
- RÈGLE STRICTE DES > 2 ANS = MORT :
  * Lis attentivement le texte de l'annonce : si le poste exige **3 ans d'expérience ou plus** (ex: "3+ years", "4+ years", "5+ years") OU si le texte montre implicitement qu'ils cherchent un profil confirmé/senior ayant déjà plusieurs années de CDI derrière lui, mets `years_of_experience = 3` (ou plus) et `is_relevant = False` (`HORS_CIBLE`) !
  * Si le poste demande **0 an (New Grad / Junior / Graduate / Débutant)** ou **1 an** (jouable avec ses 2 stages combinés), mets `years_of_experience = 0` ou `1` et `is_relevant = True`.
  * Si le poste demande **2 ans**, mets `years_of_experience = 2` et `is_relevant = True` (il prendra un petit malus automatique car plus dur).

LES CATÉGORIES ÉCHELONNÉES (DU MEILLEUR AU MOINS BON) :
1. [TIER S - ×1.18] `RO_MODELISATION_QUANT` :
   - Recherche Opérationnelle, Optimisation (graphes, PLNE, ordonnancement, énergie, transport, yield/revenue management), Modélisation Stochastique & Simulation (Markov, Monte-Carlo, files d'attente).
   - Validation de Modèles (Model Risk Management en banque/assurance), Risques Quantitatifs, Quant Research/Trading, Actuariat/Pricing, IA de Confiance / Safe & Trustworthy AI (garanties statistiques, certification IA).
2. [TIER S - ×1.18] `ARCHITECTE_AI_DATA` :
   - Application Engineer (ex: MathWorks, Dassault Systèmes), Solutions Architect IA / Data / Cloud, Forward Deployed Engineer, Client Engineering : rôles hybrides mêlant modélisation/architecture/PoC et interaction directe avec les décideurs/clients.
3. [TIER A - ×1.06] `CHEF_DE_PROJET_PM` :
   - Chef de Projet R&D / IA / Data, Technical Product Manager (TPM), Associate Product Manager (APM), Product Owner Data & IA, Pilote de projet scientifique/technique.
4. [TIER A - ×1.05] `RECHERCHE_RD_CIFRE` :
   - Ingénieur-Chercheur ou Ingénieur R&D en centre de recherche ou industrie (CEA, Inria, ONERA, EDF R&D, Thales, Safran...), Thèse CIFRE en Maths Appliquées / RO / IA.
5. [TIER A - ×1.05] `VIE_INTERNATIONAL` :
   - V.I.E ou Graduate Program international en Quant, Recherche Opérationnelle, Data/IA, Architecture ou Product.
6. [TIER B - ×0.94] `DATA_SCIENCE_ENGINEER` :
   - Data Scientist, Machine Learning Engineer, AI Engineer (Computer Vision, NLP, LLMs, Tabulaire) classique.
7. [TIER B - ×0.94] `TECH_SALES_PRESALES` :
   - Pre-Sales Engineer, Sales Engineer Tech/IA, Ingénieur d'Affaires Tech, BDR/SDR Tech chez un éditeur logiciel/IA.
8. [TIER C - ×0.82 - Filet de sécurité] `CONSULTANT_DATA_IA` :
   - Consultant Data / IA / Transformation Digitale en ESN ou cabinet de conseil.
9. [TIER C - ×0.80 - Filet de sécurité] `SOFTWARE_DATA_ENG` :
   - Data Engineer pur (ETL, SQL, Spark, Data Warehouse), Software Engineer / Développeur C++ / Python / Backend, MLOps/DevOps pur.
10. [TIER F - ×0.00 - À DÉGAGER] `HORS_CIBLE` :
   - Stage, Alternance, Apprentissage, Post-doctorat (PhD requis), ou poste exigeant >= 4 ans d'expérience.
   - Postes "vraiment horribles" pour un ingénieur UTC : Support N1/N2/Helpdesk, QA/Recette manuelle sans code, paramétrage ERP/CRM, Marketing, Design, RH, Légal.

OFFRE À ANALYSER :
- Référence : {job.id}
- Entreprise : {job.company}
- Titre : {job.title}
- Date de publication : {job.date_posted or 'Récente'}
- Localisation : {job.location or 'Non spécifiée'}
- Description :
{desc_excerpt}
"""

        import time
        for attempt in range(3):
            try:
                extraction: JobExtraction = self.client.chat.completions.create(
                    model=self.model,
                    response_model=JobExtraction,
                    max_retries=2,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Tu es Jarvis, le copilote carrière de Joshua Nancey (Jeune Diplômé Ingénieur UTC GI & Mod'Math avec 1 an de R&D en stages). "
                                "Rejette impérativement toute offre exigeant plus de 2 ans d'expérience (> 2 ans, que ce soit écrit en chiffres ou implicite dans les responsabilités)."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                )
                # Double verrou (Consensus Filtre 1 Regex + Filtre 2 IA Groq) :
                regex_years = extract_required_years_from_text(job.title, job.description_text or "")
                llm_years = extraction.years_of_experience or 0
                effective_years = max(regex_years, llm_years)
                extraction.years_of_experience = effective_years

                if effective_years > 2 or not extraction.is_relevant or extraction.matched_profile == ProfileCategory.HORS_CIBLE:
                    extraction.is_relevant = False
                    extraction.matched_profile = ProfileCategory.HORS_CIBLE
                    extraction.relevance_reason = (
                        f"❌ [Rejet Double Filtre : Regex={regex_years}a | IA Groq={llm_years}a] {extraction.relevance_reason}"
                    )
                else:
                    extraction.relevance_reason = (
                        f"🤖 [Validé Double Filtre : Regex={regex_years}a & IA Groq={llm_years}a ≤ 2 ans] {extraction.relevance_reason}"
                    )

                extraction.apply_weighted_coefficients(job.company)
                return ProcessedJob(raw=job, extraction=extraction)

            except Exception as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    wait_s = 8 * (attempt + 1)
                    print(f"[LLMExtractor] Limite TPM Groq atteinte, pause de {wait_s}s avant réessai...")
                    time.sleep(wait_s)
                    continue
                print(f"[LLMExtractor] Erreur LLM pour '{job.title}' ({job.company}) : {e}")
                return self._heuristic_fallback(job)
        return self._heuristic_fallback(job)

    def extract_jobs_batch(self, jobs: list[JobRaw]) -> list[ProcessedJob]:
        """
        Analyse un lot d'offres (ex: 8 offres d'un coup) en UN SEUL appel API Groq
        pour diviser par 10 la consommation de tokens et éviter tout blocage 429 Rate Limit.
        Combine le Filtre 1 (Regex) et le Filtre 2 (Juge IA Groq).
        """
        if not jobs:
            return []
        if not self.is_configured():
            return [self._heuristic_fallback(j) for j in jobs]

        from pydantic import BaseModel, Field

        class BatchItemEval(BaseModel):
            idx: int = Field(..., description="Index de l'offre dans le lot (0, 1, 2...)")
            is_relevant: bool = Field(..., description="True UNIQUEMENT si accessible à un Jeune Diplômé UTC (0, 1 ou 2 ans max). False si > 2 ans (explicite ou implicite) ou hors-cible.")
            years_of_experience: int = Field(..., description="Années d'expérience exigées estimées par l'IA (0, 1, 2, ou >=3 si profil confirmé/senior).")
            matched_profile: ProfileCategory = Field(..., description="Catégorie parmi RO_MODELISATION_QUANT, ARCHITECTE_AI_DATA, CHEF_DE_PROJET_PM, RECHERCHE_RD_CIFRE, VIE_INTERNATIONAL, DATA_SCIENCE_ENGINEER, TECH_SALES_PRESALES, CONSULTANT_DATA_IA, SOFTWARE_DATA_ENG, HORS_CIBLE.")
            raw_cv_score: int = Field(..., description="Note brute d'adéquation CV entre 55 et 88 (0 si rejeté).")
            relevance_reason: str = Field(..., description="Justification concise (1 phrase) du verdict d'expérience et de mission.")
            cv_pitch: str = Field(..., description="Quels projets précis de Joshua (Mod'Math RO04/RO05, Epiconcept GMIC/SGR/CATH-LLM, Aubay Tabular, TZ2 BMBI, Custos) mettre en avant.")

        class BatchEvalResponse(BaseModel):
            evaluations: list[BatchItemEval]

        items_text = []
        for idx, j in enumerate(jobs):
            desc = (j.description_text or "")
            # Extraire le début + les passages parlant de qualifications / experience / requirements
            head = desc[:650]
            req_matches = [
                m.group(0)
                for m in re.finditer(r".{0,120}\b(years?|ans?|experience|expérience|qualifications?|requirements?|profil|background|phd|master|degree)\b.{0,180}", desc[650:], re.IGNORECASE)
            ]
            req_snippet = " ... ".join(req_matches[:3])
            combined_desc = f"{head}\n[Extraits Qualifications]: {req_snippet}"[:1200]
            items_text.append(
                f"--- OFFRE [{idx}] ---\n"
                f"Entreprise: {j.company} | Titre: {j.title} | Lieu: {j.location or 'Global'}\n"
                f"Texte: {combined_desc}\n"
            )

        batch_prompt = (
            f"{JOSHUA_BIO_CONTEXT}\n\n"
            "RÈGLE ABSOLUE DU JUGE IA GROQ (FILTRE 2) :\n"
            "- Joshua vient d'être diplômé de l'UTC (avec 2 stages R&D de 6 mois combinables = 1 an d'expérience R&D).\n"
            "- Si une offre demande PLUS DE 2 ANS d'expérience (>= 3 ans écrits en chiffres OU séniorité/autonomie confirmée implicite dans le texte), mets `years_of_experience >= 3`, `is_relevant = False` et `matched_profile = 'HORS_CIBLE'` !\n"
            "- Si l'offre est ouverte à un Jeune Diplômé (0 an), ou demande ~1 an (jouable avec ses 2 stages combinés), ou 2 ans max, mets `years_of_experience` à 0, 1 ou 2, `is_relevant = True`, et classe-la dans le bon profil.\n\n"
            "Évalue chacune des offres suivantes :\n\n" + "\n".join(items_text)
        )

        try:
            resp: BatchEvalResponse = self.client.chat.completions.create(
                model=self.model,
                response_model=BatchEvalResponse,
                max_retries=2,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es le juge IA carrière de Joshua Nancey. Analyse le lot d'offres et rejette impérativement toute offre exigeant > 2 ans d'expérience.",
                    },
                    {"role": "user", "content": batch_prompt},
                ],
                temperature=0.1,
            )
            eval_map = {e.idx: e for e in resp.evaluations}
        except Exception as e:
            print(f"[LLMExtractor Batch] Fallback heuristique sur ce lot ({e})")
            return [self._heuristic_fallback(j) for j in jobs]

        results: list[ProcessedJob] = []
        for idx, j in enumerate(jobs):
            ev = eval_map.get(idx)
            if ev is None:
                results.append(self._heuristic_fallback(j))
                continue

            heur = self._heuristic_fallback(j).extraction
            regex_years = extract_required_years_from_text(j.title, j.description_text or "")
            llm_years = max(0, min(15, ev.years_of_experience))
            effective_years = max(regex_years, llm_years)

            is_rel = ev.is_relevant and heur.is_relevant and (effective_years <= 2) and (ev.matched_profile != ProfileCategory.HORS_CIBLE)
            prof = ev.matched_profile if is_rel else ProfileCategory.HORS_CIBLE

            if is_rel:
                reason = f"🤖 [Double Filtre VALIDÉ : Regex={regex_years}a & IA Groq={llm_years}a ≤ 2 ans] {ev.relevance_reason}"
            else:
                reason = f"❌ [Rejeté par Double Filtre : Regex={regex_years}a | IA Groq={llm_years}a] {ev.relevance_reason}"

            ext = JobExtraction(
                matched_profile=prof,
                is_relevant=is_rel,
                raw_cv_score=ev.raw_cv_score if is_rel else 0,
                match_score=ev.raw_cv_score if is_rel else 0,
                contract_type=heur.contract_type,
                years_of_experience=effective_years,
                is_abroad_or_vie=heur.is_abroad_or_vie,
                tech_stack=heur.tech_stack,
                salary_min_eur=None,
                relevance_reason=reason,
                cv_pitch=ev.cv_pitch if is_rel else None,
                recommended_cv_folder=heur.recommended_cv_folder,
            )
            ext.apply_weighted_coefficients(j.company)
            results.append(ProcessedJob(raw=j, extraction=ext))

        return results

    def _heuristic_fallback(self, job: JobRaw) -> ProcessedJob:
        """Rule-based fallback with strict experience extraction (rejects >= 4 years)."""
        pre = self._fast_pre_reject(job)
        if pre is not None:
            return pre

        text = f"{job.title} {job.description_text or ''}".lower()
        title_lower = job.title.lower()
        req_years = extract_required_years_from_text(job.title, job.description_text or "")
        is_junior_explicit = bool(JUNIOR_FRIENDLY_TITLE_PATTERNS.search(job.title))

        profile = ProfileCategory.HORS_CIBLE
        contract = ContractType.CDI
        is_abroad = False
        cv_folder = "5_Data_IA_Engineering"
        base_cv_score = 76

        # 1. TIER S : RO, Optimisation, Stochastique, Quant Risk, Model Validation, Safe AI
        if any(
            w in title_lower
            for w in [
                "recherche opérationnelle",
                "recherche operationnelle",
                "operations research",
                "optimisation",
                "optimization",
                "stochastique",
                "stochastic",
                "markov",
                "yield",
                "revenue management",
                "pricing",
                "model risk",
                "validation",
                "quantitative",
                "quant ",
                "actuaire",
                "actuariat",
                "decision science",
                "decision scientist",
                "value engineer",
                "trustworthy",
                "safe ai",
                "safety",
                "alignment",
                "sûreté",
            ]
        ):
            profile = ProfileCategory.RO_MODELISATION_QUANT
            cv_folder = "5_Data_IA_Engineering"
            base_cv_score = 76 if ("phd" in title_lower or "thèse" in title_lower or "doctorat" in title_lower) else 80

        # 2. TIER C (Prioritaire si "Consultant" dans le titre) : Consultant Data / IA / Transformation
        elif any(w in title_lower for w in ["consultant", "conseil", "transformation"]):
            profile = ProfileCategory.CONSULTANT_DATA_IA
            cv_folder = "1_Consulting_Tech_Data_Strategie"
            base_cv_score = 75

        # 3. TIER S : Solutions Architect / Application Engineer / Forward Deployed (Hors simple consultant ESN)
        elif any(
            w in title_lower
            for w in [
                "application engineer",
                "solutions architect",
                "solution architect",
                "applied ai architect",
                "architecte",
                "architect",
                "forward deployed",
                "deployment strategist",
                "client engineering",
                "customer engineer",
                "field engineer",
            ]
        ):
            profile = ProfileCategory.ARCHITECTE_AI_DATA
            cv_folder = "1_Consulting_Tech_Data_Strategie"
            base_cv_score = 79

        # 4. TIER A : V.I.E & International
        elif any(w in text for w in ["v.i.e", "vie ", "international graduate"]):
            profile = ProfileCategory.VIE_INTERNATIONAL
            contract = ContractType.VIE
            is_abroad = True
            base_cv_score = 77

        # 5. TIER A : Chef de Projet R&D / Product Manager / PO IA
        elif any(
            w in title_lower
            for w in ["chef de projet", "product manager", "product owner", "project manager", "pilote", "coordinateur"]
        ):
            profile = ProfileCategory.CHEF_DE_PROJET_PM
            cv_folder = "4_Product_Management_Tech"
            base_cv_score = 77

        # 6. TIER A : Ingénieur-Chercheur / R&D / CIFRE
        elif any(
            w in text
            for w in [
                "cifre",
                "doctorant",
                "doctorat",
                "phd",
                "thèse",
                "ingénieur-chercheur",
                "ingenieur-chercheur",
                "ingénieur chercheur",
                "ingenieur chercheur",
                "ingénieur de recherche",
                "ingénieur r&d",
                "research engineer",
            ]
        ):
            profile = ProfileCategory.RECHERCHE_RD_CIFRE
            is_phd = any(w in title_lower for w in ["phd", "thèse", "doctorat", "doctoral"])
            contract = ContractType.THESE_CIFRE if is_phd else (ContractType.CDD if "cdd" in text else ContractType.CDI)
            cv_folder = "5_Data_IA_Engineering"
            base_cv_score = 70 if is_phd else 76

        # 7. TIER B : Pre-Sales / Sales Engineer / Tech Sales
        elif any(
            w in title_lower
            for w in [
                "sales",
                "pre-sales",
                "presales",
                "avant-vente",
                "ingénieur d'affaires",
                "business developer",
                "account executive",
                "bdr",
                "sdr",
                "solutions engineer",
            ]
        ):
            profile = ProfileCategory.TECH_SALES_PRESALES
            cv_folder = "2_Tech_Sales_SDR_BDR"
            base_cv_score = 76

        # 8. TIER B : Data Scientist / ML Engineer / AI Engineer
        elif any(
            w in text
            for w in [
                "data scientist",
                "data science",
                "machine learning",
                "intelligence artificielle",
                "ai engineer",
                "ml engineer",
                "deep learning",
                "computer vision",
                "nlp",
                "llm",
                "modélisation",
                "modelisation",
            ]
        ):
            profile = ProfileCategory.DATA_SCIENCE_ENGINEER
            cv_folder = "5_Data_IA_Engineering"
            base_cv_score = 78

        # 9. TIER C : Data Engineer / Software Engineer / Dev C++ & Python
        elif any(
            w in text
            for w in ["data engineer", "etl", "spark", "software engineer", "développeur", "developpeur", "c++", "python", "mlops", "devops"]
        ):
            profile = ProfileCategory.SOFTWARE_DATA_ENG
            cv_folder = "5_Data_IA_Engineering"
            base_cv_score = 74

        # Ajustement de réalisme d'embauche pour un Jeune Diplômé UTC (avec 12 mois de stage R&D) :
        # 1. 🟢 Cible Jeune Diplômé Garantie (Junior/Graduate/Associate/Fellow/V.I.E ou CEA/Inria ou <=1 an explicite) : +6 pts
        # 2. 🟡 Tentable avec tes 2 stages R&D (2 ans ou non spécifié dans une boîte privée) : -5 pts
        # 3. 🟠 Au culot (3 ans demandés) : -12 pts
        is_research_inst = any(w in job.company.lower() for w in ["cea", "inria", "onera", "cnrs"])
        if is_junior_explicit or is_research_inst or req_years == 1:
            base_cv_score += 5
            exp_note = "🟢 [Cible Jeune Diplômé 0-2 ans Garantie]"
        elif req_years == 3:
            base_cv_score -= 12
            exp_note = "🟠 [Au culot : annonce demandant ~3 ans d'exp]"
        elif req_years == 2:
            base_cv_score -= 4
            exp_note = "🟡 [Accessible avec tes 12 mois de R&D : ~2 ans demandés]"
        else:
            base_cv_score -= 5
            exp_note = "🟡 [Tentable au culot : pas de filtre Junior explicite dans le titre]"

        is_rel = profile != ProfileCategory.HORS_CIBLE

        tech_list = []
        for tech in ["python", "pytorch", "tensorflow", "sql", "spark", "docker", "aws", "gcp", "azure", "c++", "kubernetes", "hpc", "linux", "r", "matlab"]:
            if f" {tech} " in f" {text} ":
                tech_list.append(tech.upper() if tech in ("sql", "aws", "gcp", "hpc", "r") else tech.capitalize())

        ext = JobExtraction(
            matched_profile=profile,
            is_relevant=is_rel,
            raw_cv_score=base_cv_score if is_rel else 0,
            match_score=base_cv_score if is_rel else 0,
            contract_type=contract,
            years_of_experience=req_years,
            is_abroad_or_vie=is_abroad,
            tech_stack=tech_list,
            salary_min_eur=None,
            relevance_reason=f"{exp_note} Classé en {profile.value}.",
            cv_pitch="Mettre en avant le diplôme UTC Génie Informatique (Label Mod'Math RO04/RO05/SY02/MT09) et les 12 mois de R&D cumulés chez Epiconcept (GMIC + garanties statistiques SGR/Hoeffding + CATH-LLM), Aubay (PyTorch Tabular) et TZ2 BMBI.",
            recommended_cv_folder=cv_folder,
        )
        ext.apply_weighted_coefficients(job.company)
        return ProcessedJob(raw=job, extraction=ext)
