from enum import Enum
import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileCategory(str, Enum):
    # TIER S (x1.25) — Le Graal : Maths/RO/Stats/Fiabilité + Humain + Pouvoir d'Architecte
    RO_MODELISATION_QUANT = "RO_MODELISATION_QUANT"
    ARCHITECTE_AI_DATA = "ARCHITECTE_AI_DATA"

    # TIER A (x1.12) — Leadership & R&D d'équipe / International
    CHEF_DE_PROJET_PM = "CHEF_DE_PROJET_PM"
    RECHERCHE_RD_CIFRE = "RECHERCHE_RD_CIFRE"
    VIE_INTERNATIONAL = "VIE_INTERNATIONAL"

    # TIER B (x0.95) — Les classiques solides qui recrutent en volume
    DATA_SCIENCE_ENGINEER = "DATA_SCIENCE_ENGINEER"
    TECH_SALES_PRESALES = "TECH_SALES_PRESALES"

    # TIER C (x0.80) — Filet de sécurité ("Il me faut un travail")
    CONSULTANT_DATA_IA = "CONSULTANT_DATA_IA"
    SOFTWARE_DATA_ENG = "SOFTWARE_DATA_ENG"

    # Legacy aliases kept for backward compatibility
    AI_DEPLOY_MLOPS = "ARCHITECTE_AI_DATA"
    THESE_CIFRE_RD = "RECHERCHE_RD_CIFRE"

    # TIER F (x0.00) — Dégagé automatiquement ("Vraiment horrible / Hors cible")
    HORS_CIBLE = "HORS_CIBLE"


PROFILE_LABELS: Dict[ProfileCategory, str] = {
    ProfileCategory.RO_MODELISATION_QUANT: "📐 [Tier S ×1.25] Recherche Opérationnelle, Modélisation Stochastique & Quant/Validation IA",
    ProfileCategory.ARCHITECTE_AI_DATA: "🏗️ [Tier S ×1.25] Solutions Architect / Application Engineer / Forward Deployed IA",
    ProfileCategory.CHEF_DE_PROJET_PM: "📋 [Tier A ×1.12] Chef de Projet R&D / Technical Product Owner IA",
    ProfileCategory.RECHERCHE_RD_CIFRE: "🧪 [Tier A ×1.12] Ingénieur-Chercheur / R&D Appliquée (CEA, Inria, Industrie)",
    ProfileCategory.VIE_INTERNATIONAL: "🌍 [Tier A ×1.12] V.I.E & International (Quant / IA / Architecture)",
    ProfileCategory.DATA_SCIENCE_ENGINEER: "🔬 [Tier B ×0.95] Data Scientist / ML & AI Engineer (Classique)",
    ProfileCategory.TECH_SALES_PRESALES: "🤝 [Tier B ×0.95] Pre-Sales / Sales Engineer / Ingénieur d'Affaires Tech",
    ProfileCategory.CONSULTANT_DATA_IA: "💼 [Tier C ×0.80] Consulting Data & IA / Transformation (Filet de sécurité)",
    ProfileCategory.SOFTWARE_DATA_ENG: "⚙️ [Tier C ×0.80] Data Engineer / Software Engineer C++ & Python (Filet de sécurité)",
    ProfileCategory.HORS_CIBLE: "❌ [Tier F ×0.00] Hors cible / Écarté",
}

# Coefficients multiplicateurs par catégorie de mission (du meilleur au pire)
MISSION_COEFFICIENTS: Dict[ProfileCategory, Tuple[str, float]] = {
    ProfileCategory.RO_MODELISATION_QUANT: ("Tier S", 1.18),
    ProfileCategory.ARCHITECTE_AI_DATA: ("Tier S", 1.18),
    ProfileCategory.CHEF_DE_PROJET_PM: ("Tier A", 1.06),
    ProfileCategory.RECHERCHE_RD_CIFRE: ("Tier A", 1.05),
    ProfileCategory.VIE_INTERNATIONAL: ("Tier A", 1.05),
    ProfileCategory.DATA_SCIENCE_ENGINEER: ("Tier B", 0.94),
    ProfileCategory.TECH_SALES_PRESALES: ("Tier B", 0.94),
    ProfileCategory.CONSULTANT_DATA_IA: ("Tier C", 0.82),
    ProfileCategory.SOFTWARE_DATA_ENG: ("Tier C", 0.80),
    ProfileCategory.HORS_CIBLE: ("Tier F", 0.00),
}

