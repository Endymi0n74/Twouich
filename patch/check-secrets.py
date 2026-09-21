#!/usr/bin/env python3
"""
check-secrets.py -- aucun secret en clair dans le depot.

Le 21/09, GitHub a signale une fuite : les identifiants Firebase du projet
d'amont etaient ecrits **en clair** dans `patch/tests/test_apk.py`, ou ils
servaient d'aiguilles de controle. Corriger le fichier ne suffisait pas : rien
n'empechait la meme chose d'arriver au commit suivant. Ce garde-fou rend la
regle executable, en local comme en CI.

Ce qu'il cherche, dans les fichiers **suivis par git** (jamais dans `.git`, ni
dans les artefacts ignores) :

  * cle d'API Google (celle des projets Firebase/web) ;
  * identifiant d'application Firebase (`1:<projet>:android:<hash>`) ;
  * URL de base Firebase (`.firebaseio.com`, `.firebasedatabase.app`) ;
  * bloc de cle privee PEM ;
  * jetons GitHub (`ghp_`, `gho_`, ...), Slack (`xox...`), cle AWS (`AKIA...`),
    cle Stripe live (`sk_live_...`) ;
  * jeton d'autorisation en clair (`oauth:...`, `bearer ...`) ;
  * tout litteral affecte a un nom qui sent le secret (`api_key`, `client_secret`,
    `password`, `access_token`, ...).

**Les valeurs trouvees sont masquees dans le rapport** (prefixe + longueur) :
de quoi retrouver la ligne, sans republier le secret dans la console de CI.

Faux positifs : une regle peut etre ecartee en connaissance de cause par un
commentaire `secret-scan: ok <raison>`, sur la meme ligne que le litteral ou sur
la ligne precedente. L'exception est alors lisible dans le diff — c'est le but.

Limite assumee : un secret **assemble a l'execution** (`"AI" + "za" + ...`)
echappe au scanner. C'est exactement la technique employee par
`patch/tests/test_apk.py` pour garder ses aiguilles sans publier la cle ; ce
garde-fou rattrape l'etourderie, il ne remplace pas le jugement.

Codes de sortie :
    0 : aucun litteral suspect (hors exceptions declarees) ;
    1 : au moins un litteral suspect — detail masque sur stdout ;
    2 : erreur d'usage (chemin introuvable, git absent en mode index).

Usage :
    python patch/check-secrets.py                  # fichiers suivis par git
    python patch/check-secrets.py --path DIR       # un arbre quelconque
    python patch/check-secrets.py --staged         # l'index (hook pre-commit)
    python patch/check-secrets.py --quiet          # verdict seul
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Les 4 premiers caracteres d'une valeur masquee suffisent a retrouver la ligne
# dans son fichier, sans recopier le secret.
MASK_PREFIX = 4


def _f(*parts: str) -> str:
    """Eclate le prefixe d'une valeur cherchee (meme geste que les aiguilles de
    `patch/tests/test_apk.py`, dont le depot vient justement d'etre signale).
    Un prefixe seul n'est pas un secret : c'est une precaution, pour que ce
    fichier ne devienne pas lui-meme un exemple a copier.
    """
    return "".join(parts)


# Etiquettes d'un litteral affecte a un nom qui sent le secret.
SECRET_LABELS = "|".join((
    "secret", "passwd", "password", "passphrase",
    "api[_\\-]?key", "api[_\\-]?token", "client[_\\-]?secret",
    "access[_\\-]?token", "refresh[_\\-]?token", "auth[_\\-]?token",
    "private[_\\-]?key", "bearer[_\\-]?token",
))

# (nom lisible, motif) — l'ordre fixe celui du rapport.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cle d'API Google", re.compile(_f("A", "Iza") + r"[0-9A-Za-z_\-]{35}")),
    ("identifiant Firebase",
     re.compile(r"\b1:[0-9]{6,}:(?:android|web|ios):[0-9a-f]{6,}\b")),
    ("URL de base Firebase",
     re.compile(r"\b[a-z0-9][a-z0-9-]{2,}\.firebase(?:io\.com|database\.app)\b")),
    ("cle privee PEM", re.compile(r"-{5}BEGIN [A-Z ]{0,20}PRIVATE KEY-{5}")),
    ("jeton GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("jeton Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("cle AWS", re.compile(r"\bAK" + r"IA[0-9A-Z]{16}\b")),
    ("cle Stripe live", re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b")),
    ("jeton d'autorisation",
     re.compile(r"[\s:=\"'](?:oauth|bearer)[\s:=\"']{1,4}[A-Za-z0-9_\-]{20,}", re.I)),
    ("litteral de secret",
     re.compile(r"(?i)\b(?:" + SECRET_LABELS + r")\b\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']")),
)

# Marqueur d'exception, sur la ligne ou celle d'avant.
EXCUSE = re.compile(r"secret-scan:\s*ok\b", re.I)

# Sous-arbres jamais parcourus en mode `--path` (artefacts de build, outils
# telecharges, caches). En mode git, c'est l'index qui decide.
SKIP_DIRS = {".git", "work", "dist", "tools", "__pycache__", ".gradle", "keys"}
MAX_BYTES = 4 * 1024 * 1024


def mask(value: str) -> str:
    """Prefixe + longueur : de quoi trouver la ligne sans republier la valeur."""
    head = value[:MASK_PREFIX]
    return f"{head}… ({len(value)} caracteres)"


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """Lignes suspectes d'un texte : (numero de ligne, regle, valeur masquee)."""
    found: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        if EXCUSE.search(line) or (number > 1 and EXCUSE.search(lines[number - 2])):
            continue
        for rule, pattern in RULES:
            for match in pattern.finditer(line):
                found.append((number, rule, mask(match.group(0))))
    return found


