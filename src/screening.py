"""
Screening v2 — Filtre d'offres à garde-fous déterministes + juges IA multiples (Groq).

Principe (leçon des faux positifs : Security Engineer, Credit Risk Associate, VIE Data Analyst/Power BI,
Perplexity « Early Career » qui exclut les new grads) :

1. Les juges IA ne décident PAS « pertinent oui/non ». Ils EXTRAIENT des faits de l'annonce
   (années exigées, new grads exclus, outils obligatoires manquants, autorisation de travail, famille de métier)
   et doivent CITER mot pour mot la phrase du texte qui justifie chaque blocage.
2. Chaque citation est vérifiée par programme dans le texte complet de l'annonce
   (même principe que `evidence_is_grounded` du projet CATH-LLM) : une citation introuvable = blocage ignoré.
3. La décision finale est du code déterministe (`decide`), pas un avis de LLM.
4. Deux modèles Groq différents (quotas indépendants) : le second ne confirme que les offres acceptées par le premier.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from src.models import JobRaw

SCREEN_VERSION = "v2.0"

# --------------------------------------------------------------------------------------
# 1. PROFIL CANDIDAT (uniquement des éléments vérifiés dans joshua_profile_corpus/)
# --------------------------------------------------------------------------------------
CANDIDATE_PROFILE = """\
CANDIDATE (verified facts only):
- Just graduated: French engineering degree (UTC, Computer Engineering, AI & Data track, Applied Mathematics label), master-level (Bac+5). NO PhD.
- Professional experience = exactly two 6-month internships (Data Science/ML R&D) = 12 months in total. No full-time job.
- Languages: French (native), English (professional B2/C1). NO German, NO Dutch, NO Spanish, NO Italian, no other spoken language.
- KNOWN tools/skills: Python, PyTorch, PyTorch Tabular, scikit-learn, LightGBM, Pandas, NumPy, SciPy, PySpark, R, SQL (PostgreSQL/Oracle/SQLite), C, C++ (Qt),
  Kotlin/Android, JavaScript/TypeScript (basic web/extensions), React, HTML/CSS, Prolog, Scilab/Matlab, Flask, FastAPI, Docker, Linux/UNIX, Git/GitHub Actions,
  Conda, AWS/Amazon S3, Streamlit, TensorBoard, LaTeX, Quarto.
  Maths & AI: mathematical modeling, optimization/operations research, stochastic processes (Markov, Poisson, queueing), statistics, statistical learning,
  Monte-Carlo, numerical analysis, deep learning, computer vision, medical imaging, NLP, LLMs, RAG, AI agents, LLM evaluation, anomaly detection, data science.
- NOT demonstrated (treat as MISSING if mandatory): Power BI, DAX, Power Query, Tableau, Qlik, Looker, Excel/VBA macro specialist, Salesforce, SAP, ServiceNow,
  Kubernetes/Terraform/Ansible (as core DevOps/SRE), Java/Spring, C#/.NET, Go/Golang, Rust, Scala, PHP, Ruby, Swift/iOS, proprietary SAS,
  credit risk / underwriting domain experience, classic cybersecurity/pentest/IAM/SOC, or fluency in German/Dutch/Spanish/Italian/etc.
"""

JUDGE_SYSTEM = """You are a strict recruiting-data extractor. You read ONE job posting and extract FACTS about its requirements.
You do NOT decide whether to apply. Rules:
- Extract only what the text says. Never invent. If unsure, use the neutral value (0, false, "unknown", "").
- `min_years_required`: minimum years of PROFESSIONAL experience REQUIRED (not preferred/nice-to-have). "2+ years of experience in credit risk" -> 2.
  "Early career"/"new grad"/"0-2 years" or an UPPER BOUND ("maximum of 2 years", "no more than 3 years", "up to 2 years", "débutant à 3 ans") -> 0.
  A range "1-3 years" -> its lower bound (1).
- `internships_count`: "yes" if the text says internships/apprenticeships/co-ops count as experience, "no" if it says they do NOT count
  (e.g. "full-time industry experience", "post-graduation experience"), else "unknown".
- `excludes_new_grads`: true if the text says the role is NOT for new/recent graduates or entry-level candidates, or requires prior industry experience
  that a new graduate cannot have. `targets_new_grads`: true if explicitly aimed at new grads / graduates / early careers / juniors / VIE.
- `mandatory_skills_missing`: concrete technical tools, programming languages, certifications, licenses or spoken languages that the text presents as
  REQUIRED/MANDATORY (not "plus", "nice to have", "preferred", "bonus") AND that are absent from the candidate's KNOWN list. Max 5 short items. No soft skills.
- `requires_work_authorization_outside_eu`: true if the text requires citizenship, security clearance, or authorization to work in a non-EU country
  (e.g. US) without offering visa sponsorship/relocation.
- `degree_required`: minimum degree needed TO APPLY. A "PhD position"/"doctoral position"/CIFRE thesis requires a master, not a PhD.
- `role_family`: the real nature of the job. `security` = classic information-security engineering (AppSec, IAM, SOC, pentest, security engineer).
  AI safety/alignment RESEARCH is `ml_research`, not `security`. `devops_infra` = DevOps/SRE/infrastructure/platform/IT. `data_analytics_bi` = dashboards/BI/reporting analyst.
- EVIDENCE fields (`years_evidence`, `new_grads_evidence`, `skills_evidence`, `work_auth_evidence`): when you report a blocker, copy the EXACT sentence
  (<= 30 words) from the posting, word for word. If there is no blocker, leave the evidence as "".