# Modificateurs d'entreprise (Congés/RTT + Salaire + Prestige Global Tech/Quant vs ESN "Pion")
ROYAL_COMPANIES_PATTERN = re.compile(
    r"\b(cea|inria|cern|onera|cnes|ifpen|lne|anssi|edf|rte|engie|air france|sncf|ratp|thales|safran|airbus|naval group|mbda|dassault aviation|bnp|société générale|societe generale|axa|natixis|amundi|crédit agricole|credit agricole|scor|banque de france|bpifrance|sanofi|hermès|hermes|l'oréal|loreal|bosch)\b",
    re.IGNORECASE,
)

GLOBAL_BIG_TECH_QUANT_AI_PATTERN = re.compile(
    r"\b(openai|anthropic|mistral|databricks|datadog|snowflake|palantir|stripe|cloudflare|scale ai|scaleai|cohere|deepl|black forest|isomorphic|helsing|elevenlabs|perplexity|huggingface|hugging face|linear|ramp|notion|sierra|harvey|anysphere|cursor|imc|optiver|flow traders|jane street|janestreet|citadel|two sigma|qrt|qube|squarepoint|cfm|adyen|airbnb|uber|booking|spotify|google|deepmind|meta|microsoft|nvidia|apple|amazon|aws|synthesia)\b",
    re.IGNORECASE,
)

TOP_TECH_EDITORS_PATTERN = re.compile(
    r"\b(mathworks|dassault systèmes|dassault systemes|artelys|hexaly|localsolver|eurodecision|cosling|gurobi|amadeus|ibm|sas|dataiku|criteo|elastic|grafanalabs|grafana|celonis|mongodb|twilio|pinterest|figma|coinbase|robinhood|duolingo|algolia|alan|qonto|pigment|contentsquare|ansys|doctolib|mirakl|dust|photoroom|gladia|aircall|blablacar|getyourguide|n26|hellofresh|n8n|lovable|ubisoft)\b",
    re.IGNORECASE,
)

ESN_CONSEIL_PENALTY_PATTERN = re.compile(
    r"\b(alten|altran|capgemini|sopra|atos|cgi|devoteam|accenture|deloitte|pwc|ey|kpmg|wavestone|onepoint|sia partners|aubay|akka|modis|sii|infotel|econocom|inetum|astek)\b",
    re.IGNORECASE,
)


def compute_company_modifier(company_name: str) -> Tuple[str, int]:
    """
    Calcule le bonus/malus lié à l'entreprise (Big Tech/Quant/AI mondial, Grands Groupes 45j RTT, Éditeurs vs ESN).
    """
    c = company_name or ""
    if GLOBAL_BIG_TECH_QUANT_AI_PATTERN.search(c):
        return ("Big Tech / Quant / AI Leader Mondial (Compensation Top 1% & Impact Global)", +9)
    if ROYAL_COMPANIES_PATTERN.search(c):
        return ("Royal (42-48j RTT/Congés & Mobilité)", +8)
    if TOP_TECH_EDITORS_PATTERN.search(c):
        return ("Éditeur Tech / Pépite RO & SaaS (Fort Salaire & Culture Produit)", +6)
    if ESN_CONSEIL_PENALTY_PATTERN.search(c):
        return ("ESN / Conseil (Filet de sécurité : moins de RTT / risque mission pion)", -10)
    return ("Standard (~32-36j RTT/Congés)", 0)


class ContractType(str, Enum):
    CDI = "CDI"
    VIE = "VIE"
    THESE_CIFRE = "THESE_CIFRE"
    GRADUATE_PROGRAM = "GRADUATE_PROGRAM"
    CDD = "CDD"
    STAGE_ALTERNANCE = "STAGE_ALTERNANCE"
    AUTRE = "AUTRE"


