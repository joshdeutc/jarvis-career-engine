"""
Générateur haute-fidélité des 8 CV ciblés (FR & EN) en PDF 1 page A4 via PyMuPDF (fitz),
alignés sur les sources LaTeX de Candidatures/ et CV_latex/, avec photo, liens cliquables
et typographie vectorielle.
"""
import base64
import os
import shutil
import subprocess
from pathlib import Path
import fitz  # PyMuPDF

BASE_CAND = Path(r"C:\Users\jo\Documents\Academy\rapport_TN10\Candidatures")
CV_LATEX_DIR = Path(r"C:\Users\jo\Documents\Academy\rapport_TN10\CV_latex")
PORTFOLIO_CV_DIR = Path(r"C:\Users\jo\Documents\Personnal_project\Jarvis_my_brother\portfolio\cv")
PHOTO_PATH = BASE_CAND / "0_Ressources_Communes" / "photo_cv.jpg"

PORTFOLIO_CV_DIR.mkdir(parents=True, exist_ok=True)


def get_photo_b64() -> str:
    if PHOTO_PATH.exists():
        return "data:image/jpeg;base64," + base64.b64encode(PHOTO_PATH.read_bytes()).decode("ascii")
    return ""


CSS_STYLE = """
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 8.7pt;
    line-height: 1.24;
    color: #111827;
    margin: 0;
    padding: 0;
}
h1 {
    font-size: 18pt;
    font-weight: bold;
    color: #0f172a;
    margin: 0 0 2pt 0;
    letter-spacing: 0.3pt;
}
.subtitle {
    font-size: 10.2pt;
    font-weight: bold;
    color: #1e3a8a;
    margin: 0 0 2pt 0;
}
.tagline {
    font-size: 8.2pt;
    color: #374151;
    margin: 0;
}
.contact {
    font-size: 7.9pt;
    text-align: right;
    color: #1f2937;
    line-height: 1.3;
}
.contact a {
    color: #1e40af;
    text-decoration: none;
}
.section-title {
    font-size: 9.6pt;
    font-weight: bold;
    color: #1e3a8a;
    text-transform: uppercase;
    letter-spacing: 0.5pt;
    border-bottom: 1pt solid #1e3a8a;
    padding-bottom: 1.5pt;
    margin-top: 6.5pt;
    margin-bottom: 3.5pt;
}
.entry-header {
    width: 100%;
    margin-top: 2.5pt;
    margin-bottom: 0.5pt;
}
.entry-org {
    font-size: 8.9pt;
    font-weight: bold;
    color: #0f172a;
}
.entry-date {
    font-size: 8.2pt;
    font-style: italic;
    color: #374151;
    text-align: right;
}
.entry-role {
    font-size: 8.4pt;
    font-style: italic;
    color: #1e3a8a;
}
.entry-loc {
    font-size: 8.0pt;
    font-style: italic;
    color: #4b5563;
    text-align: right;
}
ul {
    margin-top: 1.5pt;
    margin-bottom: 2.5pt;
    padding-left: 12pt;
}
li {
    margin-bottom: 1.5pt;
    text-align: justify;
}
.skills-table {
    width: 100%;
    margin-top: 2pt;
    font-size: 8.2pt;
}
.skills-table td {
    vertical-align: top;
    padding-right: 6pt;
    padding-bottom: 2pt;
}
"""


def build_header_html(subtitle: str, tagline: str, loc_line: str) -> str:
    return f"""
    <table style="width: 100%; margin-bottom: 2pt;">
        <tr>
            <td style="width: 63%; vertical-align: middle;">
                <h1>Joshua NANCEY</h1>
                <div class="subtitle">{subtitle}</div>
                <div class="tagline">{tagline}</div>
            </td>
            <td style="width: 37%; vertical-align: middle;" class="contact">
                <div><a href="mailto:joshua.nancey@etu.utc.fr">joshua.nancey@etu.utc.fr</a> &bull; +33 7 49 15 69 60</div>
                <div><a href="https://github.com/joshdeutc">github.com/joshdeutc</a> &bull; <a href="https://joshdeutc.github.io">joshdeutc.github.io</a></div>
                <div><a href="https://www.linkedin.com/in/joshua-nancey-3218171a2">linkedin.com/in/joshua-nancey</a></div>
                <div>{loc_line}</div>
            </td>
        </tr>
    </table>
    """


def entry_block(org: str, date: str, role: str = "", loc: str = "", bullets: list[str] = None) -> str:
    html = f"""
    <table class="entry-header">
        <tr>
            <td class="entry-org">&#9656; {org}</td>
            <td class="entry-date">{date}</td>
        </tr>
    """
    if role or loc:
        html += f"""
        <tr>
            <td class="entry-role">{role}</td>
            <td class="entry-loc">{loc}</td>
        </tr>
        """
    html += "</table>"
    if bullets:
        html += "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
    return html