Output ONLY one JSON object with exactly these keys:
{"min_years_required":int,"years_evidence":str,"internships_count":"yes|no|unknown","excludes_new_grads":bool,"new_grads_evidence":str,
 "targets_new_grads":bool,"degree_required":"none|bachelor|master|phd","mandatory_skills_missing":[str],"skills_evidence":str,
 "requires_work_authorization_outside_eu":bool,"work_auth_evidence":str,
 "role_family":"ml_research|ml_engineering|data_science|data_engineering|data_analytics_bi|quant|operations_research|solutions_architecture|forward_deployed|product_management|project_management|consulting|sales|software_engineering|security|devops_infra|other"}"""


class OfferRequirements(BaseModel):
    min_years_required: int = Field(0, ge=0, le=30)
    years_evidence: str = ""
    internships_count: Literal["yes", "no", "unknown"] = "unknown"
    excludes_new_grads: bool = False
    new_grads_evidence: str = ""
    targets_new_grads: bool = False
    degree_required: Literal["none", "bachelor", "master", "phd"] = "none"
    mandatory_skills_missing: List[str] = Field(default_factory=list)
    skills_evidence: str = ""
    requires_work_authorization_outside_eu: bool = False
    work_auth_evidence: str = ""
    role_family: Literal[
        "ml_research", "ml_engineering", "data_science", "data_engineering", "data_analytics_bi",
        "quant", "operations_research", "solutions_architecture", "forward_deployed",
        "product_management", "project_management", "consulting", "sales",
        "software_engineering", "security", "devops_infra", "other",
    ] = "other"


# --------------------------------------------------------------------------------------
# 2. PRÉ-FILTRES DÉTERMINISTES (gratuits, avant tout appel LLM)
# --------------------------------------------------------------------------------------
# Titres hors-métier (jamais envoyés au LLM)
# Attention : en français, « Apprentissage automatique / statistique / profond / par renforcement » = Machine Learning, PAS un contrat d'alternance !
OFF_TOPIC_TITLE = re.compile(
    r"\b(stage|stagiaire|intern|internship|alternance|alternant|apprenti(?:e|s)?\b|contrat d['’]apprentissage|apprentice\w*|co-?op|working student|werkstudent|praktikum|praktikant\w*|"
    r"thesis student|master['’]?s? thesis|abschlussarbeit|post-?doc\w*|"
    r"recruit\w*|talent acquisition|people (?:partner|ops)|hr\b|ressources humaines|payroll|accountant|comptable|tax\b|legal|counsel|paralegal|juriste|"
    r"marketing|brand|copywriter|content (?:writer|creator)|communications?|public relations|events?\b|designer|design lead|"
    r"customer (?:success|support|experience)|support (?:engineer|specialist|agent)|helpdesk|technicien|"
    r"office manager|executive assistant|assistant\(?e?\)?|facilities|workplace|customs manager|"
    r"account (?:executive|manager|director)|business development rep\w*|sales development|\bsdr\b|\bbdr\b|inside sales|commercial associate|"
    r"partnerships? manager|"
    r"salesforce|servicenow|sap\b|"
    r"recruiter|finance manager|controller|auditor|procurement|supply chain (?:analyst|manager)|"
    r"nurse|driver|chauffeur|warehouse|mechanic|electrician|"
    r"underwriter|fraud (?:analyst|strategist|investigator)|credit risk (?:analyst|associate)|compliance|\bkyc\b|\baml\b)\b",
    re.IGNORECASE,
)

# Titres trop seniors
TOO_SENIOR = re.compile(
    r"\b(senior|sénior|sr\.?|staff|principal|distinguished|lead|leader|leadership|head of|director|directeur|directrice|vp|vice president|"
    r"group product manager|manager,|engineering manager|architecture manager|iii|iv|v)\b",
    re.IGNORECASE,
)
# « Associate » / « Resident » sont ambigus (ex : « Credit Risk Associate » exige 2 ans) : ils ne suffisent PAS à ignorer une exigence d'années.
JUNIOR_SIGNAL = re.compile(
    r"\b(junior|graduate|new grad\w*|early career\w*|entry[- ]level|jeune diplômé|jeune diplome|débutant|debutant|v\.?i\.?e|fellow\w*|"
    r"berufseinsteiger\w*|einsteiger\w*|absolvent\w*|trainee|campus)\b",
    re.IGNORECASE,
)

# Famille de métier plausible pour son profil (le titre doit évoquer au moins un de ces domaines)
PLAUSIBLE_TITLE = re.compile(
    r"\b(data|machine learning|\bml\b|\bai\b|a\.i\.|artificial|intelligence|learning|deep|nlp|vision|llm|research\w*|scientist|quant\w*|"
    r"optimi[sz]ation|operations research|stochastic|statistic\w*|model\w*|algorithm\w*|applied|simulation|numerical|mathematic\w*|"
    r"solutions?|forward deployed|architect\w*|customer engineer|sales engineer|pre-?sales|field engineer|technical (?:account|consultant)|"
    r"product (?:manager|owner)|project|program(?:me)? manager|consult\w*|"
    r"software|engineer|ingénieur|ingenieur|ingenieurin|entwickler\w*|developer|développeur|developpeur|c\+\+|python|backend|full[- ]?stack|"
    r"graduate|new grad|early career|trainee|v\.?i\.?e|junior|associate|fellow\w*|resident)\b",
    re.IGNORECASE,
)

# Sécurité informatique classique (hors AI safety) et infra/IT : hors profil visé
OFF_PROFILE_TITLE = re.compile(
    r"\b(security (?:engineer|analyst|architect|specialist|researcher)|appsec|application security|infosec|cyber\w*|"
    r"soc analyst|penetration|pentest|iam\b|devops|\bsre\b|site reliability|platform engineer|infrastructure engineer|cloud engineer|"
    r"network (?:engineer|administrator)|system(?:s)? administrator|sysadmin|it engineer|it support|technical support|"
    r"front[- ]?end|ios engineer|android engineer|qa engineer|test engineer|embedded|firmware|hardware|mechanical|"
    r"electrical|manufacturing|silicon|asic|fpga)\b",
    re.IGNORECASE,
)
AI_SAFETY_EXCEPTION = re.compile(r"\b(ai safety|alignment|safety (?:research|training)|trustworthy|interpretab\w*|red[- ]team\w*)\b", re.IGNORECASE)

# Phrases d'exclusion explicite des jeunes diplômés (EN/FR/DE)
NEW_GRAD_EXCLUSION = [
    re.compile(r"not (?:a |an )?(?:suitable|appropriate|intended|designed|open|available|eligible)[^.]{0,40}(?:new|recent) grad", re.I),
    re.compile(r"(?:new|recent) grad\w*[^.]{0,60}(?:should not|shouldn't|do not|don't|are not|aren't|cannot|can't|will not|won't)[^.]{0,30}(?:apply|considered|eligible|fit)", re.I),
    re.compile(r"(?:please )?(?:do not|don't) apply[^.]{0,60}(?:new|recent) grad", re.I),
    re.compile(r"not (?:an? )?(?:entry[- ]level|junior|graduate) (?:role|position|job)", re.I),
    re.compile(r"(?:this|the) (?:role|position) is not (?:for|aimed at|suited)[^.]{0,40}(?:graduate|entry|junior)", re.I),
    re.compile(r"(?:no|not accepting|not hiring)[^.]{0,20}(?:new|recent) grad", re.I),
    re.compile(r"ne (?:convient|s'adresse) pas (?:à|aux)[^.]{0,40}(?:jeunes? diplômé|débutant|junior)", re.I),
    re.compile(r"pas (?:un )?poste (?:de )?(?:débutant|junior)", re.I),
    re.compile(r"keine? (?:berufseinsteiger|absolventen)", re.I),
]

US_AUTH = re.compile(
    r"(?:u\.?s\.? citizen\w*|security clearance|\bitar\b|\bts/sci\b|eligible for (?:a )?(?:u\.?s\.? )?(?:security )?clearance|"
    r"(?:without|no)[^.]{0,25}(?:visa )?sponsorship|(?:unable|not able|cannot|can't|will not|won't|do not|don't)[^.]{0,25}sponsor)",
    re.I,
)
SPONSOR_OK = re.compile(
    r"(?:visa sponsorship (?:is )?(?:available|provided|offered)|we (?:do |will |can )?sponsor|will sponsor|can sponsor|"
    r"relocation (?:assistance|support|package|provided|offered|available)|sponsor(?:s|ing)? (?:work )?visas?|blue card)",
    re.I,
)
NON_EU_LOC = re.compile(
    r"(?:united states|\busa\b|\bu\.s\.|, (?:ca|ny|wa|tx|ma|il|dc|co|ga|va|nj|fl|pa)\b|san francisco|new york|\bnyc\b|seattle|boston|austin|chicago|"
    r"los angeles|palo alto|mountain view|menlo park|washington|canada|toronto|vancouver|montreal|singapore|tokyo|japan|india|bangalore|australia|sydney|"
    r"brazil|mexico|dubai|israel|tel aviv|china|beijing|shanghai|hong kong|seoul|korea)",
    re.I,
)
EU_LOC = re.compile(
    r"(?:france|paris|lyon|toulouse|grenoble|sophia|nantes|saclay|germany|deutschland|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|stuttgart|"
    r"switzerland|schweiz|suisse|zurich|zürich|geneva|genève|lausanne|basel|netherlands|amsterdam|rotterdam|eindhoven|delft|belgium|brussels|luxembourg|"
    r"austria|vienna|wien|sweden|stockholm|denmark|copenhagen|norway|oslo|finland|helsinki|ireland|dublin|spain|madrid|barcelona|italy|milan|portugal|lisbon|"
    r"poland|warsaw|united kingdom|\buk\b|london|cambridge|oxford|edinburgh|europe|emea|\beu\b|remote[- ]?(?:eu|europe|emea))",
    re.I,
)

# Années d'expérience exigées : (nombre, extrait). On ignore les mentions « préféré / bonus » ainsi que l'âge V.I.E (18-28 ans) ou la durée de contrat (CDD de 3 ans).
_YEARS_PATTERNS = [
    re.compile(r"\b(\d{1,2})\s*(?:-|–|to|à|bis)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?|ans?|jahre?n?)(?:['’]s)?\s+(?:of\s+|d['’]\s*|in\s+|de\s+)?(?:[\w\-/,&]+\s+){0,6}?(?:experience|expérience|erfahrung|background|track record)", re.I),
    re.compile(r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?|ans?|jahre?n?)(?:['’]s)?\s+(?:of\s+|d['’]\s*|in\s+|de\s+)?(?:[\w\-/,&]+\s+){0,6}?(?:experience|expérience|erfahrung|background|track record)", re.I),
    re.compile(r"(?:minimum|at least|min\.?|au moins|mindestens|justifiant de|plus de)\s+(?:of\s+|d['’]\s*|de\s+)?(\d{1,2})\s*\+?\s*(?:years?|yrs?|ans?|jahre?n?)\s+(?:of\s+|d['’]\s*|in\s+|de\s+)?(?:[\w\-/,&]+\s+){0,6}?(?:experience|expérience|erfahrung|background|track record)", re.I),
    re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?|ans?|jahre?n?)(?:['’]s)?\s+(?:of\s+|d['’]\s*|in\s+|de\s+)?(?:[\w\-/,&]+\s+){0,6}?(?:experience|expérience|background|track record|berufserfahrung)", re.I),
    re.compile(r"(?:expérience|experience|berufserfahrung)\s+(?:professionnelle\s+|minimale\s+|of\s+|de\s+|d['’]\s*)?(?:au moins\s+|minimum\s+|at least\s+)?(\d{1,2})\s*(?:(?:-|–|to|à|bis)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs?|ans?|jahre?n?)\b", re.I),
]
_WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8, "dix": 10}
_YEARS_WORD = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|deux|trois|quatre|cinq|sept|huit|dix)\s*\+?\s*(?:or more\s+)?(?:years?|ans?)\b", re.I
)
_SOFT = re.compile(r"(?:prefer\w*|a plus|bonus|nice[- ]to[- ]have|ideally|asset|advantage|desirable|souhait\w*|apprécié\w*|idéalement|wünschenswert|von vorteil)", re.I)
_NON_EXP_SENT = re.compile(r"\b(?:âgé\w*|age[d]?|years old|18\s*(?:-|to|à)\s*28|cdd de|contrat de|durée de|duration of|thèse de \d|funded for \d)\b", re.I)
_UPPER_BOUND_EXP = re.compile(
    r"\b(?:maximum (?:of )?|no more than|at most|up to|less than|fewer than|under \d|débutant\w* à|jeune diplômé\w* à|moins de|jusqu['’]à|maximal|höchstens|bis zu)\b",
    re.I,
)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;•·\n])\s+|\n+|•", text or "") if s and s.strip()]


def find_years_requirement(text: str) -> Tuple[int, str]:
    """Retourne (années minimales exigées, phrase source). Ignore les mentions 'préféré/bonus' et les plafonds ('maximum of 2 years', 'débutant à 3 ans')."""
    best = (0, "")
    for sent in _sentences(text):
        if _SOFT.search(sent) or _NON_EXP_SENT.search(sent) or _UPPER_BOUND_EXP.search(sent):
            continue
        vals: List[int] = []
        for idx, rx in enumerate(_YEARS_PATTERNS):
            for m in rx.finditer(sent):
                v = int(m.group(1))
                if (0 if idx == 0 else 1) <= v <= 15:
                    vals.append(v)
        m2 = _YEARS_WORD.search(sent)
        if m2 and re.search(r"experience|expérience|background|role|roles|industry", sent, re.I):
            vals.append(_WORD_NUM[m2.group(1).lower()])
        if vals and re.search(r"experience|expérience|erfahrung|background|track record|industry|role", sent, re.I):
            v = min(vals)
            if v > best[0]:
                best = (v, sent[:260])
    return best


def find_new_grad_exclusion(text: str) -> str:
    for rx in NEW_GRAD_EXCLUSION:
        m = rx.search(text or "")
        if m:
            a = max(0, m.start() - 60)
            return (text[a : m.end() + 60]).replace("\n", " ").strip()
    return ""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def evidence_is_grounded(evidence: str, text: str) -> bool:
    """La citation du juge doit exister (quasi mot pour mot) dans l'annonce complète."""
    ev, tx = _norm(evidence), _norm(text)
    if len(ev) < 10:
        return False
    if ev in tx:
        return True
    words = ev.split()
    if len(words) < 5:
        return False
    shingles = [" ".join(words[i : i + 4]) for i in range(len(words) - 3)]
    return sum(1 for s in shingles if s in tx) / len(shingles) >= 0.7