class JobRaw(BaseModel):
    """Normalized raw job extracted from an ATS or job API."""
    id: str = Field(..., description="Unique job identifier / reference within the ATS")
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    url: str = Field(..., description="Direct application or job detail URL")
    location: Optional[str] = Field(None, description="Job location / workplace")
    description_text: Optional[str] = Field(None, description="Cleaned description text for LLM inference")
    date_posted: Optional[str] = Field(None, description="Publication date or timestamp")
    ats_type: str = Field(..., description="Source ATS (workday, oracle_hcm, ashby, france_travail, etc.)")


class JobExtraction(BaseModel):
    """Structured extraction personalized for Joshua Nancey (UTC Graduated Engineer)."""
    matched_profile: ProfileCategory = Field(
        ...,
        description="Catégorie de profil correspondant le mieux à l'offre parmi : "
                    "RO_MODELISATION_QUANT, ARCHITECTE_AI_DATA, CHEF_DE_PROJET_PM, "
                    "RECHERCHE_RD_CIFRE, VIE_INTERNATIONAL, DATA_SCIENCE_ENGINEER, "
                    "TECH_SALES_PRESALES, CONSULTANT_DATA_IA, SOFTWARE_DATA_ENG, HORS_CIBLE."
    )
    is_relevant: bool = Field(
        ...,
        description="Vrai si l'offre est ouverte à un Ingénieur UTC diplômé (0-3 ans d'exp max) "
                    "et N'EST PAS un stage, une alternance, un post-doc, ou un poste horrible (support N1/N2, QA manuelle, cold calling pur)."
    )
    raw_cv_score: Optional[int] = Field(
        None,
        description="Score technique brut d'adéquation avec le CV de Joshua (0 à 100) avant application du coefficient de mission."
    )
    match_score: int = Field(
        ...,
        description="Score de compatibilité (0 à 100) avec le parcours et les préférences de Joshua."
    )
    tier_label: Optional[str] = Field(
        None,
        description="Palier de priorité calculé automatiquement (Tier S, Tier A, Tier B, Tier C, Tier F)."
    )
    mission_coef: Optional[float] = Field(
        None,
        description="Coefficient multiplicateur de la mission (ex: 1.25 pour Tier S, 1.12 pour Tier A, 0.95 pour Tier B, 0.80 pour Tier C)."
    )
    company_env_label: Optional[str] = Field(
        None,
        description="Catégorie d'entreprise (Royal 42-48j RTT, Éditeur Tech, Standard, ESN/Conseil)."
    )
    company_env_bonus: Optional[int] = Field(
        None,
        description="Bonus/Malus en points lié à l'entreprise (+10, +7, 0, -12)."
    )
    score_breakdown: Optional[str] = Field(
        None,
        description="Explication lisible du calcul du score pondéré."
    )
    contract_type: ContractType = Field(
        ...,
        description="Type de contrat : CDI, VIE, THESE_CIFRE, GRADUATE_PROGRAM, CDD, STAGE_ALTERNANCE (à exclure), ou AUTRE."
    )
    years_of_experience: Optional[int] = Field(
        0,
        description="Années d'expérience minimum exigées (hors stages). Mettre 0 si jeune diplômé / débutant accepté."
    )
    is_abroad_or_vie: bool = Field(
        False,
        description="Vrai si le poste est un V.I.E ou situé hors de France."
    )
    tech_stack: Optional[List[str]] = Field(
        default_factory=list,
        description="Liste des technologies, frameworks et méthodes mathématiques mentionnés."
    )
    salary_min_eur: Optional[float] = Field(
        None,
        description="Salaire minimum annuel brut estimé en euros si mentionné, sinon null."
    )
    relevance_reason: str = Field(
        ...,
        description="Explication concise (1 phrase) de pourquoi cette offre correspond ou non."
    )
    cv_pitch: Optional[str] = Field(
        None,
        description="Conseil personnalisé pour Joshua : quelles expériences précises de son parcours "
                    "(Label Mod'Math RO04/RO05/SY02/MT09, Stage TN10 Epiconcept Vision GMIC & SGR Hoeffding / CATH-LLM MIMIC, "
                    "Stage TN09 Aubay PyTorch Tabular, Projet TZ2 BMBI Globule Rouge Kuchel & Capsules 4D, SY32, SY09, NF26, Custos) mettre en avant."
    )
    recommended_cv_folder: Optional[str] = Field(
        None,
        description="Le dossier de CV de Joshua le plus adapté."
    )
    cold_email_draft: Optional[str] = Field(
        None,
        description="Brouillon court et percutant de mail / message d'approche directe."
    )

    @field_validator("years_of_experience", mode="before")
    @classmethod
    def validate_experience(cls, v) -> int:
        if v is None:
            return 0
        v_int = int(v)
        if v_int < 0 or v_int > 40:
            return 0
        return v_int

    @field_validator("tech_stack", mode="before")
    @classmethod
    def validate_tech_stack(cls, v) -> List[str]:
        if v is None:
            return []
        return list(v)

    @field_validator("match_score", mode="before")
    @classmethod
    def validate_score(cls, v) -> int:
        if v is None:
            return 0
        return max(0, min(100, int(v)))

    @model_validator(mode="after")
    def enforce_graduate_rules(self) -> "JobExtraction":
        """Hard deterministic guardrails: No internships/apprenticeships, and MAX 1 year required experience (>=2 years is dead for a new grad)."""
        if self.contract_type == ContractType.STAGE_ALTERNANCE:
            self.is_relevant = False
            self.matched_profile = ProfileCategory.HORS_CIBLE
            self.match_score = 0
        elif self.years_of_experience is not None and self.years_of_experience >= 2:
            self.is_relevant = False
            self.matched_profile = ProfileCategory.HORS_CIBLE
            self.match_score = 0
        elif self.matched_profile == ProfileCategory.HORS_CIBLE:
            self.is_relevant = False
            self.match_score = 0
        return self

    def apply_weighted_coefficients(self, company_name: str) -> None:
        """
        Applique de manière déterministe le coefficient de mission (Tier S/A/B/C),
        le bonus/malus d'expérience (0 an vs 1 an), et le bonus/malus d'entreprise.
        """
        if not self.is_relevant or self.matched_profile == ProfileCategory.HORS_CIBLE or (self.years_of_experience or 0) >= 2:
            self.is_relevant = False
            self.matched_profile = ProfileCategory.HORS_CIBLE
            self.tier_label = "Tier F"
            self.mission_coef = 0.0
            self.match_score = 0
            self.score_breakdown = "Offre écartée (Hors cible ou >= 2 ans d'expérience)"
            return

        base = self.raw_cv_score if self.raw_cv_score is not None else self.match_score
        base = max(40, min(90, int(base)))
        self.raw_cv_score = base

        tier, coef = MISSION_COEFFICIENTS.get(self.matched_profile, ("Tier B", 0.94))
        env_label, env_bonus = compute_company_modifier(company_name)

        # Bonus/Malus d'expérience :
        # 0 an (New Grad / Junior explicite) : +4 pts
        # 1 an (jouable directement en combinant ses 2 stages R&D de 6 mois = 12 mois) : +2 pts
        yrs = self.years_of_experience or 0
        exp_mod = +4 if yrs == 0 else +2
        exp_label = "Exp 0a New Grad (+4)" if yrs == 0 else "Exp 1a Stages combinés (+2)"

        weighted = round(base * coef + env_bonus + exp_mod)
        final_score = max(15, min(99, weighted))

        self.tier_label = tier
        self.mission_coef = coef
        self.company_env_label = env_label
        self.company_env_bonus = env_bonus
        self.match_score = final_score
        sign = "+" if env_bonus >= 0 else ""
        self.score_breakdown = (
            f"Base IA Groq {base}% × {tier} (×{coef:.2f}) {sign}{env_bonus} pts [{env_label}] | {exp_label} = {final_score}%"
        )


class ProcessedJob(BaseModel):
    """Job enriched with LLM extraction metadata."""
    raw: JobRaw
    extraction: JobExtraction