CV_SPECS = [
    # 1. Tier S — RO / ModMath / Quant / R&D IA (FR)
    {
        "slug": "cv_ro_modmath_rd_fr",
        "dest_dirs": [BASE_CAND / "7_RO_ModMath_Quant_RD_IA", CV_LATEX_DIR],
        "extra_names": {CV_LATEX_DIR: "cv_fr.pdf"},
        "subtitle": "Ingénieur Modélisation Mathématique, RO &amp; R&amp;D IA",
        "tagline": "Ingénieur UTC (<b>Label Mod'Math</b>) &bull; Optimisation, Processus Stochastiques &amp; Garantie de Risque",
        "loc": "Paris / Europe (Mobile) &bull; Permis B",
        "sections": [
            ("Formation Académique", [
                entry_block(
                    "Diplôme d'Ingénieur en Génie Informatique — Filière IAD &amp; Label Mod'Math",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Label Modélisation Mathématique (Mod'Math) :</b> Optimisation continue et discrète (Simplexe, Dualité, conditions KKT, Lagrangien augmenté, descente de gradient — <i>RO04</i>), Recherche Opérationnelle &amp; Modélisation Stochastique (Chaînes de Markov, processus de Poisson, files d'attente, simulation d'événements discrets — <i>RO05</i>), Analyse numérique matricielle &amp; EDO (SVD, QR, Runge-Kutta — <i>MT09</i>).",
                        "<b>Statistiques &amp; Intelligence Artificielle :</b> Estimation paramétrique, tests d'hypothèses, intervalles de confiance (<i>SY02</i>), Apprentissage statistique &amp; bayésien, Analyse de données multidimensionnelles (<i>SY09</i>), Vision par ordinateur (<i>SY32</i>).",
                    ],
                ),
                entry_block("Classes Préparatoires aux Grandes Écoles (CPGE PTSI / PT)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
            ("Expériences Professionnelles &amp; Recherche R&amp;D", [
                entry_block(
                    "Epiconcept — Équipe R&amp;D Data Science &amp; Épidémiologie",
                    "Mars 2026 – Sept. 2026 (6 mois)",
                    "Ingénieur Recherche — Garantie Statistique du Risque, Vision Médicale &amp; LLMs",
                    "Paris, France",
                    [
                        "<b>Classification sélective à risque garanti (cadre SGR &amp; bornes de Hoeffding) :</b> Implémentation et extension bi-seuil (&tau;<sub>&minus;</sub>, &tau;<sub>+</sub>) des algorithmes de Geifman &amp; El-Yaniv pour borner simultanément le taux de faux négatifs (FNR &le; 5%) et de faux positifs (FPR &le; 5%) en échantillon fini avec garantie probabiliste 1&minus;&delta; ; quantification d'incertitude par <b>MC Dropout</b> et <b>Deep Ensembles</b>.",
                        "<b>Apprentissage profond haute résolution (GMIC) :</b> Fine-tuning du réseau global/local à attention <b>GMIC</b> (<b>ResNet-22</b> + <b>ResNet-18</b>) en 16 bits sur 300+ Go de mammographies RSNA (2944&times;1920, prévalence 2,1%), portant l'AUC de 0,683 à <b>0,889</b> (IC 95% : [0,858 ; 0,921]).",
                        "<b>Inférence LLM contrainte &amp; vérification de preuves (Projet ECDC) :</b> Benchmark de 20 configurations de LLMs (<b>MedGemma-4B/27B</b>, <b>Gemma-2-27B</b>, <b>Qwen-2.5-32B</b>) sous budget GPU NVIDIA A100 40 Go sur notes cliniques MIMIC-IV ; vérificateur déterministe de citations verbatim (<code>evidence_is_grounded</code>, <b>F1 = 0,91</b>) et transfert cross-lingue zéro-shot vers le croate (<b>F1 = 0,88</b>).",
                        "<b>Transfert méthodologique :</b> Co-auteur d'une capsule interactive de 8 chapitres (Quarto / Jupyter / Docker) sur la maîtrise du risque en IA médicale.",
                    ],
                ),
                entry_block(
                    "Laboratoire BMBI (CNRS UMR 7338 / UTC)",
                    "Sept. 2025 – Janv. 2026 (5 mois)",
                    "Projet de Recherche (TZ2) — Surfaces Implicites Neuronales 3D/4D &amp; Géométrie Différentielle",
                    "Compiègne, France",
                    [
                        "<b>Représentations implicites spatio-temporelles f<sub>&theta;</sub>(x,y,z,t) = 0 :</b> Modélisation continue de membranes biologiques déformables (globules rouges de Kuchel et micro-capsules sous cisaillement) par réseaux <b>SIREN</b> (sin(&omega;<sub>0</sub>&middot;)), encodage de Fourier et régularisation <b>Eikonale</b> (||&nabla;f|| = 1), atteignant une <b>IoU de 99,65%</b> sur déformations non-affines.",
                        "<b>Parcimonie mathématique vs capacité neuronale :</b> Démonstration que la régression polynomiale de degré 4 retrouve l'équation exacte de Kuchel en <b>10 coefficients</b> (résidu nul aux erreurs machine près) contre 197 886 poids pour le MLP.",
                        "<b>Géométrie différentielle analytique :</b> Calcul exact des courbures de Gauss (K) et moyenne (H) par différentiation automatique PyTorch d'ordre 2 (<code>autograd</code>) sans maillage ; validation numérique du théorème de <b>Gauss-Bonnet</b> (&oint; K dA = 4&pi;) à <b>0,025%</b> près.",
                    ],
                ),
                entry_block(
                    "Aubay — Pôle Innovation",
                    "Sept. 2024 – Févr. 2025 (6 mois)",
                    "Ingénieur R&amp;D Data Science — Détection d'Anomalies Contextuelles",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>Modélisation d'anomalies sur données tabulaires mixtes :</b> Étude comparative de modèles profonds (<b>GANDALF</b>, <b>FT-Transformer</b>, <b>TabTransformer</b> via PyTorch Tabular) et d'arbres d'isolation (<b>Isolation Forest</b>, <b>DIF</b>) pour séparer variables contextuelles et comportementales (<b>F1 = 0,903</b>, <b>ROC-AUC = 0,985</b>).",
                        "<b>Architecture logicielle :</b> Développement d'une plateforme d'audit full-stack (API REST <b>Flask</b>, <b>React</b>, stockage <b>AWS S3</b>, <b>Docker</b>).",
                    ],
                ),
            ]),
            ("Projets Scientifiques &amp; Ingénierie Système", [
                entry_block(
                    "SY09 — Apprentissage Statistique, Tests de Wald &amp; Clustering Adaptatif",
                    "Python, Scikit-Learn, Statsmodels",
                    bullets=[
                        "Régression logistique avec tests statistiques de <b>Wald</b>, classifieurs bayésiens/euclidiens et clustering <b>K-Means à distance de Gower</b> (données mixtes) et métrique adaptative de <b>Mahalanobis</b> sur données cliniques cardiaques.",
                    ],
                ),
                entry_block(
                    "Jarvis &amp; PDF Live Notes — Moteur RAG BM25/Graphe &amp; Serveur Collaboratif Temps Réel",
                    "Python, FastAPI, SQLite FTS5, SSE",
                    bullets=[
                        "Moteur d'évaluation multi-juges LLMs avec vérification déterministe d'extraits verbatim et espace de travail PDF collaboratif temps réel (<b>Server-Sent Events</b>) injectant des simulations interactives HTML5/Canvas à la volée.",
                    ],
                ),
            ]),
        ],
        "skills": [
            ("Mathématiques &amp; RO", "Optimisation convexe/combinatoire, Markov, Poisson, Files d'attente, Tests statistiques, Bornes de Hoeffding, Autograd d'ordre 2"),
            ("Langages", "Python, C/C++17 (Qt 6), SQL, R, Scilab/MATLAB, Kotlin, Bash, LaTeX / Quarto"),
            ("Deep Learning &amp; IA", "PyTorch, Hugging Face, PyTorch Tabular, Scikit-Learn, SIREN/PINNs, OpenCV"),
            ("Systèmes &amp; Langues", "Linux, Docker, Git, FastAPI/Flask, Français (natif), Anglais (professionnel B2+)"),
        ],
    },
    # 2. Tier S — RO / ModMath / Quant / R&D IA (EN)
    {
        "slug": "cv_ro_modmath_rd_en",
        "dest_dirs": [BASE_CAND / "7_RO_ModMath_Quant_RD_IA", CV_LATEX_DIR],
        "extra_names": {CV_LATEX_DIR: "cv.pdf"},
        "subtitle": "Mathematical Modeling, OR &amp; AI Research Engineer",
        "tagline": "M.Eng. UTC (<b>Mod'Math Honors</b>) &bull; Optimization, Stochastics &amp; Statistical Risk Control",
        "loc": "Paris, France (Open to Relocation: EU / CH / UK)",
        "sections": [
            ("Education", [
                entry_block(
                    "Master of Engineering (M.Eng.) in Computer Science, AI &amp; Mathematical Modeling",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Mathematical Modeling Track (<i>Label Mod'Math</i>):</b> Convex &amp; Combinatorial Optimization (Simplex, Duality, KKT conditions, Augmented Lagrangian, Gradient methods — <i>RO04</i>), Operations Research &amp; Stochastic Modeling (Markov Chains, Poisson Processes, Queuing Theory, Discrete-Event Simulation — <i>RO05</i>), Numerical Matrix Analysis &amp; ODEs (SVD, QR, Runge-Kutta — <i>MT09</i>).",
                        "<b>Statistical Learning &amp; AI:</b> Parametric Estimation, Hypothesis Testing &amp; Confidence Intervals (<i>SY02</i>), Multivariate Statistical Analysis &amp; Clustering (<i>SY09</i>), Bayesian Decision Theory, Deep Learning &amp; Computer Vision (<i>SY32</i>).",
                    ],
                ),
                entry_block("Preparatory Classes for Grandes Écoles (CPGE PTSI / PT — Intensive Math &amp; Physics)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
            ("Research &amp; R&amp;D Engineering Experience", [
                entry_block(
                    "Epiconcept — R&amp;D Data Science &amp; Epidemiology Lab",
                    "March 2026 – Sept. 2026 (6 months)",
                    "AI Research Intern — Statistical Risk Guarantees, Medical Computer Vision &amp; Clinical LLMs",
                    "Paris, France",
                    [
                        "<b>Distribution-Free Selective Classification (<i>SGR</i> &amp; Hoeffding Bounds):</b> Implemented and extended Geifman &amp; El-Yaniv's framework to a dual-threshold (&tau;<sub>&minus;</sub>, &tau;<sub>+</sub>) clinical triage rule, guaranteeing simultaneous finite-sample bounds (1&minus;&delta;) on False Negative Rate (FNR &le; 5%) and False Positive Rate (FPR &le; 5%) via Hoeffding inversion, combined with <b>MC Dropout</b> and <b>Deep Ensembles</b>.",
                        "<b>High-Resolution Medical Vision (GMIC):</b> Fine-tuned the interpretable <b>GMIC</b> architecture (<b>ResNet-22</b> global saliency + <b>ResNet-18</b> ROI patch attention) in 16-bit precision on 300+ GB of RSNA mammograms (2944&times;1920, 2.1% malignancy rate), improving test AUC from 0.683 to <b>0.889</b> (95% CI: [0.858, 0.921]).",
                        "<b>Grounded Clinical LLM Extraction (ECDC European Surveillance):</b> Benchmarked 20 local LLM configurations (<b>MedGemma-4B/27B</b>, <b>Gemma-2-27B</b>, <b>Qwen-2.5-32B</b>) on MIMIC-IV patient records under a strict single-GPU <b>NVIDIA A100 40 GB</b> budget; engineered a deterministic verbatim-quote verifier (<code>evidence_is_grounded</code>, <b>F1 = 0.91</b>) and achieved <b>F1 = 0.88</b> in zero-shot cross-lingual transfer to Croatian.",
                        "<b>Scientific Dissemination:</b> Co-authored an 8-chapter containerized training capsule (<b>Quarto / Jupyter / Docker</b>) on deep learning risk control.",
                    ],
                ),
                entry_block(
                    "BMBI Laboratory (CNRS UMR 7338 / UTC)",
                    "Sept. 2025 – Jan. 2026 (5 months)",
                    "Graduate Research Project (TZ2) — 3D/4D Implicit Neural Surfaces &amp; Differential Geometry",
                    "Compiègne, France",
                    [
                        "<b>Continuous Space-Time Implicit Surfaces f<sub>&theta;</sub>(x,y,z,t) = 0:</b> Modeled 3D/4D deformable biological membranes (Kuchel red blood cells and micro-capsules in shear flow) using <b>SIREN</b> (sin(&omega;<sub>0</sub>&middot;)) networks, Fourier positional encoding, and <b>Eikonal regularization</b> (||&nabla;f|| = 1), achieving <b>99.65% IoU</b> on non-affine temporal deformations.",
                        "<b>Analytical Parsimony vs. Neural Over-Parameterization:</b> Proved that degree-4 polynomial regression recovers the exact analytical Kuchel quartic in <b>10 coefficients</b> (machine-zero residual) vs. 197,886 neural weights.",
                        "<b>Mesh-Free Differential Geometry:</b> Computed exact Gaussian (K) and Mean (H) curvatures directly via <b>2nd-order PyTorch <code>autograd</code></b> (gradient &amp; Hessian), numerically verifying the <b>Gauss-Bonnet theorem</b> (&oint; K dA = 4&pi;) to <b>0.025% accuracy</b>.",
                    ],
                ),
                entry_block(
                    "Aubay — Innovation Department",
                    "Sept. 2024 – Feb. 2025 (6 months)",
                    "Data Science &amp; AI Research Intern — Contextual Anomaly Detection",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>Contextual Outlier Detection on Mixed Tabular Data:</b> Benchmarked deep tabular architectures (<b>GANDALF</b>, <b>FT-Transformer</b>, <b>TabTransformer</b> via PyTorch Tabular) alongside <b>Isolation Forest</b> and <b>Deep Isolation Forest</b> (<b>F1 = 0.903</b>, <b>ROC-AUC = 0.985</b>).",
                        "<b>Software Engineering:</b> Built a reproducible full-stack audit platform (<b>Flask</b> REST API, <b>React</b>, <b>AWS S3</b>, <b>Conda / Docker</b>).",
                    ],
                ),
            ]),
            ("Selected Scientific &amp; Systems Projects", [
                entry_block(
                    "Statistical Learning, Wald Hypothesis Testing &amp; Adaptive Clustering (SY09)",
                    "Python, Scikit-Learn, Statsmodels",
                    bullets=[
                        "Implemented logistic regression with <b>Wald statistical tests</b>, Bayesian classifiers, and <b>Gower-distance / Adaptive Mahalanobis K-Means</b> on mixed clinical cardiac datasets.",
                    ],
                ),
                entry_block(
                    "Jarvis &amp; PDF Live Notes — Grounded Multi-Judge LLM Engine &amp; Real-Time SSE Workspace",
                    "Python, FastAPI, SQLite FTS5",
                    bullets=[
                        "Built a 2-pass, 3-LLM evaluation jury with deterministic substring grounding and a real-time <b>Server-Sent Events (SSE)</b> collaborative PDF canvas streaming interactive HTML5 simulation widgets.",
                    ],
                ),
            ]),
        ],
        "skills": [
            ("Mathematics &amp; OR", "Convex/Combinatorial Optimization, Markov Chains, Poisson/Queues, Hypothesis Testing, Hoeffding Bounds, 2nd-Order Autograd"),
            ("Languages", "Python, C/C++17 (Qt 6), SQL, R, Scilab/MATLAB, Kotlin, Bash, LaTeX / Quarto"),
            ("Deep Learning &amp; AI", "PyTorch, Hugging Face, PyTorch Tabular, Scikit-Learn, SIREN/Implicit Nets, OpenCV"),
            ("Systems &amp; Languages", "Linux, Docker, Git, FastAPI/Flask, French (Native), English (Professional B2+)"),
        ],
    },
    # 3. Tier S — Solutions Architect / Forward Deployed AI Engineer (FR)
    {
        "slug": "cv_solutions_architect_fde_fr",
        "dest_dirs": [BASE_CAND / "8_Solutions_Architect_Forward_Deployed_AI"],
        "extra_names": {},
        "subtitle": "Solutions Architect &amp; Forward Deployed AI Engineer",
        "tagline": "Ingénieur UTC &bull; Systèmes LLMs en Production, Architecture Full-Stack &amp; Déploiement Critique",
        "loc": "Paris / Europe (Mobile) &bull; Permis B",
        "sections": [
            ("Expériences Professionnelles &amp; Déploiement Terrain", [
                entry_block(
                    "Epiconcept — Équipe R&amp;D Data Science &amp; Santé Publique Européenne",
                    "Mars 2026 – Sept. 2026 (6 mois)",
                    "Ingénieur R&amp;D IA &amp; Solutions LLM — Du Cadrage Métier à la Mise en Production",
                    "Paris, France",
                    [
                        "<b>Architecture d'extraction clinique par LLMs locaux (Projet Européen ECDC) :</b> Cadrage et déploiement d'un pipeline automatisé sur dossiers patients MIMIC-IV sous contrainte d'infrastructure hospitalière stricte (<b>1&times; NVIDIA A100 40 Go VRAM</b>, 100% on-premise pour conformité RGPD). Benchmark de 20 configurations (<b>MedGemma-4B/27B</b>, <b>Gemma-2-27B</b>, <b>Qwen-2.5-32B</b>, <b>Mistral-Small-24B</b>) atteignant <b>F1 = 0,91</b>.",
                        "<b>Garde-fous déterministes anti-hallucination &amp; multilinguisme :</b> Conception d'un vérificateur formel imposant un schéma JSON strict et des citations exactes (<code>evidence_is_grounded</code>) vérifiées mot à mot dans le texte source ; validation du transfert zéro-shot vers des hôpitaux croates (<b>F1 = 0,88</b>) et rédaction d'un manuel technique de 6 chapitres (<b>Quarto</b>).",
                        "<b>Vision médicale haute résolution &amp; contrôle du risque :</b> Fine-tuning du réseau <b>GMIC</b> sur 300+ Go de mammographies 16 bits (<b>AUC = 0,889</b>) et implémentation d'un triage sélectif garantissant FNR &le; 5% et FPR &le; 5% (bornes de Hoeffding).",
                        "<b>Enablement &amp; formation technique :</b> Co-création d'une capsule interactive de 8 chapitres (<b>Docker / Jupyter</b>) pour former les data scientists et épidémiologistes au déploiement de modèles profonds fiables.",
                    ],
                ),
                entry_block(
                    "Aubay — Pôle Innovation",
                    "Sept. 2024 – Févr. 2025 (6 mois)",
                    "Ingénieur Solutions Data Science &amp; Full-Stack IA",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>Plateforme SaaS d'audit et détection d'anomalies :</b> Conception de bout en bout d'une application web industrielle (<b>API REST Flask</b>, interface <b>React</b>, connecteur cloud <b>AWS S3</b>, conteneurisation <b>Docker</b>) permettant aux équipes clientes d'auditer la qualité de leurs bases de données.",
                        "<b>Moteur d'IA tabulaire hybride :</b> Intégration de <b>PyTorch Tabular</b> (<b>GANDALF</b>, <b>FT-Transformer</b>, <b>TabTransformer</b>) et <b>Isolation Forest / DIF</b> pour détecter les anomalies contextuelles sur données mixtes (<b>F1 = 0,903</b>, <b>ROC-AUC = 0,985</b>).",
                    ],
                ),
                entry_block(
                    "Laboratoire BMBI (CNRS UMR 7338) &amp; Complétude",
                    "2022 – 2026",
                    "Ingénieur Recherche Modélisation 3D/4D (5 mois) &amp; Enseignant Scientifique (4 ans)",
                    "Compiègne / Paris, France",
                    [
                        "<b>Modélisation 4D par réseaux implicites (BMBI) :</b> Reconstruction spatio-temporelle de capsules déformables par réseaux <b>SIREN</b> (<b>IoU = 99,65%</b>), régularisation Eikonale et calcul analytique de courbures par <code>autograd</code> d'ordre 2 (Gauss-Bonnet vérifié à 0,025%).",
                        "<b>Enseignement &amp; vulgarisation (Complétude, depuis 2022) :</b> Accompagnement personnalisé en mathématiques et physique-chimie ; capacité éprouvée à traduire des concepts abstraits pour des interlocuteurs non-spécialistes.",
                    ],
                ),
            ]),
            ("Architectures Logicielles &amp; Projets Déployés", [
                entry_block(
                    "PDF Live Notes — Espace Collaboratif Temps Réel Humain-Stylet + Agent IA",
                    "FastAPI, SSE, PDF.js, Android Kiosk",
                    bullets=[
                        "Architecture temps réel (<b>Server-Sent Events</b>) permettant à un agent IA d'annoter en direct un document PDF partagé avec une tablette, de surligner des passages et d'injecter des <b>simulateurs interactifs HTML5/Canvas sandboxés (<code>&lt;iframe&gt;</code>)</b> au fil du raisonnement.",
                    ],
                ),
                entry_block(
                    "MonLycée Cloud Auth Relay — Broker de Session Zero-Trust &amp; Extension Manifest V3",
                    "FastAPI, Playwright, AWS/Oracle",
                    bullets=[
                        "Microservice Cloud déportant l'authentification SSO Keycloak via Chromium headless (<b>Playwright</b>), avec verrouillage de concurrence (<code>asyncio.Lock</code>), cache mémoire TTL (&lt; 50 ms) et injection transparente de 16 cookies via Service Worker <b>Edge Manifest V3</b>.",
                    ],
                ),
                entry_block(
                    "Jarvis &amp; Custos — Moteur RAG Multi-Juges (SQLite FTS5) &amp; Suite Sécurité Android/Linux",
                    "Python, SQLite FTS5, Kotlin, systemd",
                    bullets=[
                        "Moteur d'ingestion multi-API (51 connecteurs ATS européens) et pipeline d'évaluation à 2 passes et 3 LLMs distincts avec validation déterministe de citations verbatim ; suite de contrôle d'accès <b>Android Device Owner</b> (Kotlin) et daemons Linux (<code>systemd</code>).",
                    ],
                ),
            ]),
            ("Formation Académique", [
                entry_block(
                    "Diplôme d'Ingénieur en Génie Informatique — Filière IAD &amp; Label Mod'Math",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Ingénierie Logicielle &amp; Data :</b> Architecture orientée objet (C++17 / Qt 6 — <i>LO21</i>), Entrepôts de données &amp; pipelines ETL (<i>NF26</i>), Apprentissage statistique (<i>SY09</i>), Vision par ordinateur (<i>SY32</i>).",
                        "<b>Label Mod'Math :</b> Optimisation convexe &amp; combinatoire (<i>RO04</i>), Recherche opérationnelle &amp; processus stochastiques (<i>RO05</i>).",
                    ],
                ),
                entry_block("Classes Préparatoires aux Grandes Écoles (CPGE PTSI / PT)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
        ],
        "skills": [
            ("LLMs &amp; IA Appliquée", "Inférence locale (MedGemma, Qwen, Mistral), JSON contraint, Grounding anti-hallucination, RAG (FTS5/BM25), PyTorch"),
            ("Ingénierie &amp; Cloud", "Python, FastAPI, Flask, React, JS (Manifest V3), C++17, Kotlin, SQL, Docker, Linux (systemd), AWS S3, Git/CI"),
            ("Architecture &amp; Client", "Cadrage technique, Démos &amp; PoC rapides, Documentation Quarto, Pédagogie client"),
            ("Langues", "Français (natif), Anglais (professionnel courant B2+, rédaction &amp; présentations techniques)"),
        ],
    },
    # 4. Tier S — Solutions Architect / Forward Deployed AI Engineer (EN)
    {
        "slug": "cv_solutions_architect_fde_en",
        "dest_dirs": [BASE_CAND / "8_Solutions_Architect_Forward_Deployed_AI"],
        "extra_names": {},
        "subtitle": "Forward Deployed AI Engineer &amp; Solutions Architect",
        "tagline": "M.Eng. UTC &bull; Production LLM Systems, Full-Stack Architecture &amp; Technical Delivery",
        "loc": "Paris, France (Open to Relocation: EU / CH / UK)",
        "sections": [
            ("Professional Experience &amp; Technical Delivery", [
                entry_block(
                    "Epiconcept — R&amp;D Data Science &amp; European Public Health",
                    "March 2026 – Sept. 2026 (6 months)",
                    "Forward-Deployed AI Research Intern — Clinical LLM Pipelines &amp; High-Stakes Vision",
                    "Paris, France",
                    [
                        "<b>End-to-End Clinical LLM Architecture (ECDC European Project):</b> Scoped, architected, and deployed an on-premise clinical extraction pipeline on MIMIC-IV records under strict hospital GDPR and hardware constraints (<b>single NVIDIA A100 40 GB GPU</b>). Benchmarked 20 LLM setups (<b>MedGemma-4B/27B</b>, <b>Gemma-2-27B</b>, <b>Qwen-2.5-32B</b>, <b>Mistral-Small-24B</b>), achieving <b>F1 = 0.91</b>.",
                        "<b>Deterministic Anti-Hallucination Guardrails &amp; Cross-Lingual Rollout:</b> Engineered a strict JSON schema &amp; substring verifier (<code>evidence_is_grounded</code>) enforcing verbatim clinical evidence quotes; validated zero-shot cross-lingual transfer to Croatian hospital reports (<b>F1 = 0.88</b>) and authored a 6-chapter engineering playbook (<b>Quarto</b>).",
                        "<b>Trustworthy Medical Vision &amp; Risk Triage:</b> Fine-tuned the interpretable <b>GMIC</b> network on 300+ GB of 16-bit mammograms (<b>AUC = 0.889</b>) and deployed a selective abstention layer guaranteeing FNR &le; 5% and FPR &le; 5% via Hoeffding bounds.",
                        "<b>Technical Enablement:</b> Co-authored an 8-chapter containerized training capsule (<b>Docker / Jupyter</b>) to onboard partner epidemiologists and data scientists onto deep learning and risk-controlled deployment.",
                    ],
                ),
                entry_block(
                    "Aubay — Innovation Lab",
                    "Sept. 2024 – Feb. 2025 (6 months)",
                    "AI Solutions &amp; Full-Stack Data Science Intern",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>Full-Stack Data Quality &amp; Anomaly Detection Platform:</b> Architected and delivered an end-to-end web application (<b>Flask REST API</b>, <b>React</b> frontend, <b>AWS S3</b> cloud storage, <b>Docker</b>) enabling enterprise stakeholders to audit tabular datasets interactively.",
                        "<b>Deep Tabular Modeling:</b> Integrated <b>PyTorch Tabular</b> (<b>GANDALF</b>, <b>FT-Transformer</b>, <b>TabTransformer</b>) with <b>Isolation Forest / DIF</b> to detect contextual anomalies in heterogeneous data (<b>F1 = 0.903</b>, <b>ROC-AUC = 0.985</b>).",
                    ],
                ),
                entry_block(
                    "BMBI Lab (CNRS UMR 7338) &amp; Complétude",
                    "2022 – 2026",
                    "3D/4D Neural Modeling Researcher (5 months) &amp; STEM Instructor (4 years)",
                    "Compiègne / Paris, France",
                    [
                        "<b>4D Implicit Neural Surfaces (BMBI):</b> Reconstructed deforming micro-capsules via <b>SIREN</b> networks (<b>IoU = 99.65%</b>), Eikonal regularization, and 2nd-order <code>autograd</code> curvatures (Gauss-Bonnet theorem verified to 0.025%).",
                        "<b>Technical Communication (Complétude, since 2022):</b> 4+ years of 1-on-1 mathematics and physics tutoring; proven ability to translate complex quantitative trade-offs for diverse technical and non-technical stakeholders.",
                    ],
                ),
            ]),
            ("Production Systems &amp; Full-Stack Engineering Projects", [
                entry_block(
                    "PDF Live Notes — Real-Time Human Stylus + AI Collaborative Workspace",
                    "FastAPI, SSE, PDF.js, Android Kiosk",
                    bullets=[
                        "Built a real-time <b>Server-Sent Events (SSE)</b> server and <b>PDF.js / Perfect-Freehand</b> tablet workspace enabling an AI agent to stream live vector strokes, text highlights, and sandboxed <b>interactive HTML5 simulation widgets (<code>&lt;iframe&gt;</code>)</b> onto a user's document.",
                    ],
                ),
                entry_block(
                    "MonLycée Cloud Auth Relay — Zero-Trust Session Broker &amp; Manifest V3 Extension",
                    "FastAPI, Playwright, AWS/Oracle",
                    bullets=[
                        "Engineered a cloud microservice offloading <b>Keycloak SSO</b> login to headless Chromium (<b>Playwright</b>) with mutex concurrency (<code>asyncio.Lock</code>), &lt; 50 ms RAM session caching, and 1-click cookie injection into Microsoft Edge via a <b>Manifest V3 Service Worker</b>.",
                    ],
                ),
                entry_block(
                    "Jarvis &amp; Custos — Grounded Multi-Judge RAG Engine (SQLite FTS5) &amp; OS Security Suite",
                    "Python, SQLite FTS5, Kotlin, systemd",
                    bullets=[
                        "Built a parallel multi-ATS ingestion engine (51 European boards) and a 2-pass, 3-LLM evaluation pipeline enforcing deterministic substring grounding; engineered a native <b>Android Device Owner</b> security suite (Kotlin) and Linux <code>systemd</code> watchdogs.",
                    ],
                ),
            ]),
            ("Education", [
                entry_block(
                    "Master of Engineering (M.Eng.) in Computer Science, AI &amp; Mathematical Modeling",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Software &amp; Data Engineering:</b> Object-Oriented Architecture (C++17 / Qt 6 — <i>LO21</i>), Data Warehousing &amp; ETL Pipelines (<i>NF26</i>), Statistical Learning (<i>SY09</i>), Computer Vision (<i>SY32</i>).",
                        "<b>Mod'Math Honors:</b> Convex &amp; Combinatorial Optimization (<i>RO04</i>), Operations Research &amp; Stochastic Modeling (<i>RO05</i>).",
                    ],
                ),
                entry_block("Preparatory Classes for Grandes Écoles (CPGE PTSI / PT — Intensive Math &amp; Physics)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
        ],
        "skills": [
            ("Applied AI &amp; LLMs", "Local LLM Inference (MedGemma, Qwen, Mistral), Constrained JSON, Verbatim Grounding, RAG (FTS5/BM25), PyTorch"),
            ("Full-Stack &amp; Systems", "Python, FastAPI, Flask, React, JS (Manifest V3), C++17, Kotlin, SQL, Docker, Linux (systemd), AWS S3, Git"),
            ("Solutions &amp; Delivery", "Technical Scoping, Rapid Prototyping, Customer Enablement, Quarto Docs"),
            ("Languages", "French (Native), English (Professional Working Proficiency B2+, technical writing &amp; presentations)"),
        ],
    },
    # 5. Tier B — Data / ML / Vision / LLM Engineer (FR)
    {
        "slug": "cv_data_ia_engineer",
        "dest_dirs": [BASE_CAND / "5_Data_IA_Engineering"],
        "extra_names": {},
        "subtitle": "Ingénieur R&amp;D — Machine Learning, Vision &amp; LLMs",
        "tagline": "Ingénieur UTC (<b>Label Mod'Math</b>) &bull; Deep Learning, LLMs &amp; Déploiement",
        "loc": "Paris / Europe (Mobile) &bull; Permis B",
        "sections": [
            ("Expériences Professionnelles &amp; Recherche R&amp;D", [
                entry_block(
                    "Epiconcept — Équipe R&amp;D Data Science",
                    "Mars 2026 – Sept. 2026 (6 mois)",
                    "Ingénieur R&amp;D en Apprentissage Profond, Vision Médicale &amp; LLMs",
                    "Paris, France",
                    [
                        "<b>Extraction clinique par LLMs locaux (Projet ECDC / MIMIC-IV) :</b> Déploiement et benchmark de 20 configurations de LLMs (<b>MedGemma-4B/27B</b>, <b>Gemma-2-27B</b>, <b>Qwen-2.5-32B</b>, <b>Mistral-Small-24B</b>) quantifiés en 8/4 bits sous budget strict NVIDIA A100 40 Go (<b>F1 = 0,91</b>).",
                        "<b>Vérification anti-hallucination &amp; transfert cross-lingue :</b> Protocole imposant des citations verbatim (<code>evidence_is_grounded</code>) et JSON strict ; transfert zéro-shot vers des notes cliniques croates via <b>NLLB-200 / EuroLLM-9B</b> (<b>F1 = 0,88</b>).",
                        "<b>Vision par ordinateur haute résolution (GMIC) :</b> Fine-tuning du réseau global/local à attention <b>GMIC</b> (<b>ResNet-22</b> + <b>ResNet-18</b>) en 16 bits sur 300+ Go de mammographies RSNA (2944&times;1920), portant l'AUC de 0,683 à <b>0,889</b> (IC 95% : [0,858 ; 0,921]).",
                        "<b>Contrôle statistique du risque :</b> Classification sélective (cadre SGR, bornes de Hoeffding, <b>MC Dropout</b>, <b>Deep Ensembles</b>) garantissant FNR &le; 5% et FPR &le; 5% ; capsule interactive de 8 chapitres sous <b>Docker</b>.",
                    ],
                ),
                entry_block(
                    "Laboratoire BMBI (CNRS UMR 7338 / UTC)",
                    "Sept. 2025 – Janv. 2026 (5 mois)",
                    "Projet de Recherche (TZ2) — Réseaux Implicites 3D/4D (SIREN) &amp; Géométrie Différentielle",
                    "Compiègne, France",
                    [
                        "<b>Surfaces implicites spatio-temporelles f<sub>&theta;</sub>(x,y,z,t) = 0 :</b> Reconstruction 4D de membranes déformables par réseaux <b>SIREN</b>, encodage de Fourier et régularisation <b>Eikonale</b> (||&nabla;f|| = 1), atteignant <b>99,65% d'IoU</b>.",
                        "<b>Géométrie différentielle &amp; parcimonie :</b> Retrouve l'équation analytique de Kuchel en <b>10 coefficients</b> (vs 197 886 poids neuronaux) et calcule les courbures de Gauss/moyenne par <code>autograd</code> d'ordre 2 (théorème de Gauss-Bonnet vérifié à <b>0,025%</b>).",
                    ],
                ),
                entry_block(
                    "Aubay — Pôle Innovation",
                    "Sept. 2024 – Févr. 2025 (6 mois)",
                    "Ingénieur Data Science &amp; IA — Détection d'Anomalies Contextuelles",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>Deep Learning Tabulaire :</b> Benchmark de <b>GANDALF</b>, <b>FT-Transformer</b> et <b>TabTransformer</b> (PyTorch Tabular) couplés à <b>Isolation Forest / DIF</b> sur données mixtes (<b>F1 = 0,903</b>, <b>ROC-AUC = 0,985</b>).",
                        "<b>Industrialisation Full-Stack :</b> Développement d'une API REST <b>Flask</b>, interface <b>React</b>, connecteur <b>AWS S3</b> et environnement reproductible <b>Conda / Docker</b>.",
                    ],
                ),
            ]),
            ("Formation Académique", [
                entry_block(
                    "Diplôme d'Ingénieur en Génie Informatique — Filière IAD &amp; Label Mod'Math",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Data &amp; IA :</b> Deep Learning, Vision par Ordinateur (<i>SY32</i>), Apprentissage Statistique &amp; Clustering (<i>SY09</i>), Data Warehouse &amp; ETL (<i>NF26</i>).",
                        "<b>Label Mod'Math :</b> Optimisation convexe &amp; combinatoire (<i>RO04</i>), Processus Stochastiques &amp; Markov (<i>RO05</i>), Analyse Numérique (<i>MT09</i>).",
                    ],
                ),
                entry_block("Classes Préparatoires aux Grandes Écoles (CPGE PTSI / PT)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
            ("Projets Personnels &amp; Systèmes IA", [
                entry_block(
                    "PDF Live Notes &amp; Jarvis — Co-Annotation Temps Réel (SSE) &amp; Moteur RAG Multi-Juges",
                    "Python, FastAPI, SQLite FTS5",
                    bullets=[
                        "Espace de travail PDF collaboratif temps réel (<b>Server-Sent Events</b>) permettant à un agent IA d'injecter des annotations vectorielles et des widgets interactifs HTML5/Canvas ; moteur RAG <b>SQLite FTS5 BM25</b> et comité de 3 LLMs à preuves verbatim.",
                    ],
                ),
                entry_block(
                    "MonLycée Cloud Auth Relay &amp; Custos — Broker SSO Playwright &amp; Sécurité Android",
                    "FastAPI, Playwright, Kotlin",
                    bullets=[
                        "Relais Cloud d'authentification Keycloak (cache mémoire &lt; 50 ms, extension <b>Edge Manifest V3</b>) et suite Android <b>Device Owner</b> en Kotlin avec watchdogs anti-contournement.",
                    ],
                ),
                entry_block(
                    "SY09 &amp; SY32 — Apprentissage Statistique, Tests de Wald &amp; Vision Classique (HOG/SVM)",
                    "Python, Scikit-Learn, OpenCV",
                    bullets=[
                        "Régression logistique avec tests de <b>Wald</b>, K-Means à distance de <b>Gower / Mahalanobis</b> sur données cardiaques, et détection d'objets par descripteurs HOG, SVM/Random Forest, <i>hard negative mining</i> et NMS.",
                    ],
                ),
            ]),
        ],
        "skills": [
            ("Frameworks IA", "PyTorch, Hugging Face (Transformers, bitsandbytes), PyTorch Tabular, Scikit-Learn, OpenCV, SIREN"),
            ("Langages", "Python, C/C++17 (Qt 6), SQL, Kotlin, R, Scilab, Bash, JavaScript (React / Manifest V3), LaTeX / Quarto"),
            ("MLOps &amp; Systèmes", "Docker, Linux (systemd), Git/CI, FastAPI, Flask, AWS S3, SQLite FTS5"),
            ("Langues &amp; Loisirs", "Français (natif), Anglais (courant B2+), Boxe anglaise, Lutte libre"),
        ],
    },
    # 6. Tier B — Data / ML / Vision / LLM Engineer (EN)
    {
        "slug": "cv_data_ia_engineer_en",
        "dest_dirs": [BASE_CAND / "5_Data_IA_Engineering"],
        "extra_names": {},
        "subtitle": "Machine Learning, Computer Vision &amp; LLM Engineer",
        "tagline": "M.Eng. UTC (<b>Mod'Math Honors</b>) &bull; Deep Learning, Grounded LLMs &amp; MLOps",
        "loc": "Paris, France (Open to Relocation: EU / CH / UK)",
        "sections": [
            ("Professional &amp; Research Experience", [
                entry_block(
                    "Epiconcept — R&amp;D Data Science Lab",
                    "March 2026 – Sept. 2026 (6 months)",
                    "Deep Learning, Medical Vision &amp; LLM Research Intern",
                    "Paris, France",
                    [
                        "<b>Grounded Clinical LLM Extraction (ECDC / MIMIC-IV):</b> Deployed and benchmarked 20 local LLM configurations (<b>MedGemma-4B/27B</b>, <b>Gemma-2-27B</b>, <b>Qwen-2.5-32B</b>, <b>Mistral-Small-24B</b>) quantized in 8/4-bit under a single <b>NVIDIA A100 40 GB</b> budget (<b>F1 = 0.91</b>).",
                        "<b>Anti-Hallucination &amp; Cross-Lingual Transfer:</b> Built a deterministic substring verifier (<code>evidence_is_grounded</code>) enforcing verbatim quotes and strict JSON schemas; achieved <b>F1 = 0.88</b> in zero-shot cross-lingual transfer to Croatian clinical notes via <b>NLLB-200 / EuroLLM-9B</b>.",
                        "<b>High-Resolution Medical Vision (GMIC):</b> Fine-tuned the interpretable <b>GMIC</b> network (<b>ResNet-22</b> global saliency + <b>ResNet-18</b> local patch attention) in 16-bit precision on 300+ GB of RSNA mammograms (2944&times;1920), boosting AUC from 0.683 to <b>0.889</b> (95% CI: [0.858, 0.921]).",
                        "<b>Statistical Risk Control:</b> Implemented selective prediction (<i>SGR</i> framework, Hoeffding bounds, <b>MC Dropout</b>, <b>Deep Ensembles</b>) guaranteeing FNR &le; 5% and FPR &le; 5%; co-authored an 8-chapter interactive <b>Docker / Jupyter</b> training capsule.",
                    ],
                ),
                entry_block(
                    "BMBI Laboratory (CNRS UMR 7338 / UTC)",
                    "Sept. 2025 – Jan. 2026 (5 months)",
                    "Graduate Research Project (TZ2) — 3D/4D Implicit Neural Surfaces (SIREN) &amp; Autograd Geometry",
                    "Compiègne, France",
                    [
                        "<b>Space-Time Implicit Surfaces f<sub>&theta;</sub>(x,y,z,t) = 0:</b> Modeled 4D deforming biological capsules using <b>SIREN</b> networks, Fourier features, and <b>Eikonal regularization</b> (||&nabla;f|| = 1), achieving <b>99.65% IoU</b>.",
                        "<b>Analytical Parsimony &amp; Differential Geometry:</b> Recovered the analytical Kuchel quartic in <b>10 coefficients</b> (vs. 197,886 neural weights) and verified the <b>Gauss-Bonnet theorem</b> to <b>0.025%</b> via 2nd-order PyTorch <code>autograd</code>.",
                    ],
                ),
                entry_block(
                    "Aubay — Innovation Department",
                    "Sept. 2024 – Feb. 2025 (6 months)",
                    "Data Science &amp; AI Intern — Contextual Anomaly Detection",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>Deep Tabular Learning:</b> Benchmarked <b>GANDALF</b>, <b>FT-Transformer</b>, and <b>TabTransformer</b> (PyTorch Tabular) coupled with <b>Isolation Forest / DIF</b> on mixed datasets (<b>F1 = 0.903</b>, <b>ROC-AUC = 0.985</b>).",
                        "<b>Full-Stack Engineering:</b> Delivered a production-ready web platform with a <b>Flask REST API</b>, <b>React</b> frontend, <b>AWS S3</b> storage, and reproducible <b>Conda / Docker</b> containers.",
                    ],
                ),
            ]),
            ("Education", [
                entry_block(
                    "Master of Engineering (M.Eng.) in Computer Science, AI &amp; Mathematical Modeling",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Data &amp; AI Track:</b> Deep Learning, Computer Vision (<i>SY32</i>), Statistical Learning &amp; Clustering (<i>SY09</i>), ETL &amp; Data Warehousing (<i>NF26</i>).",
                        "<b>Mod'Math Honors:</b> Convex &amp; Combinatorial Optimization (<i>RO04</i>), Stochastic Processes &amp; Markov Chains (<i>RO05</i>), Numerical Analysis (<i>MT09</i>).",
                    ],
                ),
                entry_block("Preparatory Classes for Grandes Écoles (CPGE PTSI / PT — Intensive Math &amp; Physics)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
            ("Selected AI &amp; Systems Engineering Projects", [
                entry_block(
                    "PDF Live Notes &amp; Jarvis — Real-Time AI SSE Workspace &amp; Multi-Judge RAG Engine",
                    "Python, FastAPI, SQLite FTS5",
                    bullets=[
                        "Real-time collaborative PDF workspace (<b>Server-Sent Events</b>) streaming AI vector annotations and sandboxed HTML5 simulation widgets; <b>SQLite FTS5 BM25</b> RAG knowledge base and 3-LLM grounded evaluation jury.",
                    ],
                ),
                entry_block(
                    "MonLycée Cloud Auth Relay &amp; Custos — Playwright Session Broker &amp; Android Security",
                    "FastAPI, Playwright, Kotlin",
                    bullets=[
                        "Cloud-deported Keycloak SSO session broker (&lt; 50 ms RAM cache, <b>Edge Manifest V3</b> extension) and native <b>Android Device Owner</b> security suite in Kotlin.",
                    ],
                ),
                entry_block(
                    "SY09 &amp; SY32 — Statistical Learning, Wald Testing &amp; Classical Computer Vision (HOG/SVM)",
                    "Python, Scikit-Learn, OpenCV",
                    bullets=[
                        "Logistic regression with <b>Wald statistical tests</b>, <b>Gower / Adaptive Mahalanobis K-Means</b> on cardiac datasets, and sliding-window object detection via HOG features, SVM/Random Forest, hard negative mining, and NMS.",
                    ],
                ),
            ]),
        ],
        "skills": [
            ("AI Frameworks", "PyTorch, Hugging Face (Transformers, bitsandbytes), PyTorch Tabular, Scikit-Learn, OpenCV, SIREN"),
            ("Languages", "Python, C/C++17 (Qt 6), SQL, Kotlin, R, Scilab, Bash, JavaScript (React / Manifest V3), LaTeX / Quarto"),
            ("MLOps &amp; Systems", "Docker, Linux (systemd), Git/CI, FastAPI, Flask, AWS S3, SQLite FTS5"),
            ("Languages &amp; Interests", "French (Native), English (Fluent B2+), Boxing, Freestyle Wrestling"),
        ],
    },
    # 7. Tier A — Technical Product Manager / Chef de Projet IA (FR)
    {
        "slug": "cv_product_manager",
        "dest_dirs": [BASE_CAND / "4_Product_Management_Tech", BASE_CAND / "1_Consulting_Tech_Data_Strategie"],
        "extra_names": {BASE_CAND / "1_Consulting_Tech_Data_Strategie": "cv_consulting.pdf"},
        "subtitle": "Technical Product Manager &amp; Chef de Projet IA",
        "tagline": "Ingénieur UTC (<b>Label Mod'Math</b>) &bull; Cadrage Produit IA, Arbitrage Coût/Risque &amp; Delivery",
        "loc": "Paris / Europe (Mobile) &bull; Permis B",
        "sections": [
            ("Expériences Professionnelles &amp; Pilotage de Produits IA", [
                entry_block(
                    "Epiconcept — Équipe R&amp;D Data Science &amp; Santé Publique Européenne",
                    "Mars 2026 – Sept. 2026 (6 mois)",
                    "Chef de Projet R&amp;D IA (Stage de fin d'études) — Produits LLMs Cliniques &amp; Vision Médicale",
                    "Paris, France",
                    [
                        "<b>Cadrage produit &amp; arbitrage coût / performance (Projet Européen ECDC) :</b> Définition de la feuille de route d'un outil d'extraction automatique d'infections nosocomiales déployable dans les hôpitaux européens sous contrainte stricte de confidentialité (100% local, budget matériel <b>1&times; GPU A100 40 Go</b>). Démonstration qu'un modèle spécialisé léger (<b>MedGemma-4B</b>, <b>F1 = 0,91</b>) surpasse les modèles 27B/32B tout en divisant la latence et le coût matériel.",
                        "<b>Confiance utilisateur &amp; explicabilité par le design :</b> Conception d'un protocole d'auditabilité imposant des preuves textuelles exactes (<code>evidence_is_grounded</code>) et validation du déploiement multilingue sur dossiers croates (<b>F1 = 0,88</b>).",
                        "<b>Gestion du risque produit en dépistage mammographique :</b> Traduction des contraintes médicales en règle de décision sélective bi-seuil (FNR &le; 5%, FPR &le; 5% sur le modèle <b>GMIC</b> à <b>AUC = 0,889</b>), orientant automatiquement les cas incertains vers une double lecture humaine.",
                        "<b>Transmission &amp; conduite du changement :</b> Co-conception d'une capsule de formation de 8 chapitres (<b>Quarto / Docker</b>) et d'un guide méthodologique de 6 chapitres pour accélérer l'adoption par les équipes métiers.",
                    ],
                ),
                entry_block(
                    "Aubay — Pôle Innovation",
                    "Sept. 2024 – Févr. 2025 (6 mois)",
                    "Product Owner Technique &amp; Ingénieur Data Science — Plateforme d'Audit de Données",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>De l'exploration R&amp;D au produit Full-Stack :</b> Recueil des besoins d'audit qualité, benchmark de modèles tabulaires (<b>GANDALF</b>, <b>FT-Transformer</b>, <b>Isolation Forest</b>, <b>F1 = 0,903</b>) et livraison d'une application web complète (<b>Flask / React / AWS S3 / Docker</b>).",
                        "<b>Structuration méthodologique :</b> Cartographie des typologies d'anomalies (ponctuelles, collectives, contextuelles) et rédaction d'un guide d'aide au choix d'algorithmes pour les consultants Data du groupe.",
                    ],
                ),
                entry_block(
                    "Laboratoire BMBI (CNRS UMR 7338) &amp; Complétude",
                    "2022 – 2026",
                    "Chargé de Recherche Modélisation 3D/4D (5 mois) &amp; Enseignant Scientifique (4 ans)",
                    "Compiègne / Paris, France",
                    [
                        "<b>Arbitrage complexité / précision (BMBI) :</b> Comparaison entre modèles physiques analytiques (10 coefficients) et réseaux profonds 4D <b>SIREN</b> (<b>IoU = 99,65%</b>, Gauss-Bonnet vérifié à 0,025%).",
                        "<b>Pédagogie &amp; communication (Complétude) :</b> 4 ans d'accompagnement scientifique personnalisé ; vulgarisation de concepts mathématiques auprès d'interlocuteurs aux profils variés.",
                    ],
                ),
            ]),
            ("Produits &amp; Outils Conçus de Bout en Bout (0 &rarr; 1)", [
                entry_block(
                    "PDF Live Notes — Espace de Travail Collaboratif Humain-Stylet + Agent IA",
                    "FastAPI, SSE, PDF.js, Android",
                    bullets=[
                        "Conception produit et développement d'une interface tablette où un tuteur IA annote en direct le PDF de l'utilisateur et génère à la volée des simulateurs visuels interactifs (<code>&lt;iframe&gt;</code> HTML5) pour illustrer les équations.",
                    ],
                ),
                entry_block(
                    "Jarvis &amp; MonLycée Auth Relay — Automatisation Métier &amp; Extension Navigateur",
                    "Python, Playwright, Manifest V3",
                    bullets=[
                        "Moteur d'aide à la décision multi-API (51 connecteurs ATS, jury de 3 LLMs à preuves verbatim) et extension navigateur <b>Manifest V3</b> d'authentification SSO déportée en 1 clic (&lt; 50 ms).",
                    ],
                ),
                entry_block(
                    "NF26 &amp; Custos — Entrepôt de Données Empreinte Carbone (ADEME) &amp; Produit Mobile",
                    "Python, SQL, Kotlin",
                    bullets=[
                        "Conception d'un pipeline ETL et Data Warehouse analytique sur la Base Carbone ADEME ; développement d'une application Android (<b>Custos</b>) de gestion du temps d'écran par engagements irrévocables (<i>commitment device</i>).",
                    ],
                ),
            ]),
            ("Formation Académique", [
                entry_block(
                    "Diplôme d'Ingénieur en Génie Informatique — Filière IAD &amp; Label Mod'Math",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Double compétence IA &amp; Modélisation :</b> Apprentissage statistique &amp; Deep Learning (<i>SY09, SY32</i>), Recherche Opérationnelle &amp; Optimisation (<i>RO04, RO05</i>), Conception logicielle &amp; Gestion de projet (<i>LO21, NF26</i>).",
                    ],
                ),
                entry_block("Classes Préparatoires aux Grandes Écoles (CPGE PTSI / PT)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
        ],
        "skills": [
            ("Product &amp; Stratégie IA", "Cadrage 0&rarr;1, Discovery, Spécifications fonctionnelles/techniques, Arbitrage coût/latence/risque, KPIs (F1, AUC, ECE)"),
            ("Stack Technique", "Python, SQL, PyTorch, LLMs (Prompting, JSON, RAG), API REST (FastAPI/Flask), React, Docker, Git, Quarto/LaTeX"),
            ("Méthodes", "Agile / Scrum, Documentation structurée, Design d'expériences, Vulgarisation client"),
            ("Langues", "Français (natif), Anglais (professionnel courant B2+)"),
        ],
    },
    # 8. Tier A — Technical Product Manager (EN)
    {
        "slug": "cv_product_manager_en",
        "dest_dirs": [BASE_CAND / "4_Product_Management_Tech"],
        "extra_names": {},
        "subtitle": "Technical Product Manager — AI, Data &amp; Systems",
        "tagline": "M.Eng. UTC (<b>Mod'Math Honors</b>) &bull; AI Product Scoping, Cost/Risk Trade-Offs &amp; Delivery",
        "loc": "Paris, France (Open to Relocation: EU / CH / UK)",
        "sections": [
            ("Professional Experience &amp; AI Product Delivery", [
                entry_block(
                    "Epiconcept — R&amp;D Data Science &amp; European Public Health",
                    "March 2026 – Sept. 2026 (6 months)",
                    "AI Technical Product &amp; Research Intern — Clinical LLM Products &amp; Medical Vision",
                    "Paris, France",
                    [
                        "<b>Product Scoping &amp; Cost/Performance Trade-Offs (ECDC European Project):</b> Defined the technical roadmap for an automated hospital-infection surveillance product under strict GDPR and hardware constraints (on-premise, <b>1&times; NVIDIA A100 40 GB</b>). Benchmarked 20 LLM setups and proved that a specialized 4B model (<b>MedGemma-4B</b>, <b>F1 = 0.91</b>) outperformed 27B/32B models while cutting latency and compute cost.",
                        "<b>Trust-by-Design &amp; International Rollout:</b> Designed a deterministic evidence-grounding protocol (<code>evidence_is_grounded</code>) requiring verbatim clinical quotes for clinician auditability; validated zero-shot rollout to Croatian hospitals (<b>F1 = 0.88</b>).",
                        "<b>Clinical Risk Management in Mammography Screening:</b> Translated clinical safety requirements into a dual-threshold selective abstention rule (FNR &le; 5%, FPR &le; 5% on the <b>GMIC</b> model at <b>AUC = 0.889</b>), routing ambiguous cases to human radiologists.",
                        "<b>Stakeholder Enablement:</b> Co-created an 8-chapter interactive training capsule (<b>Docker / Jupyter</b>) and a 6-chapter Quarto playbook for epidemiologists and engineering teams.",
                    ],
                ),
                entry_block(
                    "Aubay — Innovation Department",
                    "Sept. 2024 – Feb. 2025 (6 months)",
                    "Technical Product Owner &amp; Data Science Intern — Data Quality Audit Platform",
                    "Boulogne-Billancourt, France",
                    [
                        "<b>0-to-1 Full-Stack Product Delivery:</b> Gathered stakeholder requirements, benchmarked deep tabular anomaly models (<b>GANDALF</b>, <b>FT-Transformer</b>, <b>Isolation Forest</b>, <b>F1 = 0.903</b>), and delivered a containerized web platform (<b>Flask / React / AWS S3 / Docker</b>).",
                        "<b>Decision Framework:</b> Established a formal taxonomy of point, collective, and contextual anomalies to guide consulting teams on model selection and data-cleaning ROI.",
                    ],
                ),
                entry_block(
                    "BMBI Lab (CNRS UMR 7338) &amp; Complétude",
                    "2022 – 2026",
                    "3D/4D Modeling Researcher (5 months) &amp; STEM Instructor (4 years)",
                    "Compiègne / Paris, France",
                    [
                        "<b>Model Parsimony vs. Complexity (BMBI):</b> Evaluated analytical physical models (10 parameters) against 4D <b>SIREN</b> neural networks (<b>IoU = 99.65%</b>, Gauss-Bonnet verified to 0.025%).",
                        "<b>Communication &amp; Coaching (Complétude):</b> 4+ years of 1-on-1 STEM instruction, translating abstract quantitative concepts into clear, actionable mental models.",
                    ],
                ),
            ]),
            ("0-to-1 Products &amp; Systems Built", [
                entry_block(
                    "PDF Live Notes — Real-Time Human Stylus + AI Collaborative Workspace",
                    "FastAPI, SSE, PDF.js, Android",
                    bullets=[
                        "Designed and built a real-time tablet workspace where an AI tutor streams live vector annotations onto a user's PDF and injects sandboxed <b>interactive HTML5 simulation widgets (<code>&lt;iframe&gt;</code>)</b> to visualize mathematical concepts.",
                    ],
                ),
                entry_block(
                    "Jarvis &amp; MonLycée Auth Relay — Decision Engine &amp; Browser Extension",
                    "Python, Playwright, Manifest V3",
                    bullets=[
                        "Multi-ATS intelligence engine (51 European connectors, 3-LLM grounded evaluation jury) and 1-click <b>Manifest V3</b> browser extension for remote SSO session brokering (&lt; 50 ms cache).",
                    ],
                ),
                entry_block(
                    "NF26 &amp; Custos — Carbon Footprint Data Warehouse (ADEME) &amp; Mobile Product",
                    "Python, SQL, Kotlin",
                    bullets=[
                        "Designed an end-to-end ETL pipeline and dimensional Data Warehouse on the ADEME Carbon Database; built a native Android commitment-device product (<b>Custos</b>) for digital focus.",
                    ],
                ),
            ]),
            ("Education", [
                entry_block(
                    "Master of Engineering (M.Eng.) in Computer Science, AI &amp; Mathematical Modeling",
                    "2023 – 2026",
                    "Université de Technologie de Compiègne (UTC)",
                    "Compiègne, France",
                    [
                        "<b>Dual AI &amp; Modeling Track:</b> Statistical Learning &amp; Deep Vision (<i>SY09, SY32</i>), Operations Research &amp; Optimization (<i>RO04, RO05</i>), Software Architecture &amp; Data Engineering (<i>LO21, NF26</i>).",
                    ],
                ),
                entry_block("Preparatory Classes for Grandes Écoles (CPGE PTSI / PT — Intensive Math &amp; Physics)", "2020 – 2023", "Lycée Raspail", "Paris, France"),
            ]),
        ],
        "skills": [
            ("Product &amp; AI Strategy", "0&rarr;1 Product Discovery, PRDs &amp; Technical Specs, Latency/Cost/Risk Trade-Offs, Evaluation Metrics (F1, AUC, ECE)"),
            ("Technical Stack", "Python, SQL, PyTorch, LLMs (Prompting, JSON, Grounded RAG), REST APIs (FastAPI/Flask), React, Docker, Git, Quarto"),
            ("Methodology", "Agile / Scrum, Experiment Design, Technical Writing, Stakeholder Alignment"),
            ("Languages", "French (Native), English (Professional Working Proficiency B2+)"),
        ],
    },
]


def render_cv_pdf(spec: dict) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)  # A4

    # Insert photo in top-right corner
    photo_w = 56
    photo_h = 68
    photo_rect = fitz.Rect(595.28 - 24 - photo_w, 20, 595.28 - 24, 20 + photo_h)
    if PHOTO_PATH.exists():
        page.insert_image(photo_rect, filename=str(PHOTO_PATH), keep_proportion=True)

    # Header HTML (left of photo)
    header_rect = fitz.Rect(24, 18, 595.28 - 24 - photo_w - 8, 20 + photo_h)
    header_html = build_header_html(spec["subtitle"], spec["tagline"], spec["loc"])
    page.insert_htmlbox(header_rect, header_html, css=CSS_STYLE)

    # Main Body HTML (below header)
    body_parts = []
    for sec_title, items in spec["sections"]:
        body_parts.append(f'<div class="section-title">{sec_title}</div>')
        body_parts.extend(items)

    # Skills section
    sk = spec["skills"]
    skills_title = "Compétences Techniques" if "_fr" in spec["slug"] or spec["slug"] in ("cv_data_ia_engineer", "cv_product_manager") else "Technical Skills"
    body_parts.append(f'<div class="section-title">{skills_title}</div>')
    body_parts.append(f"""
    <table class="skills-table">
        <tr>
            <td style="width: 52%;"><b>{sk[0][0]} :</b> {sk[0][1]}</td>
            <td style="width: 48%;"><b>{sk[1][0]} :</b> {sk[1][1]}</td>
        </tr>
        <tr>
            <td style="width: 52%;"><b>{sk[2][0]} :</b> {sk[2][1]}</td>
            <td style="width: 48%;"><b>{sk[3][0]} :</b> {sk[3][1]}</td>
        </tr>
    </table>
    """)

    body_rect = fitz.Rect(24, 20 + photo_h + 2, 595.28 - 24, 841.89 - 18)
    rc = page.insert_htmlbox(body_rect, "\n".join(body_parts), css=CSS_STYLE)

    out_portfolio = PORTFOLIO_CV_DIR / f"{spec['slug']}.pdf"
    doc.save(str(out_portfolio), garbage=4, deflate=True)
    doc.close()

    # Copy to Candidatures and CV_latex
    for d in spec["dest_dirs"]:
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_portfolio, d / f"{spec['slug']}.pdf")
        if d in spec.get("extra_names", {}):
            shutil.copy2(out_portfolio, d / spec["extra_names"][d])

    print(f"[OK] {spec['slug']}.pdf generated (spare_height={rc[0]:.1f}pt, scale={rc[1]:.3f})")
    return out_portfolio


def main():
    for spec in CV_SPECS:
        render_cv_pdf(spec)

    # Sync .tex files to CV_latex as well
    shutil.copy2(
        BASE_CAND / "7_RO_ModMath_Quant_RD_IA" / "cv_ro_modmath_rd_en.tex",
        CV_LATEX_DIR / "cv.tex",
    )
    shutil.copy2(
        BASE_CAND / "7_RO_ModMath_Quant_RD_IA" / "cv_ro_modmath_rd_fr.tex",
        CV_LATEX_DIR / "cv_fr.tex",
    )


if __name__ == "__main__":
    main()