def title_prefilter(job: JobRaw) -> Optional[str]:
    """Retourne un motif de rejet (str) ou None si l'offre doit continuer. 100 % gratuit."""
    t = job.title or ""
    if OFF_TOPIC_TITLE.search(t):
        return "hors-métier (titre)"
    if OFF_PROFILE_TITLE.search(t) and not AI_SAFETY_EXCEPTION.search(t):
        return "famille de métier hors profil (sécurité/infra/embarqué/front)"
    if TOO_SENIOR.search(t) and not JUNIOR_SIGNAL.search(t):
        return "titre trop senior"
    if not PLAUSIBLE_TITLE.search(t):
        return "titre sans lien avec ton profil"
    return None


def hard_regex_findings(job: JobRaw) -> List[Tuple[str, str]]:
    """Blocages déterministes tirés du texte (toujours « grounded » puisque extraits du texte)."""
    text = f"{job.title}\n{job.description_text or ''}"
    out: List[Tuple[str, str]] = []
    yrs, ev = find_years_requirement(job.description_text or "")
    if yrs >= 2:
        out.append((f"EXPERIENCE: {yrs} ans exigés", ev))
    ng = find_new_grad_exclusion(text)
    if ng:
        out.append(("NEW GRADS EXCLUS", ng))
    loc = job.location or ""
    desc = job.description_text or ""
    is_vie = bool(re.search(r"\bv\.?i\.?e\.?\b|volontariat international", text, re.I))
    if not is_vie:
        if US_AUTH.search(desc) and not SPONSOR_OK.search(desc):
            m = US_AUTH.search(desc)
            out.append(("AUTORISATION DE TRAVAIL (hors UE) exigée", desc[max(0, m.start() - 60) : m.end() + 60].replace("\n", " ")))
        elif NON_EU_LOC.search(loc) and not EU_LOC.search(loc) and not SPONSOR_OK.search(desc):
            out.append(("POSTE HORS UE sans sponsoring de visa mentionné", loc[:120]))
    return out


