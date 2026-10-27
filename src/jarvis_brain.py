"""
Jarvis Brain — Moteur d'indexation et de recherche locale (SQLite FTS5 BM25)
pour le Second Cerveau de Joshua Nancey.

Indexe :
- Le corpus maître vérifié (joshua_profile_corpus/)
- Tous les cours, TPs, rapports et projets UTC (C:/Users/jo/Documents/Academy)
- Tous les projets personnels (C:/Users/jo/Documents/Personnal_project)
Formats supportés : .md, .qmd, .tex, .pdf, .docx, .pptx, .ipynb, .py, .c, .cpp, .h, .hpp, .kt, .sci, .pl, .sql, .sh
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# Configuration des chemins racines à scanner
ROOT_DIRS = [
    Path(r"C:\Users\jo\Documents\Personnal_project\Jarvis_my_brother\joshua_profile_corpus"),
    Path(r"C:\Users\jo\Documents\Academy"),
    Path(r"C:\Users\jo\Documents\Personnal_project"),
    Path(r"C:\Users\jo\Documents\cold_turkey_blocker"),
]

DB_PATH = Path(r"C:\Users\jo\Documents\Personnal_project\Jarvis_my_brother\jarvis_brain.db")

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".venv-docs",
    "venv",
    ".gradle",
    ".kotlin",
    ".idea",
    ".claude",
    "build",
    "dist",
    "runs",
    "checkpoints",
    "__MACOSX",
    "BDD_BGES",
    "platform-tools",
    "cropped_images",
    "preprocess_image",
    "Objects",
    "objects",
}

TEXT_EXTENSIONS = {
    ".md",
    ".qmd",
    ".tex",
    ".py",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".kt",
    ".sci",
    ".pl",
    ".sql",
    ".sh",
    ".txt",
}

DOC_EXTENSIONS = {".pdf", ".docx", ".pptx", ".ipynb"}
ALL_EXTENSIONS = TEXT_EXTENSIONS | DOC_EXTENSIONS

# Fichiers de bruit à ignorer
SKIP_FILENAME_PATTERNS = (
    ".bak_",
    "tmpclaude-",
    "seen_jobs.json",
    "offres_retenues.html",
    "CMakeCache.txt",
)


def classify_path(path: Path) -> tuple[str, str]:
    """Retourne (categorie, sous_projet) à partir du chemin du fichier."""
    s = str(path).replace("\\", "/")
    s_lower = s.lower()

    if "joshua_profile_corpus" in s_lower:
        return ("0_Corpus_Verifie", path.stem)

    if "/academy/" in s_lower:
        after = s.split("/Academy/", 1)[-1] if "/Academy/" in s else s.split("/academy/", 1)[-1]
        parts = after.split("/")
        top = parts[0]
        sub = parts[1] if len(parts) > 1 else top

        if top in ("A23", "P24", "A25"):
            return (f"UTC_{top}", f"{top}_{sub.upper()}")
        if top == "rapport_TN09":
            return ("Stage_TN09_Aubay", "Rapport_TN09")
        if top in ("rapport_TN10", "TN10_project", "UTC_crap"):
            return ("Stage_TN10_Epiconcept", sub)
        if top == "UTC-academic-project":
            mapping = {
                "ETL-project": "P25_NF26_ETL_BGES",
                "Machine-learning-prediction": "P25_SY09_Machine_Learning",
                "Rapport_final": "P25_SY32_Vision_Ecocups",
                "Seven-wonder-duel-in-C": "P24_LO21_7WondersDuel_Cpp",
                "surfaces-implicites": "A25_TZ2_BMBI_Surfaces_Implicites",
            }
            return ("UTC_Projets", mapping.get(sub, sub))
        return ("UTC_Autre", top)

    if "/personnal_project/" in s_lower:
        after = (
            s.split("/Personnal_project/", 1)[-1]
            if "/Personnal_project/" in s
            else s.split("/personnal_project/", 1)[-1]
        )
        top = after.split("/")[0]
        return ("Projet_Perso", top)

    if "cold_turkey_blocker" in s_lower:
        return ("Projet_Perso", "cold_turkey_blocker")

    return ("Autre", path.parent.name)


def chunk_text_lines(text: str, max_chars: int = 1800, overlap_lines: int = 4) -> list[tuple[str, str]]:
    """Découpe un texte par blocs de lignes avec étiquette 'L10-L45'."""
    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[tuple[str, str]] = []
    start_idx = 0
    n = len(lines)

    while start_idx < n:
        cur_len = 0
        end_idx = start_idx
        while end_idx < n and (cur_len + len(lines[end_idx]) + 1 <= max_chars or end_idx == start_idx):
            cur_len += len(lines[end_idx]) + 1
            end_idx += 1

        chunk_str = "\n".join(lines[start_idx:end_idx]).strip()
        if len(chunk_str) >= 25:
            loc = f"L{start_idx + 1}-L{end_idx}"
            chunks.append((loc, chunk_str))

        if end_idx >= n:
            break
        start_idx = max(start_idx + 1, end_idx - overlap_lines)

    return chunks


def extract_pdf_chunks(path: Path, max_pages: int = 120) -> list[tuple[str, str]]:
    """Extrait le texte page par page d'un fichier PDF via PyMuPDF."""
    if fitz is None:
        return []
    chunks: list[tuple[str, str]] = []
    try:
        doc = fitz.open(str(path))
        num_pages = min(len(doc), max_pages)
        for page_idx in range(num_pages):
            text = doc[page_idx].get_text("text").strip()
            text = re.sub(r"\n{3,}", "\n\n", text)
            if len(text) >= 40:
                # Si la page est très longue, la sous-découper
                if len(text) > 2500:
                    for sub_idx, (_, sub_text) in enumerate(chunk_text_lines(text, max_chars=2000), 1):
                        chunks.append((f"p.{page_idx + 1}#{sub_idx}", sub_text))
                else:
                    chunks.append((f"p.{page_idx + 1}", text))
        doc.close()
    except Exception:
        return []
    return chunks


