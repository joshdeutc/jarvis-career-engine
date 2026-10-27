# Total Pages: 14

## --- PAGE 1 ---

Conception d'une Architecture 
Serverless pour l'Agrégation de Données 
ATS, le Traitement par LLM et la 
Notification : Une Approche 
Multidisciplinaire 
L'agrégation et l'analyse de données non structurées issues d'Internet représentent un défi 
fondamental en ingénierie logicielle contemporaine, en particulier dans les domaines de la 
veille stratégique, du recrutement technologique et de la surveillance épidémiologique. La 
fragmentation endémique des plateformes de publication, couplée à la variabilité sémantique 
inhérente aux descriptions textuelles, rend les approches traditionnelles par expressions 
régulières (Regex) ou par scraping web heuristique particulièrement fragiles. L'écosystème 
open-source actuel, tel qu'observé sur des plateformes collaboratives comme GitHub, manque 
d'architectures intégrées, légères et sans serveur (serverless) capables de surveiller de 
manière autonome ces flux de données, d'en extraire le sens avec une précision déterministe, 
et de notifier les utilisateurs finaux tout en respectant les contraintes strictes des API de 
messagerie. 
Ce rapport détaille la conception exhaustive d'un pipeline d'automatisation complet qui comble 
cette lacune architecturale. La solution développée s'articule autour de plusieurs piliers 
technologiques et théoriques : l'ingestion de données via les API publiques et non 
documentées des principaux systèmes de suivi des candidatures (Applicant Tracking Systems 
ou ATS) ; la modélisation stochastique des requêtes réseau via les processus de Poisson et les 
chaînes de Markov ; l'extraction et la validation d'entités via des grands modèles de langage 
(LLM) interfacés par la bibliothèque Instructor et Pydantic ; un moteur de diffusion asynchrone 
orchestré par l'API Telegram ; et enfin, une orchestration serverless reposant sur les workflows 
GitHub Actions et la persistance d'état asymétrique via Git. 
Exploration et Rétro-Ingénierie des Systèmes de Suivi 
des Candidatures (ATS) 
La majorité des entreprises technologiques modernes s'appuient sur des ATS pour gérer la 
publication de leurs offres d'emploi. Bien que ces plateformes soient prioritairement conçues 
pour être interrogées par des widgets front-end intégrés aux sites carrières, elles exposent des 
API REST publiques (ou nécessitant des clés publiques) d'une immense richesse1. L'exploitation 
de ces points d'accès (endpoints) permet de s'affranchir des techniques lourdes d'extraction 
web, qui nécessitent l'instanciation coûteuse de navigateurs "headless" (sans interface 
graphique), et d'obtenir directement des données structurées au format JSON avec une 
latence réseau minimale2. 


## --- PAGE 2 ---

L'Écosystème Greenhouse 
Greenhouse s'est imposé comme l'ATS prédominant pour les startups technologiques en 
phase de croissance2. L'API Job Board de Greenhouse permet d'extraire l'intégralité des offres 
ouvertes d'une entreprise via une simple requête HTTP GET3. L'endpoint principal est structuré 
de la manière suivante : https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs3. 
L'ajout de paramètres spécifiques à cette requête modifie substantiellement la charge utile 
(payload) retournée. Le paramètre ?content=true force l'API à inclure le code HTML complet de 
la description du poste, ainsi que les métadonnées hiérarchiques relatives aux départements et 
aux bureaux géographiques5. Un second paramètre, ?questions=true, permet de récupérer la 
structure exhaustive du formulaire de candidature, y compris les champs personnalisés et les 
menus déroulants requis pour postuler4. Cette fonctionnalité est d'une importance capitale, car 
elle permet de modéliser dynamiquement la complexité d'une candidature sans nécessiter de 
rendu JavaScript côté client7. 
Toutefois, l'API Greenhouse présente une limitation majeure : l'absence de filtrage natif par 
mot-clé ou par date de publication3. Cette contrainte impose une récupération totale des 
données (full fetch) à chaque exécution3. L'objet JSON retourné contient systématiquement un 
identifiant interne, un titre, une localisation, une URL absolue, et un horodatage updated_at3. 
C'est cet horodatage qui permet aux systèmes tiers de gérer l'état différentiel lors des 
exécutions successives du pipeline. 
L'Architecture Lever 
Contrairement à l'approche de Greenhouse, l'API de Lever propose un moteur de recherche 
natif et une pagination intégrée, ce qui permet de réduire considérablement la bande passante 
utilisée3. L'endpoint https://api.lever.co/v0/postings/{site}?mode=json autorise le filtrage direct à 
la source en utilisant des paramètres de requête tels que team, department, location, ou 
commitment3. 
L'implémentation de la pagination sur Lever repose sur l'utilisation conjointe des paramètres 
skip et limit3. Bien qu'un paramètre limit=100 puisse être défini de manière statique, une 
architecture robuste doit implémenter une boucle de pagination qui itère jusqu'à ce que la taille 
du tableau JSON retourné soit strictement inférieure à la limite spécifiée6. La structure des 
données de Lever est particulièrement détaillée concernant la catégorisation, isolant de 
manière explicite le lieu de travail (workplaceType pouvant prendre les valeurs unspecified, 
on-site, remote, ou hybrid) et les plages salariales via l'objet salaryRange (incluant la devise, le 
minimum et le maximum)8. 
Les Modèles Ashby, SmartRecruiters et Workable 
Le marché des ATS comporte d'autres acteurs majeurs dont les API nécessitent des stratégies 
d'interrogation spécifiques. L'harmonisation de ces sources hétérogènes constitue la première 
étape de tout pipeline d'agrégation. 
 