# --------------------------------------------------------------------------------------
# 3. EXTRACTION DU TEXTE UTILE (on ne tronque plus aveuglément)
# --------------------------------------------------------------------------------------
_REQ_HEAD = re.compile(
    r"(requirements?|qualifications?|what you(?:'|’)ll (?:need|bring)|what we(?:'|’)re looking for|who you are|about you|you have|you(?:'|’)ll have|"
    r"minimum|must have|basic qualifications|your profile|profil recherché|votre profil|vous avez|compétences|expérience|anforderungen|ihr profil|dein profil|qualifikation)",
    re.I,
)
_KEY_SENT = re.compile(
    r"(\d+\s*\+?\s*(?:years?|yrs?|ans|jahre)|years? of|new grad|recent grad|graduate|entry[- ]level|junior|interns?(?:hip)?s?\b|visa|sponsor|authori[sz]ed to work|work permit|"
    r"citizen|clearance|fluent|native|proficien|\bc1\b|\bc2\b|german|deutsch|dutch|power ?bi|tableau|phd|doctorate|master|bachelor|degree|"
    r"not (?:a )?(?:good )?fit|do not apply|should not apply|required|mandatory|must)",
    re.I,
)


def focus_text(desc: str, limit: int = 2600, key_cap: int = 1000) -> str:
    desc = (desc or "").strip()
    if len(desc) <= limit:
        return desc
    head = desc[:450]
    idx = None
    for m in _REQ_HEAD.finditer(desc, 450):
        idx = m.start()
        break
    if idx is not None:
        body = desc[max(450, idx - 30) : max(450, idx - 30) + (limit - 450)]
    else:
        half = (limit - 450) // 2
        body = desc[450 : 450 + half] + " [...] " + desc[-half:]
    seen = f"{head} {body}"
    extra: List[str] = []
    for s in _sentences(desc):
        if _KEY_SENT.search(s) and s[:60] not in seen:
            extra.append(s[:240])
        if sum(len(x) for x in extra) > key_cap:
            break
    return f"{head}\n...\n{body}\n[KEY SENTENCES]\n" + "\n".join(extra)


