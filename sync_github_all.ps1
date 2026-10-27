# =============================================================================
# Script de synchronisation GitHub en 1 clic — Portfolio & Dépôts nettoyés
# Exécuter dans PowerShell : .\sync_github_all.ps1
# =============================================================================

$repos = @(
    @{ Name = "monlycee-relay (Misha)"; Path = "C:\Users\jo\Documents\Personnal_project\Misha_qui_casse_les_couilles"; Remote = "origin"; Branch = "main" },
    @{ Name = "pdf-live-notes"; Path = "C:\Users\jo\Documents\Personnal_project\pdf-live-notes"; Remote = "origin"; Branch = "main" },
    @{ Name = "Machine-learning-prediction (SY09)"; Path = "C:\Users\jo\Documents\Academy\UTC-academic-project\Machine-learning-prediction"; Remote = "origin"; Branch = "main" },
    @{ Name = "Seven-wonder-duel-in-C (LO21)"; Path = "C:\Users\jo\Documents\Academy\UTC-academic-project\Seven-wonder-duel-in-C"; Remote = "origin"; Branch = "main" },
    @{ Name = "self-system"; Path = "C:\Users\jo\Documents\Personnal_project\self-system"; Remote = "origin"; Branch = "main" },
    @{ Name = "CV_latex (Sans_image_et_en_anglais)"; Path = "C:\Users\jo\Documents\Academy\rapport_TN10\CV_latex"; Remote = "origin"; Branch = "main" },
    @{ Name = "tn10-medical-ai-showcase (NOUVEAU)"; Path = "C:\Users\jo\Documents\Personnal_project\tn10-medical-ai-showcase"; Remote = "origin"; Branch = "main" },
    @{ Name = "surfaces-implicites (BMBI TZ2)"; Path = "C:\Users\jo\Documents\Academy\UTC-academic-project\surfaces-implicites"; Remote = "joshdeutc"; Branch = "main" },
    @{ Name = "github-profile-joshdeutc (Profil GitHub)"; Path = "C:\Users\jo\Documents\Personnal_project\github-profile-joshdeutc"; Remote = "origin"; Branch = "main" },
    @{ Name = "joshdeutc.github.io (Portfolio Web)"; Path = "C:\Users\jo\Documents\Personnal_project\joshdeutc.github.io"; Remote = "origin"; Branch = "main" },
    @{ Name = "Jarvis_my_brother"; Path = "C:\Users\jo\Documents\Personnal_project\Jarvis_my_brother"; Remote = "origin"; Branch = "master" }
)

Write-Host "=== Synchronisation des dépôts GitHub (@joshdeutc) ===" -ForegroundColor Cyan
foreach ($r in $repos) {
    if (Test-Path $r.Path) {
        Write-Host "`n--> Push $($r.Name) [$($r.Path)]" -ForegroundColor Yellow
        git -C $r.Path push -u $r.Remote $r.Branch
    }
}
Write-Host "`n=== Terminé ! ===" -ForegroundColor Green