Plateforme ATS 
Endpoint Public Typique 
Caractéristiques 


## --- PAGE 3 ---

Techniques et Limites 
Ashby 
api.ashbyhq.com/posting
-api/job-board/{board} 
Supporte le paramètre 
?includeCompensation=tr
ue pour extraire des 
données salariales 
structurées. Le flux public 
ne dispose pas de filtrage 
natif avancé3. L'indicateur 
isListed permet d'exclure 
les offres masquées3. 
SmartRecruiters 
api.smartrecruiters.com/v
1/companies/{company}/p
ostings 
Expose le paramètre 
updatedAfter pour 
interroger uniquement les 
offres récentes (delta 
fetch). La pagination 
s'effectue via les 
paramètres limit et 
offset11. 
Workable 
apply.workable.com/api/v
1/widget/accounts/{accou
nt} 
Nécessite l'injection du 
paramètre ?details=true 
pour obtenir le contenu 
des descriptions3. Les 
métadonnées complexes 
requièrent parfois des 
appels additionnels vers 
d'autres endpoints3. 
L'architecture de collecte doit également anticiper les comportements erratiques ou non 
documentés des API. Par exemple, l'évaluation empirique de certains paramètres de pagination 
(comme un limit=-1 ou limit=not-a-number) démontre que les serveurs gèrent ces anomalies 
de manière inconsistante, retournant parfois un code HTTP 200 avec l'intégralité de la base de 
données, ou ignorant purement et simplement le paramètre14. Une gestion stricte des 
exceptions HTTP est donc impérative. 
Modélisation Mathématique de l'Ingestion des 
Données 
Pour concevoir un script optimal qui s'exécute dans un environnement serverless (tel que 
GitHub Actions) sans épuiser les quotas de calcul et sans surcharger les serveurs distants, il est 
essentiel de modéliser mathématiquement le comportement des sources de données. 


## --- PAGE 4 ---

L'application de la théorie des probabilités et de la modélisation stochastique permet de 
dimensionner précisément la fréquence d'interrogation (polling frequency). 
Espaces Probabilisés et Fondations Théoriques 
Toute modélisation rigoureuse débute par la définition d'un espace probabilisé formel 
15. L'univers 
 représente l'ensemble des résultats possibles d'une observation de 
l'API. La tribu 
 est un sous-ensemble de l'ensemble des parties de 
, stable par passage au 
complémentaire et par union dénombrable15. La mesure de probabilité 
 associe à chaque 
événement de la tribu une valeur comprise entre 0 et 115. 
L'état d'un ATS à un instant  peut être décrit par des vecteurs aléatoires, construits sur la tribu 
borélienne 
15. La loi de probabilité induite par ces variables détermine la probabilité de 
découvrir de nouvelles offres d'emploi ou de constater la clôture d'offres existantes15. 
L'indépendance de ces événements, bien que souvent assumée pour simplifier les modèles (où 
), est rarement stricte dans la réalité, car les campagnes de recrutement 
suivent des cycles organisationnels précis15. 
Modélisation des Arrivées via les Processus de Poisson 
L'apparition de nouvelles publications sur un tableau d'offres d'emploi peut être modélisée avec 
précision par un processus de comptage stochastique, spécifiquement un processus de 
Poisson non homogène 
16. Contrairement à un processus homogène où l'intensité 
 est constante, le recrutement suit des variations temporelles fortes16. 