# --------------------------------------------------------------------------------------
# 4. CLIENT GROQ AVEC PACING PAR MODÈLE (quota TPM propre à chaque modèle)
# --------------------------------------------------------------------------------------
class Pacer:
    """Respecte le quota TPM d'un modèle : consommation réelle des 60 dernières secondes + requête estimée."""

    def __init__(self, tpm: int):
        self.tpm = tpm
        self.lock = threading.Lock()
        self.events: deque = deque()

    def wait(self, requested: int) -> None:
        while True:
            with self.lock:
                now = time.time()
                while self.events and now - self.events[0][0] > 60:
                    self.events.popleft()
                used = sum(t for _, t in self.events)
                if used + requested <= self.tpm or not self.events:
                    return
                sleep_for = 60 - (now - self.events[0][0]) + 0.1
            time.sleep(max(0.3, min(sleep_for, 20)))

    def record(self, tokens: int) -> None:
        with self.lock:
            self.events.append((time.time(), tokens))


def _extract_json(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    a, b = raw.find("{"), raw.rfind("}")
    return raw[a : b + 1] if a != -1 and b != -1 else raw


class GroqJudge:
    def __init__(self, model: str, api_key: str, tpm: int = 8000, usage_ratio: float = 0.85):
        from groq import Groq

        self.model = model
        self.client = Groq(api_key=api_key, max_retries=0, timeout=25.0)
        self.pacer = Pacer(int(tpm * usage_ratio))
        self.max_tokens = 700
        self._use_effort = True
        self.calls = 0
        self.failures = 0

    def build_user(self, job: JobRaw) -> str:
        return (
            f"{CANDIDATE_PROFILE}\n"
            f"JOB POSTING\nCompany: {job.company}\nTitle: {job.title}\nLocation: {job.location or 'n/a'}\n"
            f"Text:\n<<<\n{focus_text(job.description_text or '')}\n>>>"
        )

    def judge(self, job: JobRaw) -> Optional[OfferRequirements]:
        user = self.build_user(job)
        est = int((len(JUDGE_SYSTEM) + len(user)) / 3.2) + self.max_tokens
        for attempt in range(5):
            self.pacer.wait(est)
            kwargs = dict(
                model=self.model,
                messages=[{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}],
                temperature=0,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )
            if self._use_effort:
                kwargs["reasoning_effort"] = "low" if "gpt-oss" in self.model else "none" if "qwen" in self.model else None
                if kwargs["reasoning_effort"] is None:
                    kwargs.pop("reasoning_effort")
            try:
                resp = self.client.chat.completions.create(**kwargs)
                self.calls += 1
                used = getattr(getattr(resp, "usage", None), "total_tokens", est) or est
                self.pacer.record(int(used))
                data = _extract_json(resp.choices[0].message.content)
                return OfferRequirements.model_validate_json(data)
            except ValidationError:
                self.failures += 1
                continue
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "429" in msg or "rate_limit" in msg.lower():
                    m = re.search(r"try again in ([\d.]+)s", msg)
                    time.sleep(float(m.group(1)) + 0.5 if m else 6 * (attempt + 1))
                    continue
                if ("400" in msg or "reasoning_effort" in msg) and self._use_effort:
                    self._use_effort = False
                    continue
                self.failures += 1
                time.sleep(1.5)
        return None


# --------------------------------------------------------------------------------------
# 5. DÉCISION DÉTERMINISTE
# --------------------------------------------------------------------------------------
OFF_PROFILE_FAMILIES = {"security", "devops_infra", "data_analytics_bi", "other"}

# Garde-fou déterministe : un LLM ne peut pas déclarer « manquante » une compétence que Joshua possède déjà dans son corpus UTC/stages
CANDIDATE_KNOWN_SKILLS_RX = re.compile(
    r"\b(python|pytorch|tabular|tensorflow|keras|scikit|sklearn|lightgbm|xgboost|pandas|numpy|scipy|pyspark|spark|\br\b|sql|postgres\w*|oracle|sqlite|mongodb|"
    r"\bc\b|c\+\+|qt|kotlin|android|javascript|typescript|react|html|css|prolog|scilab|matlab|flask|fastapi|rest\b|api\w*|docker|container\w*|linux|unix|"
    r"git\b|github|ci/cd|conda|aws|amazon s3|\bs3\b|storage|networking|network|streamlit|tensorboard|latex|quarto|slurm|hpc|"
    r"statist\w*|math\w*|optim\w*|operations research|recherche opérationnelle|stochast\w*|markov|poisson|monte[- ]?carlo|probabilit\w*|"
    r"numerical|machine learning|deep learning|representation learning|computer vision|image|nlp|natural language|llm\w*|rag\b|agent\w*|transformer\w*|"
    r"langchain|llamaindex|pinecone|weaviate|vector|data science|data mining|data analysis|visuali[sz]ation|modeling|modélisation|algorithm\w*|"
    r"mlops|observability|model lifecycle|cloud[- ]?native|software architecture|code review|test\w*|debug\w*|"
    r"french|français|english|anglais)\b",
    re.IGNORECASE,
)


def filter_missing_skills(skills: List[str]) -> List[str]:
    """Retire de mandatory_skills_missing toute compétence déjà maîtrisée par Joshua."""
    out: List[str] = []
    for s in skills or []:
        s_clean = (s or "").strip()
        if not s_clean:
            continue
        if CANDIDATE_KNOWN_SKILLS_RX.search(s_clean):
            continue
        out.append(s_clean)
    return out


@dataclass
class Decision:
    accepted: bool
    reasons: List[str] = field(default_factory=list)
    family: str = "other"
    years: int = 0
    judged_by: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    targets_new_grads: bool = False
    pitch_hint: str = ""

    def to_dict(self) -> Dict:
        return self.__dict__.copy()


def decide(job: JobRaw, judgements: List[Tuple[str, OfferRequirements]]) -> Decision:
    full_text = f"{job.title}\n{job.description_text or ''}"
    is_vie = bool(re.search(r"\bv\.?i\.?e\.?\b|volontariat international", full_text, re.I))
    reasons: List[str] = []
    notes: List[str] = []
    for code, ev in hard_regex_findings(job):
        reasons.append(f"{code} — « {ev[:140]} »")

    years = 0
    family_votes: List[str] = []
    targets = False
    for model, j in judgements:
        tag = model.split("/")[-1]
        family_votes.append(j.role_family)
        targets = targets or j.targets_new_grads
        years = max(years, j.min_years_required)

        if j.min_years_required >= 2 and not _UPPER_BOUND_EXP.search(j.years_evidence or ""):
            if evidence_is_grounded(j.years_evidence, full_text):
                reasons.append(f"EXPERIENCE: {j.min_years_required} ans exigés [{tag}] — « {j.years_evidence[:140]} »")
            else:
                notes.append(f"[{tag}] annonce {j.min_years_required} ans mais citation introuvable -> ignoré")
        if j.min_years_required == 1 and j.internships_count == "no" and not _UPPER_BOUND_EXP.search(j.years_evidence or ""):
            if evidence_is_grounded(j.years_evidence, full_text):
                reasons.append(f"EXPERIENCE: 1 an en entreprise, stages exclus [{tag}] — « {j.years_evidence[:140]} »")
        if j.excludes_new_grads and not _UPPER_BOUND_EXP.search(j.new_grads_evidence or ""):
            if evidence_is_grounded(j.new_grads_evidence, full_text) and j.new_grads_evidence.strip() != (job.title or "").strip():
                reasons.append(f"NEW GRADS EXCLUS [{tag}] — « {j.new_grads_evidence[:140]} »")
            else:
                notes.append(f"[{tag}] new grads exclus mais citation introuvable -> ignoré")
        real_missing = filter_missing_skills(j.mandatory_skills_missing)
        if real_missing:
            ev_s = j.skills_evidence or ""
            has_spoken_lang = any(re.search(r"\b(german|deutsch|allemand|dutch|nederlands|spanish|italian|polish|swedish|japanese|arabic)\b", s, re.I) for s in real_missing)
            is_example_or_list = (
                not has_spoken_lang
                and bool(re.search(r"\b(such as|e\.g\.|for example|or similar|and/or|ideally|one or more)\b", ev_s, re.I))
                and bool(CANDIDATE_KNOWN_SKILLS_RX.search(ev_s))
            )
            if not is_example_or_list and evidence_is_grounded(ev_s, full_text):
                reasons.append(f"COMPÉTENCE OBLIGATOIRE ABSENTE ({', '.join(real_missing[:4])}) [{tag}] — « {ev_s[:140]} »")
            else:
                notes.append(f"[{tag}] compétences manquantes {real_missing} (liste d'exemples ou sans citation) -> ignoré")
        if not is_vie and j.requires_work_authorization_outside_eu and evidence_is_grounded(j.work_auth_evidence, full_text):
            reasons.append(f"AUTORISATION DE TRAVAIL hors UE [{tag}] — « {j.work_auth_evidence[:140]} »")
        if j.degree_required == "phd" and re.search(r"\b(ph\.?d|doctorate|doctorat)\b", full_text, re.I) and not re.search(
            r"(ph\.?d\.? (?:position|student|candidate)|doctoral (?:position|researcher|student)|thèse|cifre|doctorant)", full_text, re.I
        ):
            reasons.append(f"DOCTORAT exigé [{tag}]")

    family = max(set(family_votes), key=family_votes.count) if family_votes else "other"
    if judgements and all(f in OFF_PROFILE_FAMILIES for f in family_votes):
        reasons.append(f"FAMILLE DE MÉTIER hors profil ({'/'.join(sorted(set(family_votes)))})")

    # dédoublonnage en conservant l'ordre
    seen, uniq = set(), []
    for r in reasons:
        k = r.split(" — ")[0]
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return Decision(
        accepted=not uniq,
        reasons=uniq,
        family=family,
        years=years,
        judged_by=[m for m, _ in judgements],
        notes=notes,
        targets_new_grads=targets,
    )


# --------------------------------------------------------------------------------------
# 6. CACHE (un jugement n'est payé qu'une fois par offre et par version)
# --------------------------------------------------------------------------------------
def fingerprint(job: JobRaw) -> str:
    h = hashlib.sha1(f"{SCREEN_VERSION}|{job.title}|{(job.description_text or '')[:6000]}".encode("utf-8", "ignore"))
    return h.hexdigest()[:16]


class EvalCache:
    def __init__(self, path: str = "eval_cache.json"):
        self.path = path
        self.data: Dict[str, Dict] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def get(self, job: JobRaw) -> Optional[Dict]:
        e = self.data.get(job.id)
        if e and e.get("fp") == fingerprint(job):
            return e
        return None

    def put(self, job: JobRaw, decision: Decision) -> None:
        self.data[job.id] = {
            "fp": fingerprint(job),
            "ts": int(time.time()),
            "company": job.company,
            "title": job.title,
            "decision": decision.to_dict(),
        }

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)