def extract_docx_chunks(path: Path) -> list[tuple[str, str]]:
    """Extrait le texte d'un fichier Word .docx sans dépendance externe."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                return []
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        paragraphs: list[str] = []
        for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            texts = [t.text for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
            if texts:
                paragraphs.append("".join(texts))
        full_text = "\n".join(paragraphs)
        return chunk_text_lines(full_text, max_chars=1800)
    except Exception:
        return []


def extract_pptx_chunks(path: Path) -> list[tuple[str, str]]:
    """Extrait le texte diapo par diapo d'un fichier PowerPoint .pptx."""
    chunks: list[tuple[str, str]] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            slide_files = sorted(
                [name for name in zf.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")],
                key=lambda x: int(re.search(r"slide(\d+)\.xml", x).group(1)) if re.search(r"slide(\d+)\.xml", x) else 0,
            )
            for idx, slide_name in enumerate(slide_files, 1):
                root = ET.fromstring(zf.read(slide_name))
                texts = [t.text for t in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t") if t.text]
                slide_text = "\n".join(texts).strip()
                if len(slide_text) >= 25:
                    chunks.append((f"slide {idx}", slide_text))
    except Exception:
        return []
    return chunks


def extract_ipynb_chunks(path: Path) -> list[tuple[str, str]]:
    """Extrait les cellules Markdown et Code d'un notebook Jupyter .ipynb."""
    chunks: list[tuple[str, str]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        cells = data.get("cells", [])
        for idx, cell in enumerate(cells, 1):
            ctype = cell.get("cell_type", "")
            if ctype not in ("markdown", "code"):
                continue
            source = cell.get("source", [])
            text = "".join(source) if isinstance(source, list) else str(source)
            text = text.strip()
            if len(text) >= 25:
                chunks.append((f"cell {idx} ({ctype})", text[:2500]))
    except Exception:
        return []
    return chunks


def extract_file_chunks(path: Path) -> list[tuple[str, str]]:
    """Route l'extraction selon l'extension du fichier."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_chunks(path)
    if ext == ".docx":
        return extract_docx_chunks(path)
    if ext == ".pptx":
        return extract_pptx_chunks(path)
    if ext == ".ipynb":
        return extract_ipynb_chunks(path)
    if ext in TEXT_EXTENSIONS:
        # Ignorer les fichiers texte énormes (> 1.5 Mo) qui sont souvent des dumps de données
        try:
            if path.stat().st_size > 1_500_000:
                return []
            text = path.read_text(encoding="utf-8", errors="replace")
            return chunk_text_lines(text, max_chars=1800)
        except Exception:
            return []
    return []


def iter_candidate_files(roots: Iterable[Path]) -> Iterable[Path]:
    """Parcourt récursivement les dossiers racines en filtrant le bruit."""
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Filtrer les sous-dossiers bruyants sur place
            dirnames[:] = [
                d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".venv") and not d.startswith("cmake-build")
            ]
            for fname in filenames:
                if any(pat in fname for pat in SKIP_FILENAME_PATTERNS):
                    continue
                fpath = Path(dirpath) / fname
                ext = fpath.suffix.lower()
                if ext not in ALL_EXTENSIONS:
                    continue
                resolved = fpath.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield resolved


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            category TEXT,
            project TEXT,
            ext TEXT,
            mtime REAL,
            size INTEGER,
            chunk_count INTEGER
        );
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            path,
            category,
            project,
            filename,
            loc,
            content,
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )


def build_index(force: bool = False) -> None:
    t0 = time.time()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if force:
        conn.execute("DELETE FROM files;")
        conn.execute("DELETE FROM chunks_fts;")
        conn.commit()

    existing = {
        row[0]: (row[1], row[2])
        for row in conn.execute("SELECT path, mtime, size FROM files").fetchall()
    }

    visited_paths: set[str] = set()
    added_or_updated = 0
    skipped_unchanged = 0
    total_chunks_added = 0

    for fpath in iter_candidate_files(ROOT_DIRS):
        spath = str(fpath)
        visited_paths.add(spath)
        try:
            st = fpath.stat()
        except OSError:
            continue

        if not force and spath in existing:
            old_mtime, old_size = existing[spath]
            if abs(st.st_mtime - old_mtime) < 1e-3 and st.st_size == old_size:
                skipped_unchanged += 1
                continue

        category, project = classify_path(fpath)
        chunks = extract_file_chunks(fpath)

        # Mise à jour atomique pour ce fichier
        conn.execute("DELETE FROM chunks_fts WHERE path = ?", (spath,))
        conn.execute("DELETE FROM files WHERE path = ?", (spath,))

        if chunks:
            conn.executemany(
                "INSERT INTO chunks_fts (path, category, project, filename, loc, content) VALUES (?, ?, ?, ?, ?, ?)",
                [(spath, category, project, fpath.name, loc, content) for loc, content in chunks],
            )

        conn.execute(
            "INSERT INTO files (path, category, project, ext, mtime, size, chunk_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (spath, category, project, fpath.suffix.lower(), st.st_mtime, st.st_size, len(chunks)),
        )
        added_or_updated += 1
        total_chunks_added += len(chunks)

    # Purger les fichiers supprimés ou déplacés
    stale_paths = set(existing.keys()) - visited_paths
    for stale in stale_paths:
        conn.execute("DELETE FROM chunks_fts WHERE path = ?", (stale,))
        conn.execute("DELETE FROM files WHERE path = ?", (stale,))

    conn.commit()
    total_files, total_chunks = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(chunk_count), 0) FROM files WHERE chunk_count > 0"
    ).fetchone()
    conn.close()

    elapsed = time.time() - t0
    print(f"[Jarvis Brain] Indexation terminée en {elapsed:.2f}s")
    print(f"  - Fichiers mis à jour / ajoutés : {added_or_updated} ({total_chunks_added} nouveaux blocs)")
    print(f"  - Fichiers inchangés ignorés    : {skipped_unchanged}")
    print(f"  - Fichiers obsolètes purgés     : {len(stale_paths)}")
    print(f"  - Total indexé dans la base     : {total_files} fichiers | {total_chunks} blocs consultables")
    print(f"  - Base SQLite FTS5              : {DB_PATH}")


def sanitize_fts_query(raw_query: str) -> str:
    """Transforme une requête libre en requête FTS5 robuste (OR / AND)."""
    tokens = re.findall(r"[\w\d]+", raw_query, flags=re.UNICODE)
    if not tokens:
        return '""'
    # Utiliser OR avec boost implicite BM25 pour retrouver les documents qui matchent le maximum de termes
    return " OR ".join(f'"{t}"*' for t in tokens if len(t) >= 2)


def search_brain(query: str, category: str | None = None, project: str | None = None, limit: int = 8) -> None:
    if not DB_PATH.exists():
        print("Base non trouvée. Lancement de l'indexation initiale...")
        build_index()

    conn = sqlite3.connect(DB_PATH)
    fts_query = sanitize_fts_query(query)

    sql = """
        SELECT
            path,
            category,
            project,
            filename,
            loc,
            snippet(chunks_fts, 5, '«', '»', ' … ', 48) AS snip,
            bm25(chunks_fts, 1.0, 2.0, 3.0, 4.0, 0.5, 5.0) AS score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
    """
    params: list[object] = [fts_query]

    if category:
        sql += " AND category LIKE ?"
        params.append(f"%{category}%")
    if project:
        sql += " AND project LIKE ?"
        params.append(f"%{project}%")

    # Prioriser légèrement le Corpus Vérifié (0_Corpus_Verifie)
    sql += """
        ORDER BY (CASE WHEN category = '0_Corpus_Verifie' THEN score * 1.35 ELSE score END) ASC
        LIMIT ?
    """
    params.append(limit)

    t0 = time.time()
    rows = conn.execute(sql, params).fetchall()
    dt_ms = (time.time() - t0) * 1000
    conn.close()

    print(f"=== Résultats Jarvis Brain pour : {query!r} ({len(rows)} résultats en {dt_ms:.1f} ms) ===\n")
    for idx, (path, cat, proj, fname, loc, snip, score) in enumerate(rows, 1):
        clean_snip = re.sub(r"\s+", " ", snip).strip()
        print(f"[{idx}] [{cat} | {proj}] {fname} ({loc})  [score={score:.2f}]")
        print(f"    Chemin  : {path}")
        print(f"    Extrait : {clean_snip}\n")


def show_stats() -> None:
    if not DB_PATH.exists():
        print("Base non trouvée. Exécutez `python src/jarvis_brain.py index`.")
        return

    conn = sqlite3.connect(DB_PATH)
    print("=== Statistiques Globales du Cerveau Jarvis ===")
    rows = conn.execute(
        """
        SELECT category, project, COUNT(*) as nb_files, SUM(chunk_count) as nb_chunks
        FROM files
        WHERE chunk_count > 0
        GROUP BY category, project
        ORDER BY category, nb_chunks DESC
        """
    ).fetchall()

    print(f"{'Catégorie':<24} | {'Projet / UV':<34} | {'Fichiers':>8} | {'Blocs':>8}")
    print("-" * 83)
    tot_f, tot_c = 0, 0
    for cat, proj, nf, nc in rows:
        nc = nc or 0
        tot_f += nf
        tot_c += nc
        print(f"{cat:<24} | {proj:<34} | {nf:>8} | {nc:>8}")
    print("-" * 83)
    print(f"{'TOTAL':<24} | {'':<34} | {tot_f:>8} | {tot_c:>8}")
    conn.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Jarvis Brain — Indexeur & Moteur de recherche local de Joshua")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("index", help="Indexe ou met à jour tous les dossiers de Joshua")
    p_idx.add_argument("--force", action="store_true", help="Reconstruit l'index depuis zéro")

    p_search = sub.add_parser("search", help="Recherche hybride BM25 dans tous les cours, rapports et projets")
    p_search.add_argument("query", type=str, help="Termes à rechercher")
    p_search.add_argument("--category", "-c", type=str, default=None, help="Filtrer par catégorie (ex: UTC_A23, Stage_TN10)")
    p_search.add_argument("--project", "-p", type=str, default=None, help="Filtrer par projet ou UV (ex: MT09, RO05, custos)")
    p_search.add_argument("--limit", "-n", type=int, default=8, help="Nombre de résultats à retourner")

    sub.add_parser("stats", help="Affiche la cartographie complète des connaissances indexées")

    args = parser.parse_args()
    if args.cmd == "index":
        build_index(force=args.force)
    elif args.cmd == "search":
        search_brain(args.query, category=args.category, project=args.project, limit=args.limit)
    elif args.cmd == "stats":
        show_stats()


if __name__ == "__main__":
    main()