def scan_file(path: pathlib.Path) -> list[tuple[int, str, str]]:
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    if len(raw) > MAX_BYTES or b"\x00" in raw[:4096]:
        return []  # binaire ou trop gros : pas de litteral de texte a y lire
    return scan_text(raw.decode("utf-8", errors="replace"))


def tracked_files(root: pathlib.Path) -> list[pathlib.Path] | None:
    """Fichiers de l'index git ; None si git ne repond pas ici."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [root / name for name in out.decode("utf-8", "replace").split("\0") if name]


def staged_files(root: pathlib.Path) -> list[pathlib.Path] | None:
    """Fichiers modifies dans l'index (ajoutes, copies, modifies, renommes)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--name-only", "-z",
             "--diff-filter=ACMR"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [root / name for name in out.decode("utf-8", "replace").split("\0") if name]


def walk(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refuse tout litteral ressemblant a un secret dans le depot.",
    )
    parser.add_argument("--path", default=None,
                        help="arbre a scanner (defaut : depot, fichiers suivis par git)")
    parser.add_argument("--staged", action="store_true",
                        help="ne scanner que ce qui est dans l'index (hook pre-commit)")
    parser.add_argument("--quiet", action="store_true",
                        help="verdict seul, sans l'entete")
    args = parser.parse_args()

    root = pathlib.Path(args.path).resolve() if args.path else ROOT
    if not root.is_dir():
        print(f"❌ {root} n'est pas un dossier", file=sys.stderr)
        return 2

    if args.staged:
        files = staged_files(root)
        if files is None:
            print("❌ git absent ou hors depot : --staged impossible", file=sys.stderr)
            return 2
        scope = "index git (fichiers prets a commiter)"
    elif args.path:
        files = walk(root)
        scope = f"arbre {root}"
    else:
        files = tracked_files(root)
        if files is None:
            files = walk(root)
            scope = f"arbre {root} (git absent)"
        else:
            scope = "fichiers suivis par git"

    findings: list[tuple[str, int, str, str]] = []
    for path in files:
        try:
            shown = path.relative_to(root).as_posix()
        except ValueError:
            shown = str(path)
        for number, rule, value in scan_file(path):
            findings.append((shown, number, rule, value))

    if not args.quiet:
        print("═" * 71)
        print("  check-secrets — aucun secret en clair dans le depot")
        print("═" * 71)
        print(f"  {len(files)} fichier(s) — {scope} — {len(RULES)} regle(s)")
        print()

    if not findings:
        print(f"✅ aucun secret en clair ({len(files)} fichier(s), {len(RULES)} regles)")
        return 0

    for shown, number, rule, value in findings:
        print(f"❌ {shown}:{number}  [{rule}]  {value}")
    print()
    print(f"❌ {len(findings)} litteral(aux) suspect(s) — une valeur a retirer du depot.")
    print("   Sortie : variable d'environnement, secret GitHub, ou fragments")
    print("   reassembles a l'execution (cf. FIREBASE_TRACE). Si la valeur n'en est")
    print("   pas une, declare-le en clair :  secret-scan: ok <raison>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