La fonction d'intensité 
 fluctue selon les heures ouvrées, les jours de la semaine et les 
saisons. La fonction moyenne associée, représentant l'espérance du nombre d'offres publiées 
jusqu'à l'instant , est définie par l'intégrale : 
 
La probabilité d'observer 
 nouvelles offres dans un intervalle de temps 
 est alors 
régie par la loi de Poisson : 
 
Cette modélisation a des implications architecturales directes16. Si le pipeline interroge les API 


## --- PAGE 5 ---

durant le week-end, la valeur de 
 est proche de zéro, rendant l'espérance de 
 quasi nulle. L'orchestrateur (le cron de GitHub Actions) doit donc être paramétré 
pour aligner sa fréquence de déclenchement sur les pics de la fonction d'intensité 
 (par 
exemple, concentrer les exécutions entre 8h00 et 18h00 en semaine), maximisant ainsi 
l'efficacité énergétique et computationnelle du script17. 
Les Chaînes de Markov et le Cycle de Vie des Données 
Le cycle de vie temporel d'une annonce ou de la disponibilité d'une donnée peut être décrit 
formellement par une chaîne de Markov à temps continu ou discret18. Soit un processus 
stochastique 
 évoluant dans un espace d'états discret 
19. 
La propriété fondamentale de Markov stipule que la probabilité de transition vers un état futur 
ne dépend que de l'état présent, et non de l'historique complet : 
 
La dynamique du système est entièrement caractérisée par la matrice de transition 
18. Dans 
notre contexte de surveillance des API, l'état "Fermé" constitue un état absorbant. Un état  est 
dit absorbant si la probabilité d'y rester est totale, soit 
18. Les autres états sont 
qualifiés de transitoires (transient), car la probabilité que le processus y retourne infiniment 
souvent est nulle (
)19. 
L'application de ce modèle simplifie radicalement la gestion de l'état du script. Étant donné 
qu'une offre disparue de l'API publique est mathématiquement absorbée par l'état "Fermé", le 
script n'a pas besoin de requêter un endpoint spécifique pour confirmer la suppression. La 
simple absence de l'identifiant dans le vecteur de réponse justifie la mise à jour asymétrique de 
la base de données locale, évitant ainsi des requêtes HTTP superflues. 
L'étude comportementale asymptotique de ces processus, via le théorème ergodique et le 
calcul des distributions stationnaires 
 (où 
), permet également de modéliser le 
nombre moyen d'offres actives sur le long terme, dimensionnant ainsi la capacité de stockage 
requise pour les fichiers d'état JSON locaux21. 
Extraction Sémantique et Structuration par Modèles 
de Langage (LLM) 
Une fois le code HTML brut ou le texte des descriptions de poste extrait, la phase la plus 
délicate consiste à en déduire des entités structurées de haute précision. La sémantique 
humaine étant hautement variable, l'extraction de métadonnées (années d'expérience, pile 
technologique, exigences salariales) dépasse les capacités des expressions régulières 


## --- PAGE 6 ---

classiques. 
Les Défaillances de l'Extraction Naïve par LLM 
L'approche naïve, consistant à soumettre le texte brut à un modèle de langage avec une 
instruction du type "Extrais les compétences et le salaire au format JSON", présente des 
défaillances systémiques documentées22. Les LLM étant par nature stochastiques, ils génèrent 
fréquemment des hallucinations structurelles : modification imprévisible des clés du 
dictionnaire JSON, instabilité du formatage temporel (alternance entre "Jan 5", "2025-01-05", 
ou "05/01/25"), ou violation des types de données (retourner une chaîne de caractères textuelle 
là où un entier strict est attendu)22. Ces erreurs de coercition de type corrompent 
inévitablement les bases de données et les processus en aval. 
Le Paradigme Pydantic et Instructor 
Pour résoudre cette instabilité de manière déterministe, l'industrie converge vers l'utilisation de 
Pydantic (le standard Python pour la validation de données) couplé à la bibliothèque 
open-source Instructor23. Instructor agit comme une couche d'abstraction logicielle (wrapper) 
autour des clients API des LLM (OpenAI, Anthropic, ou Groq) afin de contraindre la génération 
de texte à respecter scrupuleusement un schéma JSON défini, exploitant les fonctionnalités de 
"Function Calling" ou de "JSON Schema Mode" des modèles25. 
La conception du schéma d'extraction exige une ingénierie de prompt implicite. Chaque champ 
du modèle Pydantic est enrichi d'une description (Field description) qui oriente l'attention 
(attention mechanism) du modèle lors de l'inférence22. 
 
 
 
