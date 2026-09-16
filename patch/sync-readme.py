#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════
# sync-readme.py — le README suit-il le CHANGELOG ?
# ═══════════════════════════════════════════════════════════════════════
# Deux dérives se sont déjà produites : une section de version absente du
# README alors que la release était publiée, et des liens d'installation
# restés sur l'APK précédent. Ce script fait tenir les deux sous une règle :
#
#   1. le bloc « Télécharger … / adb install -r … » pointe l'APK de la
#      version la PLUS RÉCENTE du CHANGELOG (URL exacte du tag) ;
#   2. chaque entrée « ## vX.Y.Z » du CHANGELOG a sa section dans le README.
#
# Mode `sync` (défaut)  : corrige le bloc de liens et insère les sections
#                         manquantes au-dessus de la première existante.
# Mode `--check`        : ne modifie rien, sort en 1 si le README dévie
#                         (utilisé par la CI).
#
# Le script ne possède RIEN d'autre : les sections existantes (prose,
# images, reformulations) ne sont jamais réécrites — la v1.0.1 du README
# contient par exemple une capture que le CHANGELOG n'a pas.
#
# Convention : une puce de CHANGELOG commençant par « version » (ex.
# « version de maintenance… ») est une note de projet, pas une
# fonctionnalité ; elle est quand même recopiée dans la section générée.
#
# Usage :  python patch/sync-readme.py [--check]
# Sortie : 0 si README et CHANGELOG concordent, 1 si décalage ou bloc
#          d'installation manquant/corrompu (réparable en réinsérant le
#          bloc), 2 si erreur de lecture (fichiers absents…).
# ═══════════════════════════════════════════════════════════════════════
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
CHANGELOG_PATH = ROOT / "CHANGELOG-twouich.md"
REPO = "Endymi0n74/Twouich"