# --------------------------------------------------------------------------------------
# 7. ORCHESTRATION DES JUGES (2 passes, modèles différents, en parallèle)
# --------------------------------------------------------------------------------------
class Screener:
    def __init__(self, api_key: str, models: List[str], tpm: int = 8000):
        self.judges = {m: GroqJudge(m, api_key, tpm) for m in models}
        self.models = models

    def _run_pass(self, jobs: List[JobRaw], assign: Dict[str, str], progress_label: str) -> Dict[str, Optional[OfferRequirements]]:
        by_model: Dict[str, List[JobRaw]] = {m: [] for m in self.models}
        for j in jobs:
            by_model[assign[j.id]].append(j)
        results: Dict[str, Optional[OfferRequirements]] = {}
        lock = threading.Lock()
        done = [0]
        total = len(jobs)

        def worker(model: str) -> None:
            for j in by_model[model]:
                r = self.judges[model].judge(j)
                with lock:
                    results[j.id] = r
                    done[0] += 1
                    if done[0] % 10 == 0 or done[0] == total:
                        print(f"   [{progress_label}] {done[0]}/{total} offres jugées", flush=True)

        threads = [threading.Thread(target=worker, args=(m,), daemon=True) for m in self.models if by_model[m]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def screen(self, jobs: List[JobRaw]) -> Dict[str, Decision]:
        """Passe A (juge 1..n en round-robin) puis passe B (autre modèle) sur les offres encore acceptées."""
        out: Dict[str, Decision] = {}
        if not jobs:
            return out
        n = len(self.models)
        assign_a = {j.id: self.models[i % n] for i, j in enumerate(jobs)}
        res_a = self._run_pass(jobs, assign_a, "Passe A")

        survivors: List[JobRaw] = []
        dec_a: Dict[str, Decision] = {}
        for j in jobs:
            ra = res_a.get(j.id)
            if ra is None:
                out[j.id] = Decision(False, ["JUGE IA INDISPONIBLE (offre non évaluée, à relancer)"], notes=["no-cache"])
                continue
            d = decide(j, [(assign_a[j.id], ra)])
            dec_a[j.id] = d
            if d.accepted:
                survivors.append(j)
            else:
                out[j.id] = d
        if survivors and n >= 2:
            assign_b = {}
            for j in survivors:
                ma = assign_a[j.id]
                assign_b[j.id] = self.models[(self.models.index(ma) + 1) % n]
            res_b = self._run_pass(survivors, assign_b, "Passe B (confirmation)")
            for j in survivors:
                rb = res_b.get(j.id)
                ra = res_a[j.id]
                js = [(assign_a[j.id], ra)] + ([(assign_b[j.id], rb)] if rb is not None else [])
                d = decide(j, js)
                if rb is None:
                    d.notes.append("confirmation indisponible (1 seul juge)")
                out[j.id] = d
        else:
            for j in survivors:
                out[j.id] = dec_a[j.id]
        return out


# --------------------------------------------------------------------------------------
# 8. CONVERSION DECISION -> PROCESSEDJOB (Pondération Multi-Critères & Pitch UTC)
# --------------------------------------------------------------------------------------
def decision_to_processed_job(job: JobRaw, decision: Decision) -> "ProcessedJob":
    from src.models import ContractType, JobExtraction, ProcessedJob, ProfileCategory

    t_low = (job.title or "").lower()
    full_low = f"{job.title or ''} {job.description_text or ''} {job.location or ''}".lower()
    fam = decision.family

    is_vie = bool(re.search(r"\bv\.?i\.?e\.?\b|volontariat international", full_low, re.I))
    is_phd = bool(re.search(r"\b(phd|ph\.d|thèse|doctorat|doctoral|cifre)\b", t_low, re.I))
    is_research_org = any(w in (job.company or "").lower() for w in ["cea", "inria", "cern", "onera", "cnrs"])

    if is_vie:
        contract = ContractType.VIE
    elif is_phd:
        contract = ContractType.THESE_CIFRE
    elif "graduate" in t_low or "fellow" in t_low:
        contract = ContractType.GRADUATE_PROGRAM
    elif "cdd" in full_low or is_research_org and "cdd" in (job.company or "").lower():
        contract = ContractType.CDD
    else:
        contract = ContractType.CDI

    # Mapping de la famille métier et du titre vers la catégorie pondérée de Joshua
    if fam in ("operations_research", "quant") or any(
        w in t_low
        for w in [
            "operations research", "recherche opérationnelle", "optimisation", "optimization",
            "stochastic", "stochastique", "quant", "quantitative", "value engineer",
            "decision science", "model validation", "model risk", "safety", "alignment", "trustworthy",
        ]
    ):
        prof = ProfileCategory.RO_MODELISATION_QUANT
        cv_folder = "5_Data_IA_Engineering"
        base_score = 83
        pitch = (
            "Mettre en avant le Label Mod'Math UTC (RO04 Optimisation linéaire/non-linéaire & graphes, RO05 Processus stochastiques Markov/Poisson/files d'attente, "
            "SY02 Statistiques & Monte-Carlo, MT09 Analyse numérique), le contrôle statistique garanti du risque chez Epiconcept (SGR, bornes de Hoeffding, abstention sur mammographies GMIC) "
            "et la modélisation géométrique 4D du globule rouge au laboratoire BMBI (TZ2)."
        )
    elif fam in ("solutions_architecture", "forward_deployed") or any(
        w in t_low
        for w in ["solutions architect", "solution architect", "application engineer", "forward deployed", "deployment strategist", "customer engineer", "field engineer", "architecte"]
    ):
        prof = ProfileCategory.ARCHITECTE_AI_DATA
        cv_folder = "1_Consulting_Tech_Data_Strategie"
        base_score = 82
        pitch = (
            "Mettre en avant ton profil hybride Ingénieur UTC GI + Mod'Math capable de concevoir l'architecture IA de bout en bout et de la défendre face aux décideurs : "
            "déploiement de 20 configurations LLMs 4-bit sous contrainte VRAM 40 Go avec vérification anti-hallucination (CATH-LLM Epiconcept, F1=0,88), "
            "architecture full-stack Flask/React/S3 + PyTorch Tabular chez Aubay Innov' (F1=0,91), et capsules exécutables Docker/Quarto."
        )
    elif fam in ("product_management", "project_management") or any(
        w in t_low for w in ["chef de projet", "product manager", "product owner", "project manager", "program manager", "pilote"]
    ):
        prof = ProfileCategory.CHEF_DE_PROJET_PM
        cv_folder = "4_Product_Management_Tech"
        base_score = 79
        pitch = (
            "Mettre en avant le pilotage de bout en bout de tes 2 projets R&D chez Epiconcept (cadrage méthodologique avec les épidémiologistes ECDC, arbitrage coût/risque/VRAM, "
            "livraison de capsules reproductibles Docker & Quarto) ainsi que la conception produit complète de Custos (Kotlin) et PDF Live Notes."
        )
    elif is_vie:
        prof = ProfileCategory.VIE_INTERNATIONAL
        cv_folder = "5_Data_IA_Engineering"
        base_score = 80
        pitch = (
            "Mettre en avant l'éligibilité V.I.E immédiate (Ingénieur UTC diplômé 2026, Anglais B2 professionnel Linguaskill 179), "
            "les 12 mois de R&D cumulés chez Epiconcept (Vision GMIC & LLMs cliniques) et Aubay Innov' (PyTorch Tabular, API REST Flask/React), et le Label Mod'Math."
        )
    elif is_research_org or is_phd or fam == "ml_research":
        prof = ProfileCategory.RECHERCHE_RD_CIFRE
        cv_folder = "5_Data_IA_Engineering"
        base_score = 78 if is_phd else 81
        pitch = (
            "Mettre en avant tes travaux de recherche appliquée : TZ2 au laboratoire BMBI (surfaces implicites neuronales 3D/4D IGR/SIREN, perte Eikonal, courbures par autograd d'ordre 2, "
            "IoU 99,65 %), Epiconcept (classification sélective SGR/Hoeffding sur mammographies GMIC AUC=0,889 & évaluation LLMs MIMIC-IV) et Aubay Innov' (GANDALF/TabTransformer)."
        )
    elif fam == "sales" or any(w in t_low for w in ["pre-sales", "presales", "sales engineer", "solutions engineer", "avant-vente"]):
        prof = ProfileCategory.TECH_SALES_PRESALES
        cv_folder = "2_Tech_Sales_SDR_BDR"
        base_score = 77
        pitch = (
            "Mettre en avant ta double compétence technique profonde (IA/Mod'Math UTC, LLMs, Vision, Optimisation) et pédagogique "
            "(création de capsules interactives de vulgarisation scientifique chez Epiconcept, démonstrateurs Flask/React chez Aubay)."
        )
    elif fam == "consulting" or "consultant" in t_low:
        prof = ProfileCategory.CONSULTANT_DATA_IA
        cv_folder = "1_Consulting_Tech_Data_Strategie"
        base_score = 75
        pitch = (
            "Mettre en avant ton expérience en cabinet/ESN R&D chez Aubay Innov' (détection d'anomalies sur données tabulaires mixtes avec PyTorch Tabular & Isolation Forest, "
            "intégration API Flask/React/S3) et chez Epiconcept (LLMs & Computer Vision), ainsi que ton diplôme d'Ingénieur UTC GI."
        )
    elif fam in ("ml_engineering", "data_science"):
        prof = ProfileCategory.DATA_SCIENCE_ENGINEER
        cv_folder = "5_Data_IA_Engineering"
        base_score = 79
        pitch = (
            "Mettre en avant tes 12 mois de R&D Data Science & ML : Epiconcept (Deep Learning Vision GMIC sur 300+ Go de mammographies + LLMs ouverts 4-bit MedGemma/Qwen3/Mistral "
            "avec vérification automatique `evidence_is_grounded` F1=0,88) et Aubay Innov' (PyTorch Tabular GANDALF/FT-Transformer + Isolation Forest F1=0,91)."
        )
    else:
        prof = ProfileCategory.SOFTWARE_DATA_ENG
        cv_folder = "5_Data_IA_Engineering"
        base_score = 75
        pitch = (
            "Mettre en avant ta formation d'Ingénieur UTC Génie Informatique (Python, C++17/Qt LO21, Kotlin, SQL/PySpark NF26, Linux/Docker) "
            "et tes réalisations logicielles complètes (back-end Flask/FastAPI, Custos Android, PDF Live Notes en SSE, pipelines ETL Big Data)."
        )

    if decision.targets_new_grads or JUNIOR_SIGNAL.search(job.title or "") or is_research_org:
        base_score = min(88, base_score + 4)

    tech_list: List[str] = []
    for label, rx in [
        ("Python", r"\bpython\b"),
        ("PyTorch", r"\bpytorch\b"),
        ("SQL", r"\bsql\b"),
        ("C++", r"c\+\+"),
        ("Spark", r"\b(?:py)?spark\b"),
        ("Docker", r"\bdocker\b"),
        ("LLMs / GenAI", r"\b(?:llm\w*|genai|generative ai|rag|agent\w*)\b"),
        ("Computer Vision", r"\b(?:computer vision|vision par ordinateur|image processing)\b"),
        ("Optimisation / RO", r"\b(?:optimi[sz]ation|operations research|recherche opérationnelle|stochastic|stochastique)\b"),
        ("Statistiques / Quant", r"\b(?:statistic\w*|statistique\w*|quant\w*|monte[- ]?carlo)\b"),
        ("Linux", r"\blinux\b"),
        ("FastAPI / Flask", r"\b(?:fastapi|flask)\b"),
        ("React / TS", r"\b(?:react|typescript)\b"),
        ("AWS / Cloud", r"\b(?:aws|s3|gcp|azure)\b"),
    ]:
        if re.search(rx, full_low, re.I):
            tech_list.append(label)

    is_abroad = is_vie or not bool(re.search(r"\b(france|paris|saclay|grenoble|lyon|toulouse|nantes|bordeaux|lille|rennes|sophia|annecy|montpellier)\b", (job.location or "").lower()))

    if decision.accepted:
        judges_str = ", ".join(m.split("/")[-1] for m in decision.judged_by) or "Regex"
        exp_badge = "🟢 Cible Jeune Diplômé / 0-1 an" if (decision.targets_new_grads or decision.years <= 1) else f"🟡 Exp={decision.years}a"
        reason = (
            f"✅ [Validé par Double Juge IA ({judges_str}) + Garde-fous | {exp_badge} | Famille: {fam}] "
            f"Aucune exclusion New Grad, expérience requise = {decision.years} an(s), aucune compétence obligatoire hors profil."
        )
    else:
        reason = "❌ [Rejeté] " + " ; ".join(decision.reasons[:3])

    ext = JobExtraction(
        matched_profile=prof if decision.accepted else ProfileCategory.HORS_CIBLE,
        is_relevant=decision.accepted,
        raw_cv_score=base_score if decision.accepted else 0,
        match_score=base_score if decision.accepted else 0,
        contract_type=contract,
        years_of_experience=decision.years if decision.accepted else max(2, decision.years),
        is_abroad_or_vie=is_abroad,
        tech_stack=tech_list[:8],
        salary_min_eur=None,
        relevance_reason=reason,
        cv_pitch=pitch if decision.accepted else None,
        recommended_cv_folder=cv_folder,
    )
    ext.apply_weighted_coefficients(job.company)
    return ProcessedJob(raw=job, extraction=ext)