Python 
from pydantic import BaseModel, Field, field_validator​
from typing import List, Optional​
import instructor​
from groq import Groq​
​
class JobExtraction(BaseModel):​
    is_relevant: bool = Field(..., description="Vrai si l'offre concerne spécifiquement l'ingénierie IA, 
la Data Science ou la modélisation mathématique.")​
    tech_stack: List[str] = Field(..., description="Liste des technologies, langages et frameworks 
mentionnés, par exemple : Python, PyTorch Tabular, C/C++, Go.")​
    years_of_experience: int = Field(0, description="Années d'expérience minimum requises. 
Mettre 0 si non spécifié.")​
    salary_min_eur: Optional[float] = Field(None, description="Salaire minimum annuel, converti 
en euros si nécessaire.")​
 
La puissance de ce paradigme réside dans l'application des mécanismes de validation natifs de 


## --- PAGE 7 ---

Python aux flux génératifs de l'intelligence artificielle27. La méthode 
instructor.from_provider("groq/llama-3.3-70b-versatile") permet d'initialiser un client unifié 
capable d'interagir avec n'importe quel modèle open-source23. 
Validation Autonome et Boucles de Réflexion (Self-Correction) 
L'innovation conceptuelle majeure de la bibliothèque Instructor est sa capacité à orchestrer des 
boucles de réflexion et de correction automatique (retries) en cas d'échec de validation23. 
Les développeurs peuvent intégrer des validateurs stricts directement dans le modèle de 
données : 
 
 
 
Python 
    @field_validator('years_of_experience')​
    def validate_experience(cls, v):​
        if v < 0 or v > 40:​
            raise ValueError("Erreur de cohérence : les années d'expérience doivent être comprises 
entre 0 et 40.")​
        return v​
 
Si le LLM retourne une valeur aberrante, Pydantic lève une exception ValidationError22. Le 
framework Instructor intercepte cette exception, formate un prompt de correction contenant 
l'erreur exacte générée par Python, et renvoie la requête au LLM25. Ce mécanisme de 
"Validation Gate" garantit mathématiquement que 100 % des données atteignant la sortie de la 
fonction respecteront le contrat de données, éradiquant les pannes silencieuses du pipeline23. 
Convergence Interdisciplinaire : De la Data Science à la Santé Publique 
L'architecture d'extraction sémantique décrite ci-dessus trouve des applications qui dépassent 
largement le cadre du recrutement. L'analyse de profils complexes (comme ceux exigeant la 
maîtrise de frameworks spécifiques tels que PyTorch Tabular, FT-Transformer, GANDALF, ou 
des algorithmes de détection d'anomalies comme l'Isolation Forest33) démontre la flexibilité du 
système. 
Cette même architecture de validation par LLM peut être déployée pour des analyses de santé 
publique ou des études épidémiologiques35. Par exemple, une étude portant sur l'analyse de 46 
407 tweets liés au diabète et au prix de l'insuline aux États-Unis a mis en évidence l'importance 
de classifier des données textuelles non structurées36. Dans cette étude, des algorithmes de 
clustering et d'analyse de sentiments (VADER) ont identifié que 18 % des messages traitaient 
spécifiquement du prix de l'insuline, générant des émotions primaires de frustration, de 
tristesse, ou de colère36. 
Si ce pipeline de scraping était réorienté vers les réseaux sociaux (via des API comparables), le 
modèle Pydantic pourrait être redéfini pour extraire le score de détresse lié au diabète 
(Diabetes Distress Score), la présence de mots-clés émotionnels (DDS, PAID questionnaires), 


## --- PAGE 8 ---

ou les mentions de comorbidités36. Le LLM, contraint par Instructor, classifierait chaque 
message entrant dans l'un des 30 clusters émotionnels identifiés par les chercheurs, 
démontrant ainsi la portabilité de l'approche serverless proposée36. 
Moteur de Diffusion Asynchrone : Maîtrise de l'API 
Telegram Bot 
Une fois les données filtrées, validées et structurées, le système doit notifier les abonnés en 
temps réel. L'API Telegram Bot offre une interface HTTP extrêmement robuste pour cette tâche, 
mais elle impose des mécanismes de limitation de débit (rate limiting) particulièrement stricts. 
Ignorer ces limites expose l'application à une exclusion temporaire ou à la révocation définitive 
du jeton d'accès (token)37. 
Algorithmique du Contrôle de Congestion (Rate Limiting) 
Les contraintes de l'API Telegram sont documentées de manière empirique par la communauté 
des développeurs. Les limites globales se situent à environ 30 messages par seconde pour 
l'ensemble du bot38. Au niveau granulaire, les limites sont fixées à 20 messages par minute pour 
un groupe spécifique, et à environ 1 message par seconde pour une discussion privée 
individuelle38. 
Le franchissement de ces seuils déclenche un rejet immédiat de la requête, matérialisé par une 
erreur HTTP 429 Too Many Requests38. Le corps de cette réponse JSON contient un paramètre 
critique : retry_after, qui indique sous forme d'entier le nombre de secondes pendant lesquelles 
le bot est banni et doit suspendre toute activité réseau38. Une itération aveugle (tight loop) 
ignorant ce paramètre engendre une augmentation exponentielle de la pénalité37. 
L'implémentation d'un algorithme de contrôle de flux, tel qu'un "Token Bucket" ou une file 
d'attente asynchrone avec délai (delay queue), est donc indispensable39. L'extrait de code 
suivant modélise cette gestion protectrice en Python : 
 
 
 
Python 
import time​
import requests​
​
last_sent_per_chat = {}​
GLOBAL_RATE_LIMIT_MARGIN = 25 # Seuil conservateur sous la limite théorique de 30 
msgs/sec​
​
def send_telegram_message_safe(chat_id, text, token, parse_mode='HTML'):​
    # Respect de la limite granulaire de 1 message par seconde par chat​
    wait_time = 1.0 - (time.time() - last_sent_per_chat.get(chat_id, 0))​
    if wait_time > 0:​


## --- PAGE 9 ---

        time.sleep(wait_time)​
        ​
    api_url = f'https://api.telegram.org/bot{token}/sendMessage'​
    payload = {​
        'chat_id': chat_id,​
        'text': text,​
        'parse_mode': parse_mode,​
        'disable_web_page_preview': True​
    }​
    ​
    response = requests.post(api_url, json=payload)​
    ​
    if response.status_code == 429:​
        # Algorithme de circuit breaker : suspension selon l'injonction de l'API​
        retry_after = response.json().get('parameters', {}).get('retry_after', 5)​
        time.sleep(retry_after)​
        return send_telegram_message_safe(chat_id, text, token, parse_mode) # Récursivité 
protectrice​
        ​
    last_sent_per_chat[chat_id] = time.time()​
    return response.json()​
 
Cette architecture de temporisation permet au pipeline d'absorber d'importants volumes de 
données (par exemple, lors d'une première exécution qui découvrirait des centaines de 
nouvelles entités) sans violer les politiques de service de Telegram39. 
Typographie et Échappement des Caractères : HTML vs MarkdownV2 
Pour garantir la lisibilité des notifications sur des terminaux mobiles, l'API Telegram permet 
l'enrichissement sémantique du texte (Message Entities) via les modes MarkdownV2 et HTML43. 
Le mode MarkdownV2 exige l'échappement rigoureux de nombreux caractères spéciaux 
courants (tels que les tirets, points, parenthèses, accolades) à l'aide d'une barre oblique inverse 
(\)45. Cette exigence rend ce format particulièrement cassant et source d'erreurs lorsqu'il s'agit 
d'afficher du texte généré par un LLM, où la présence de ponctuations arbitraires est 
inévitable46. 
L'utilisation du paramètre parse_mode='HTML' est par conséquent fortement recommandée 
par les experts de l'écosystème46. Toutefois, Telegram n'accepte qu'un sous-ensemble restrictif 
de balises (essentiellement <b>, <i>, <u>, <s>, <a>, et <code>)46. L'intégration de balises non 
supportées ou mal fermées paralyse la requête et retourne l'erreur "400 Bad Request: can't 
parse entities"46. Il est impératif d'appliquer une fonction d'assainissement (sanitization) sur 
l'ensemble du contenu brut avant l'injection dans les balises, remplaçant systématiquement les 
symboles < par <, > par >, et & par & pour éviter toute corruption du parseur XML de Telegram45. 
Orchestration Serverless et Persistance d'État via Git 


## --- PAGE 10 ---

L'ultime défi d'une telle architecture réside dans son déploiement. L'utilisation de serveurs 
dédiés (VPS) ou de conteneurs hébergés (AWS EC2) engendre des coûts d'infrastructure et 
une complexité de maintenance souvent injustifiés pour des tâches d'agrégation légères. La 
solution optimale consiste à détourner les plateformes d'intégration et de déploiement 
continus (CI/CD), en particulier GitHub Actions, pour transformer un simple dépôt de code en 
un moteur d'exécution autonome et gratuit49. 
Déclenchement Temporel (Cron Workflows) 
L'orchestration temporelle du script s'effectue via l'événement on: schedule défini dans un 
fichier de configuration YAML situé dans le répertoire .github/workflows/50. En utilisant la 
syntaxe cron POSIX (par exemple - cron: '0 */4 * * *' pour une exécution toutes les quatre 
heures), le service GitHub alloue un conteneur éphémère (généralement basé sur 
ubuntu-latest), clone le code source, configure l'interpréteur Python, installe les dépendances 
requises (pip install pydantic instructor groq requests), et exécute la logique métier17. 
Les identifiants sensibles, tels que la clé API Groq ou le jeton du bot Telegram, sont injectés de 
manière sécurisée sous forme de variables d'environnement via le gestionnaire de secrets de 
GitHub (GitHub Secrets), garantissant l'intégrité cryptographique du système50. 
La Persistance d'État Asymétrique par Auto-Commit 
La difficulté conceptuelle inhérente aux architectures serverless est leur amnésie structurelle 
(statelessness). À la fin de chaque exécution du workflow, l'environnement virtuel est détruit. 
Pour éviter que le bot Telegram ne renvoie perpétuellement les mêmes offres d'emploi, le 
système doit posséder une mémoire à long terme lui permettant de discriminer les annonces 
déjà traitées des annonces inédites. 
Plutôt que de provisionner une base de données externe (comme Redis ou PostgreSQL), la 
persistance de l'état peut être réalisée directement au sein de l'arborescence du dépôt Git 
sous la forme d'un fichier JSON local (par exemple, seen_jobs.json)51. Ce fichier fait office de 
base de données relationnelle asymétrique, stockant les clés uniques (UUID ou empreintes 
cryptographiques) des entités traitées. 
À l'issue de la phase de notification, si de nouvelles données ont été identifiées, le script Python 
met à jour ce fichier JSON sur le disque virtuel de l'environnement GitHub Actions. L'étape 
finale du pipeline YAML fait alors appel à l'action open-source 
stefanzweifel/git-auto-commit-action53. 
Cette action GitHub analyse l'arbre de travail (working tree) pour détecter les modifications 
(dirty check), génère un commit automatisé encapsulant les nouvelles données, et effectue un 
git push vers la branche principale du dépôt54. L'intégration de ce mécanisme requiert de 
configurer explicitement les permissions du workflow avec la directive contents: write55. 
 
 
 
YAML 
      - name: Persistance de la base de données asymétrique​


## --- PAGE 11 ---

        uses: stefanzweifel/git-auto-commit-action@v5​
        with:​
          commit_message: "chore(data): synchronisation de l'état dans seen_jobs.json"​
          file_pattern: 'seen_jobs.json'​
 
Cette approche ingénieuse offre une série d'avantages opérationnels inégalés : elle réduit les 
coûts d'infrastructure de base de données à zéro, fournit une traçabilité native et auditable de 
toutes les modifications via l'historique des commits Git, et garantit la portabilité totale de la 
solution informatique56. 
Conclusions Analytiques 
L'élaboration de ce pipeline serverless adresse directement et efficacement le vide 
technologique identifié dans les dépôts open-source concernant l'extraction intelligente de 
données en continu. L'architecture décrite fusionne des disciplines variées — ingénierie 
logicielle, probabilités, intelligence artificielle générative, et administration réseau — pour créer 
un système résilient et entièrement automatisé. 
L'exploitation des API non authentifiées des ATS (Greenhouse, Lever, Ashby, etc.) supprime la 
nécessité de recourir au web scraping instable. En modélisant les cycles d'interrogation sur les 
processus de Poisson et les chaînes de Markov, la charge computationnelle est optimisée. 
L'apport décisif réside dans l'intégration de Pydantic et de la bibliothèque Instructor pour 
contraindre les sorties des modèles LLM (tels que ceux hébergés par Groq), éliminant les 
hallucinations structurelles grâce aux boucles de réflexion autocorrectives. Enfin, la 
combinaison du contrôle de congestion granulaire imposé par l'API Telegram et de la 
persistance d'état via les commits automatisés de GitHub Actions parachève une solution ne 
nécessitant aucune infrastructure matérielle tierce. 
Ce schéma architectural transcende largement le cadre strict du suivi des offres d'emploi. Il 
établit une fondation robuste pour le développement d'agents d'intelligence artificielle 
autonomes, capables de surveiller des flux d'informations complexes (de la veille 
technologique spécialisée à la surveillance épidémiologique sur les réseaux sociaux), de les 
valider sémantiquement, et de déclencher des alertes ciblées en temps réel. 
Works cited 
1.​ Greenhouse Job Board API: Jobs & Company Data - Apify, 
https://apify.com/johnvc/greenhouse-job-board-api 
2.​ Greenhouse Jobs Scraper: ATS Job Listings API - Apify, 
https://apify.com/automation-lab/greenhouse-jobs-scraper 
3.​ 6 ATS Platforms with Public Job Posting APIs [2026] - Cavuno, 
https://cavuno.com/blog/ats-platforms-public-job-posting-apis 
4.​ greenhouse-api-docs/source/includes/job-board/_jobs.md at master, 
https://github.com/grnhse/greenhouse-api-docs/blob/master/source/includes/job
-board/_jobs.md 
5.​ Introduction – Job Board API - Developer Resources | Greenhouse, 
https://docs.greenhouse.io/job-board.html 


## --- PAGE 12 ---

6.​ ats - Željko Šević | Node.js Developer, https://sevic.dev/tags/ats/ 
7.​ Greenhouse Job Board API: ?questions=true returns a posting's, 
https://agents.stackoverflow.com/tils/8596ae4f-2cc9-4c9b-a7eb-67592a796ced?
sort=newest&page=3 
8.​ API documentation and examples for the lever postings REST API, 
https://github.com/lever/postings-api 
9.​ Build a Framer careers page with Lever Postings API | BRIX Templates, 
https://brixtemplates.com/blog/how-to-build-a-framer-careers-page-with-levers
-postings-api 
10.​Ashby Job Postings API, 
https://developers.ashbyhq.com/docs/public-job-posting-api 
11.​Endpoints - The SmartRecruiters API Platform, 
https://developers.smartrecruiters.com/docs/endpoints 
12.​Get job postings - The SmartRecruiters API Platform, 
https://developers.smartrecruiters.com/docs/get-job-postings 
13.​Workable API: Job Board API, widget feed, keys and docs (2026), 
https://jobspipe.dev/sources/workable 
14.​13 Keyless Job APIs: A Broken `limit` Returns 200 Rows, or 0, 
https://blog.spinov.online/blog/free-job-board-apis-no-key/ 
15.​RO05_CM1.pdf 
16.​RO05_CM9_processus_poisson.pdf 
17.​juan-azabal/jobagent - GitHub, https://github.com/juan-azabal/jobagent 
18.​RO05_CM5.pdf 
19.​RO05_CM10.pdf 
20.​RO05_CM6_prof.pdf 
21.​RO05_CM7.pdf 
22.​Structured Data Extraction with LLMs, Python and Pydantic, 
https://www.rodrigo-arenas.com/en/blogs/structured-data-extraction-with-llms/ 
23.​instructor/docs/index.md at main - GitHub, 
https://github.com/jxnl/instructor/blob/main/docs/index.md 
24.​Instructor - Multi-Language Library for Structured LLM Outputs, 
https://python.useinstructor.com/ 
25.​567-labs/instructor: structured outputs for llms - GitHub, 
https://github.com/567-labs/instructor 
26.​Structured Output for Open Source and Local LLMs - Instructor, 
https://python.useinstructor.com/blog/2024/03/07/open-source-local-structured-
output-pydantic-json-openai/ 
27.​otienosteve/pydantic-validation-and-parsing - GitHub, 
https://github.com/otienosteve/pydantic-validation-and-parsing 
28.​Validators | Pydantic Docs, 
https://pydantic.dev/docs/validation/dev/concepts/validators/ 
29.​Structured Outputs with Groq AI and Pydantic - Instructor, 
https://python.useinstructor.com/integrations/groq/ 
30.​Groq AI Integration - Fast Structured Outputs - Instructor, 
https://python.useinstructor.com/examples/groq/ 


## --- PAGE 13 ---

31.​Instructor Structured Extraction with Pydantic Validation Gate - Kestra, 
https://kestra.io/blueprints/instructor-structured-extraction-with-pydantic-valida
tion-gate 
32.​How to Use Pydantic for LLMs: Schema, Validation & Prompts, 
https://pydantic.dev/articles/llm-intro 
33.​cv_fr.tex 
34.​rapport.pdf 
35.​Projets Data Science Santé Publique - 0_FSUPP_CPT - Google Drive.pdf 
36.​e001190.full.pdf 
37.​Telegram API: Bot API vs MTProto Explained (2026) - Activepieces, 
https://www.activepieces.com/blog/telegram-api-bot-api-vs-mtproto-explained-
2026 
38.​Telegram Bot API Rate Limits Explained — Calculator & Best Practices, 
https://botnamefinder.com/blog/telegram-bot-rate-limits-explained 
39.​Telegram Bot API Rate Limits Explained (2026) - aziqdev, 
https://aziqdev.com/blog/telegram-bot-api-rate-limits 
40.​How to solve rate limit errors from Telegram Bot API with GramIO, 
https://gramio.dev/rate-limits 
41.​Limiting your API requests: the right way | by Alexander Bareyko, 
https://medium.com/hackernoon/limiting-your-api-requests-the-right-way-9608
b661a0ce 
42.​Telegram机器人进阶：利用API实现自动化消息推送（附Python代码, 
https://blog.csdn.net/5f4d3s2a1q/article/details/150507683 
43.​Styled text with message entities - Telegram APIs, 
https://core.telegram.org/api/entities 
44.​ParseMode | grammY, https://grammy.dev/ref/types/parsemode 
45.​(almost) correct escaping for the Telegram's MarkdownV2 - GitHub, 
https://github.com/utterstep/telegram-escape 
46.​Telegram Bot API: send messages and marketing content, 
https://www.marketingskills.sh/OpenClaudia/openclaudia-skills/telegram-bot 
47.​How should I use parse_mode='HTML' in a Telegram Python bot?, 
https://stackoverflow.com/questions/56104009/how-should-i-use-parse-mode-h
tml-in-a-telegram-python-bot 
48.​Telegram Bot: a set of characters break out of HTML escape, 
https://stackoverflow.com/questions/77622632/telegram-bot-a-set-of-characters
-break-out-of-html-escape 
49.​Automation workflows with GitHub Actions and Webhooks, 
https://www.hughrundle.net/automation-workflows-with-github-actions-and-we
bhooks/ 
50.​Automate JavaScript Code Formatting Using GitHub Actions and, 
https://pradumnasaraf.dev/blog/code-formatting-github-actions 
51.​dayaki/job-monitor-bot: Automated job search bot that ... - GitHub, 
https://github.com/dayaki/job-monitor-bot 
52.​Track new job postings from Naukri, StepStone and Job Bank, 
https://dev.to/projectdev/track-new-job-postings-from-naukri-stepstone-and-jo


## --- PAGE 14 ---

b-bank-canada-for-a-niche-role-python-13c9 
53.​GitHub Actions | doloc, 
https://doloc.io/getting-started/frameworks/github-actions/ 
54.​Automated Localization: Github Actions + Localazy, 
https://localazy.com/blog/automated-localization-github-actions-localazy 
55.​Is there a way to push changes with a GitHub action? - Stack Overflow, 
https://stackoverflow.com/questions/55657835/is-there-a-way-to-push-changes
-with-a-github-action 
56.​Review of the git-auto-commit-action - Waylon Walker, 
https://waylonwalker.com/git-auto-commit-action-review/ 
57.​Install MegaLinter on GitHub Actions, https://megalinter.io/7.0.2/install-github/ 