def read_text(path: Path) -> tuple[str, str]:
    """Retourne (texte normalisé \n, EOL d'origine) en préservant les CRLF."""
    if not path.exists():
        print(f"❌ fichier introuvable : {path}", file=sys.stderr)
        raise SystemExit(2)
    raw = path.read_text(encoding="utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), eol


def write_text(path: Path, text: str, eol: str) -> None:
    if eol == "\r\n":
        text = text.replace("\n", "\r\n")
    path.write_text(text, encoding="utf-8", newline="")


def parse_changelog(text: str) -> list[dict]:
    """Entrées de premier niveau « ## vX.Y.Z » avec leurs puces directes.

    Les sous-sections « ### » et leurs puces sont ignorées : elles
    n'apparaissent que dans les notes de release majeures, rédigées à la
    main dans le README.
    """
    entries: list[dict] = []
    current: dict | None = None
    for line in text.split("\n"):
        m = re.match(r"^## (v[0-9][\w.]*)", line)
        if m:
            current = {"version": m.group(1), "bullets": []}
            entries.append(current)
        elif current is not None and line.startswith("- "):
            bullet = line[2:].strip()
            bullet = re.sub(r"\.$", "", bullet)  # phrase CHANGELOG → puce
            current["bullets"].append(bullet)
    if not entries:
        raise SystemExit(
            f"❌ aucune entrée « ## vX.Y.Z » trouvée dans {CHANGELOG_PATH.name}"
        )
    return entries


def normalize(s: str) -> str:
    """Clé de comparaison insensible à la ponctuation finale et à la casse."""
    return re.sub(r"\s+", " ", s.strip().rstrip(".;:").lower())


def is_note_projet(bullet: str) -> bool:
    return bool(re.match(r"^version[\s:]", normalize(bullet)))


def link_lines(version: str) -> tuple[str, str]:
    """Le bloc de liens d'installation pour la version donnée (URL du tag)."""
    apk = f"Twouich_{version}.apk"
    return (
        f"Télécharger [`{apk}`](https://github.com/{REPO}/releases/download/"
        f"{version}/{apk}) depuis la release publiée.",
        f"adb install -r {apk}",
    )


def section_block(entry: dict, last_of_all: bool) -> list[str]:
    """Lignes d'une section README pour une entrée CHANGELOG.

    Ponctuation du README : « ; » entre les puces, « . » pour la dernière
    puce de la dernière section — sauf les notes de projet, qui gardent le
    point final du CHANGELOG.
    """
    lines = [f"## {entry['version']}", ""]
    n = len(entry["bullets"])
    for i, bullet in enumerate(entry["bullets"]):
        if is_note_projet(bullet):
            lines.append(f"- {bullet}.")
        elif last_of_all and i == n - 1:
            lines.append(f"- {bullet}.")
        else:
            lines.append(f"- {bullet} ;")
    lines.append("")
    return lines


def readme_versions(text: str) -> list[str]:
    return re.findall(r"^## (v[0-9][\w.]*)", text, flags=re.M)


def fix_link_block(lines: list[str], version: str) -> list[str]:
    """Remplace les deux lignes du bloc de liens par leur forme attendue."""
    expected_link, expected_adb = link_lines(version)
    link_idx = adb_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^Télécharger \[`Twouich_", line):
            link_idx = i
        elif re.match(r"^adb install -r Twouich_", line):
            adb_idx = i
    if link_idx is None or adb_idx is None:
        missing = []
        if link_idx is None:
            missing.append("ligne « Télécharger [`Twouich_…") 
        if adb_idx is None:
            missing.append("ligne « adb install -r Twouich_… »")
        raise SystemExit(
            "❌ bloc d'installation introuvable dans README.md ("
            + " et ".join(missing)
            + ").\n   Réinsérer le bloc sous « ## Installation », puis relancer."
        )
    lines[link_idx] = expected_link
    lines[adb_idx] = expected_adb
    return lines


def insert_missing_sections(
    lines: list[str], entries: list[dict]
) -> tuple[list[str], list[str]]:
    """Insère les sections manquantes au-dessus de la première existante."""
    present = set(readme_versions("\n".join(lines)))
    missing = [e for e in entries if e["version"] not in present]
    if not missing:
        return lines, []

    first_section_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^## v[0-9]", line):
            first_section_idx = i
            break
    if first_section_idx is None:
        for i, line in enumerate(lines):
            if line.startswith("## Installation"):
                first_section_idx = i
                break
    if first_section_idx is None:
        raise SystemExit(
            "❌ ni section de version ni « ## Installation » dans README.md : "
            "impossible de savoir où insérer les sections."
        )

    block: list[str] = []
    for e in missing:
        block.extend(section_block(e, last_of_all=False))
    block.append(f"Les notes des versions précédentes sont conservées ci-dessous.")
    block.append("")

    merged = lines[:first_section_idx] + block + lines[first_section_idx:]
    merged = re.sub(r"\n{3,}", "\n\n", "\n".join(merged)).split("\n")
    return merged, [e["version"] for e in missing]


def check(lines: list[str], entries: list[dict]) -> int:
    """Mode --check : constate les écarts, ne modifie rien."""
    newest = entries[0]["version"]
    expected_link, expected_adb = link_lines(newest)
    problems: list[str] = []

    actual_link = next(
        (l for l in lines if re.match(r"^Télécharger \[`Twouich_", l)), None
    )
    if actual_link is None:
        problems.append("bloc d'installation introuvable (ligne « Télécharger … »)")
    elif actual_link != expected_link:
        problems.append(
            f"lien d'installation pointe « {actual_link[:80]}… » au lieu de "
            f"« {expected_link[:80]}… »"
        )

    actual_adb = next(
        (l for l in lines if re.match(r"^adb install -r Twouich_", l)), None
    )
    if actual_adb is None:
        problems.append("commande « adb install -r » introuvable")
    elif actual_adb != expected_adb:
        problems.append(f"« {actual_adb} » au lieu de « {expected_adb} »")

    present = set(readme_versions("\n".join(lines)))
    absent = [e["version"] for e in entries if e["version"] not in present]
    if absent:
        problems.append(
            "sections de version absentes du README : " + ", ".join(absent)
        )

    if problems:
        print("❌ README désynchronisé du CHANGELOG :")
        for p in problems:
            print(f"   - {p}")
        print("   → lancer : python patch/sync-readme.py")
        return 1

    print(f"✔ README aligné sur le CHANGELOG ({newest})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise le README (liens d'installation et sections "
        "de version) avec CHANGELOG-twouich.md."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="vérifier sans modifier (utilisé en CI) ; sort en 1 si décalage",
    )
    args = parser.parse_args()

    # Console Windows en cp1252 : les symboles ✔/❌ exigent de l'UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    readme, readme_eol = read_text(README_PATH)
    changelog, _ = read_text(CHANGELOG_PATH)
    entries = parse_changelog(changelog)
    lines = readme.split("\n")

    if args.check:
        return check(lines, entries)

    newest = entries[0]["version"]
    lines = fix_link_block(lines, newest)
    lines, inserted = insert_missing_sections(lines, entries)
    result = "\n".join(lines)
    if result != readme:
        write_text(README_PATH, result, readme_eol)
    if inserted:
        print(
            f"✔ sections insérées : {', '.join(inserted)} ; "
            f"liens pointés vers {newest}"
        )
    else:
        print(f"✔ liens pointés vers {newest} (aucune section manquante)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
