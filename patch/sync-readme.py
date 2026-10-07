#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════
# sync-readme.py — les README suivent-ils le CHANGELOG ?
# ═══════════════════════════════════════════════════════════════════════
# Trois dérives se sont déjà produites : une section de version absente du
# README alors que la release était publiée, des liens d'installation
# restés sur l'APK précédent, et — pire — le miroir anglais README.en.md
# resté trois releases de retard sans que rien ne crie (le script ne
# lisait que le README français). Ce script fait tenir le tout sous
# quatre règles :
#
#   1. le bloc « Télécharger/Download … / adb install -r … » de CHAQUE
#      README (FR et EN) pointe l'APK de la version la PLUS RÉCENTE du
#      CHANGELOG (URL exacte du tag) ;
#   2. chaque entrée « ## vX.Y.Z » du CHANGELOG a sa section dans le
#      README FR, SAUF si le README n'en contient plus aucune (opt-out :
#      une édition qui retire toutes les sections désactive cette règle —
#      le script ne les réimpose pas) ;
#   3. la section qui décrit la version la plus récente — « ## Nouveautés
#      v… » côté FR, « ## What's new in v… » côté EN — est possédée par
#      le script : régénérée depuis l'entrée CHANGELOG correspondante.
#      Côté français, les puces sont recopiées verbatim ; côté anglais, le
#      script ne traduit pas : la prose est déclarée une fois par release
#      dans WHATS_NEW_EN ci-dessous, et --check refuse un miroir en
#      retard, en dérive, ou sans traduction déclarée.
#   4. CHAQUE README porte UNE SEULE version : la plus récente du
#      CHANGELOG, partout — lien « Télécharger/Download », commande adb
#      et section « Nouveautés / What's new » portent exactement
#      la même. Toute occurrence résiduelle d'une autre version dans ces
#      positions possédées est un défaut (le miroir EN est resté trois
#      releases en v1.0.20 sans que rien ne crie).
#   5. rien d'autre n'est possédé : les sections historiques (prose,
#      images, reformulations) ne sont jamais réécrites — la v1.0.1 du
#      README contient par exemple une capture que le CHANGELOG n'a pas,
#      et les mentions v1.0.16 des « Fonctionnalités » sont légitimes.
#
# Mode `sync` (défaut)  : corrige les blocs de liens, insère les sections
#                         manquantes et régénère la section « Nouveautés »
#                         des deux README.
# Mode `--check`        : ne modifie rien, sort en 1 si un README dévie
#                         (utilisé par la CI).
#
# Convention : une puce de CHANGELOG commençant par « version » (ex.
# « version de maintenance… ») est une note de projet, pas une
# fonctionnalité ; elle est quand même recopiée dans la section générée.
#
# Usage :  python patch/sync-readme.py [--check]
# Sortie : 0 si les deux README concordent avec le CHANGELOG, 1 si
#          décalage, bloc d'installation manquant/corrompu (réparable en
#          réinsérant le bloc), ou traduction EN manquante en mode sync
#          (échec bruyant, rien n'est écrit) ; 2 si erreur de lecture
#          (fichiers absents…).
# ═══════════════════════════════════════════════════════════════════════
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
README_EN_PATH = ROOT / "README.en.md"
CHANGELOG_PATH = ROOT / "CHANGELOG-twouich.md"
REPO = "Endymi0n74/Twouich"

FR_LINK_SENTENCE = (
    "Télécharger [`{apk}`]({url}) depuis la release publiée."
)
EN_LINK_SENTENCE = "Download [`{apk}`]({url}) from the published release."

# Sections possessées : la première est le titre FR, la seconde le titre EN.
FR_SECTION_RE = re.compile(r"^## Nouveautés (v[0-9][\w.]*)")
EN_SECTION_RE = re.compile(r"^## What's new in (v[0-9][\w.]*)")

# Traduction anglaise de la section « Nouveautés », une entrée par release.
# Le script ne traduit pas : la prose est déclarée ICI une seule fois par
# version (au moment de la release), et le mode --check refuse un miroir
# anglais resté sans traduction — c'est le trou qui a laissé README.en.md
# glisser jusqu'en v1.0.20 pendant que le français avançait.
WHATS_NEW_EN: dict[str, list[str]] = {
    "v1.0.23": [
        "**Phone-player rotation no longer breaks the layout mid-playback.** "
        "Switching portrait → landscape keeps the video at an exact 16:9 frame "
        "(`1845×1038` in a simulated 2712×1220 screen) and ranks chat and the "
        "compose bar in a column to its right — the landscape branch is replayed "
        "with **re-measured** geometry, instead of the stale configuration "
        "`onConfigurationChanged` still found in place.",
        "**The \"Send a message\" bar rises above the keyboard.** Measured "
        "glued to the IME top edge (`y=1687` with the keyboard open up to 2712) "
        "while the chat shrinks accordingly; keyboard closed, the original "
        "portrait stacking is unchanged. With the window edge-to-edge (target "
        "35), `adjustResize` is not enough — and **IME insets report nothing on "
        "this MIUI**: the keyboard height is read via "
        "`getWindowVisibleDisplayFrame`, the only reliable source measured on "
        "the device. A layout watch (`PhoneLayoutWatch`) replays the geometry "
        "on every visible-frame change, with an anti-loop guard.",
        "No message was sent during validation; no session was lost "
        "(`adb install -r`, `firstInstallTime` preserved). Measurement details "
        "and recipes: `TEST-DEVICE.md` § 8.26.",
    ],
}

# Date de l'entrée CHANGELOG (« 6 octobre 2026 ») → « October 6, 2026 ».
MONTHS_EN = {
    "janvier": "January", "février": "February", "fevrier": "February",
    "mars": "March", "avril": "April", "mai": "May", "juin": "June",
    "juillet": "July", "août": "August", "aout": "August",
    "septembre": "September", "octobre": "October",
    "novembre": "November", "décembre": "December", "decembre": "December",
}


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
    """Entrées de premier niveau « ## vX.Y.Z — date » avec leurs puces.

    Les sous-sections « ### » et leurs puces sont ignorées : elles
    n'apparaissent que dans les notes de release majeures, rédigées à la
    main dans le README. Chaque entrée porte en plus :
      - « date » : le texte après le tiret long du titre (« 6 octobre 2026 ») ;
      - « raw_bullets » : les puces verbatim (repli markdown recollé),
        telles quelles — c'est ce que recopie la section « Nouveautés ».
    """
    entries: list[dict] = []
    current: dict | None = None
    for line in text.split("\n"):
        m = re.match(r"^## (v[0-9][\w.]*)\s*[—–-]+\s*(.*)$", line)
        if m:
            current = {
                "version": m.group(1),
                "date": m.group(2).strip(),
                "bullets": [],
                "raw_bullets": [],
            }
            entries.append(current)
        elif current is None:
            continue
        elif line.startswith("- "):
            bullet = line[2:].strip()
            current["raw_bullets"].append(bullet)
            bullet = re.sub(r"\.$", "", bullet)  # phrase CHANGELOG → puce
            current["bullets"].append(bullet)
        elif (
            current["raw_bullets"]
            and line.strip()
            and not line.startswith((">", "#"))
        ):
            # Ligne de continuation d'une puce (repli markdown) : recollée.
            cont = line.strip()
            current["raw_bullets"][-1] += " " + cont
            current["bullets"][-1] += " " + cont
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


def link_block(version: str, sentence: str) -> tuple[str, str]:
    """Le bloc de liens d'installation pour la version donnée (URL du tag)."""
    apk = f"Twouich_{version}.apk"
    url = f"https://github.com/{REPO}/releases/download/{version}/{apk}"
    return (sentence.format(apk=apk, url=url), f"adb install -r {apk}")


def fr_link_lines(version: str) -> tuple[str, str]:
    return link_block(version, FR_LINK_SENTENCE)


def en_link_lines(version: str) -> tuple[str, str]:
    return link_block(version, EN_LINK_SENTENCE)


def en_date(date_fr: str) -> str:
    """« 6 octobre 2026 » → « October 6, 2026 » (tolère « 1er »)."""
    parts = date_fr.replace("1er ", "1 ").split()
    if len(parts) == 3:
        day, month, year = parts
        return f"{MONTHS_EN.get(month.lower(), month)} {day}, {year}"
    return date_fr


def newest_section_fr(entry: dict) -> list[str]:
    """Section « Nouveautés » attendue : titre + puces CHANGELOG verbatim."""
    heading = f"## Nouveautés {entry['version']}"
    if entry["date"]:
        heading += f" — {entry['date']}"
    return [heading, ""] + [f"- {b}" for b in entry["raw_bullets"]] + [""]


def whats_new_en(entry: dict) -> list[str] | None:
    return WHATS_NEW_EN.get(entry["version"])


def newest_section_en(entry: dict) -> list[str] | None:
    """Section « What's new » attendue ; None si la traduction manque."""
    bullets = whats_new_en(entry)
    if bullets is None:
        return None
    heading = f"## What's new in {entry['version']}"
    if entry["date"]:
        heading += f" — {en_date(entry['date'])}"
    return [heading, ""] + [f"- {b}" for b in bullets] + [""]


def section_block(entry: dict, last_of_all: bool) -> list[str]:
    """Lignes d'une section README historique pour une entrée CHANGELOG.

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


def fix_link_block(
    lines: list[str], version: str, link_prefix: str, sentence: str,
    filename: str,
) -> list[str]:
    """Pointe le bloc de liens d'un README vers la version donnée.

    Le bloc possédé tolère deux formes : le bloc complet (lien + clôture
    adb), ou une ligne « Télécharger/Download … » remaniée à la main sans
    lien — la clôture adb est alors recréée. Sans aucune ligne de lien,
    le bloc est perdu : échec bruyant.
    """
    expected_link, expected_adb = link_block(version, sentence)
    link_re = re.compile(f"^{link_prefix}")
    adb_re = re.compile(r"^adb install -r Twouich_")
    link_idx = adb_idx = None
    for i, line in enumerate(lines):
        if link_re.match(line):
            link_idx = i
        elif adb_re.match(line):
            adb_idx = i
    if link_idx is None:
        raise SystemExit(
            f"❌ bloc d'installation introuvable dans {filename} ("
            f"aucune ligne « {link_prefix} … » sous « ## Installation »).\n"
            "   Réinsérer le bloc, puis relancer."
        )
    lines[link_idx] = expected_link
    if adb_idx is None:
        lines[link_idx + 1 : link_idx + 1] = [
            "", "```bash", expected_adb, "```",
        ]
    else:
        lines[adb_idx] = expected_adb
    return lines


def insert_missing_sections(
    lines: list[str], entries: list[dict]
) -> tuple[list[str], list[str]]:
    """Insère les sections manquantes au-dessus de la première existante."""
    present = set(readme_versions("\n".join(lines)))
    if not present:
        # Opt-out : une édition qui retire toutes les sections désactive la
        # règle — le script ne les réimpose pas.
        return lines, []
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


def section_span(
    lines: list[str], heading_re: re.Pattern
) -> tuple[int | None, int | None]:
    """(début, fin) de la section possessée ; fin = prochaine ligne « ## »."""
    start = next(
        (i for i, l in enumerate(lines) if heading_re.match(l)), None
    )
    if start is None:
        return None, None
    end = next(
        (
            i for i in range(start + 1, len(lines))
            if lines[i].startswith("## ")
        ),
        len(lines),
    )
    return start, end


def trimmed(lines: list[str]) -> list[str]:
    """Copie sans les lignes vides de fin (les vides internes comptent)."""
    out = list(lines)
    while out and not out[-1].strip():
        out.pop()
    return out


def upsert_newest_section(
    lines: list[str], heading_re: re.Pattern, expected: list[str],
    label: str,
) -> tuple[list[str], bool]:
    """Régénère la section possessée (heading + corps) ; la crée si absente.

    Une section présente mais d'une version antérieure est remplacée sur
    place — le README ne raconte qu'une version : la plus récente.
    """
    start, end = section_span(lines, heading_re)
    if start is not None:
        if trimmed(lines[start:end]) == trimmed(expected):
            return lines, False
        lines[start:end] = expected
        return lines, True
    # Absente : insérer au-dessus de « ## Installation ».
    inst = next(
        (i for i, l in enumerate(lines) if l.startswith("## Installation")),
        None,
    )
    if inst is None:
        raise SystemExit(
            f"❌ ni section « {label} » ni « ## Installation » dans le "
            "README : insertion impossible."
        )
    block = list(expected)
    if inst > 0 and lines[inst - 1].strip():
        block.insert(0, "")
    lines[inst:inst] = block
    return lines, True


def version_positions(lines: list[str]) -> list[tuple[int, str]]:
    """Occurrences de version dans les positions possédées d'un README.

    Trois positions : la ligne « Télécharger/Download » (version dans
    l'URL et dans le nom d'APK), la clôture « adb install -r » (nom
    d'APK) et le titre « Nouveautés / What's new ». Renvoie (index,
    version) — les versions citées dans la prose des « Fonctionnalités »
    ou des sections historiques ne sont PAS des positions possédées.
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if re.match(r"^(Télécharger|Download) ", line):
            m = re.search(r"Twouich_(v[0-9][\w.]*)\.apk", line)
            if m:
                out.append((i, m.group(1)))
            else:
                out.append((i, ""))  # ligne de lien sans APK : défectueuse
        elif re.match(r"^adb install -r ", line):
            m = re.search(r"Twouich_(v[0-9][\w.]*)\.apk", line)
            if m:
                out.append((i, m.group(1)))
            else:
                out.append((i, ""))
        else:
            m = FR_SECTION_RE.match(line) or EN_SECTION_RE.match(line)
            if m:
                out.append((i, m.group(1)))
    return out


def check(
    fr_lines: list[str], en_lines: list[str], entries: list[dict]
) -> int:
    """Mode --check : constate les écarts sur les DEUX README, ne touche à rien."""
    newest = entries[0]["version"]
    problems: list[str] = []

    # Règle 1 : blocs de liens FR et EN.
    fr_link, fr_adb = fr_link_lines(newest)
    actual_link = next((l for l in fr_lines if re.match(r"^Télécharger", l)), None)
    if actual_link is None:
        problems.append("README.md : bloc d'installation introuvable (ligne « Télécharger … »)")
    elif actual_link != fr_link:
        problems.append(
            f"README.md : lien d'installation « {actual_link[:70]}… » au lieu de "
            f"« {fr_link[:70]}… »"
        )
    actual_adb = next(
        (l for l in fr_lines if re.match(r"^adb install -r Twouich_", l)), None
    )
    if actual_adb is None:
        problems.append("README.md : commande « adb install -r » introuvable")
    elif actual_adb != fr_adb:
        problems.append(f"README.md : « {actual_adb} » au lieu de « {fr_adb} »")

    en_link, en_adb = en_link_lines(newest)
    actual_link_en = next((l for l in en_lines if re.match(r"^Download ", l)), None)
    if actual_link_en is None:
        problems.append("README.en.md : bloc d'installation introuvable (ligne « Download … »)")
    elif actual_link_en != en_link:
        problems.append(
            f"README.en.md : lien d'installation « {actual_link_en[:70]}… » au lieu de "
            f"« {en_link[:70]}… »"
        )
    actual_adb_en = next(
        (l for l in en_lines if re.match(r"^adb install -r Twouich_", l)), None
    )
    if actual_adb_en is None:
        problems.append("README.en.md : commande « adb install -r » introuvable")
    elif actual_adb_en != en_adb:
        problems.append(f"README.en.md : « {actual_adb_en} » au lieu de « {en_adb} »")

    # Règle 2 : sections de version historiques (opt-out inchangé).
    present = set(readme_versions("\n".join(fr_lines)))
    absent = [e["version"] for e in entries if e["version"] not in present]
    if absent and present:
        problems.append(
            "sections de version absentes du README : " + ", ".join(absent)
        )

    # Règle 3 : section « Nouveautés » courante, FR puis EN.
    s, e = section_span(fr_lines, FR_SECTION_RE)
    if s is None:
        problems.append(f"README.md : section « Nouveautés » absente (attendue pour {newest})")
    else:
        carried = FR_SECTION_RE.match(fr_lines[s]).group(1)
        if carried != newest:
            problems.append(
                f"README.md : « Nouveautés » porte {carried} au lieu de {newest}"
            )
        elif trimmed(fr_lines[s:e]) != trimmed(newest_section_fr(entries[0])):
            problems.append(
                "README.md : le corps de « Nouveautés » ne correspond pas à "
                "l'entrée CHANGELOG"
            )

    en_expected = newest_section_en(entries[0])
    if en_expected is None:
        problems.append(
            f"README.en.md : traduction EN absente pour {newest} "
            f'(ajouter WHATS_NEW_EN["{newest}"] dans patch/sync-readme.py)'
        )
    else:
        s, e = section_span(en_lines, EN_SECTION_RE)
        if s is None:
            problems.append(
                f"README.en.md : section « What's new » absente (attendue pour {newest})"
            )
        else:
            carried = EN_SECTION_RE.match(en_lines[s]).group(1)
            if carried != newest:
                problems.append(
                    f"README.en.md : « What's new » porte {carried} au lieu de {newest}"
                )
            elif trimmed(en_lines[s:e]) != trimmed(en_expected):
                problems.append(
                    "README.en.md : le corps de « What's new » ne correspond pas "
                    "à la traduction déclarée"
                )

    # Règle 4 : UNE SEULE version par README — toute occurrence d'une
    # autre version dans une position possédée est un défaut.
    for name, lines_ in (("README.md", fr_lines), ("README.en.md", en_lines)):
        for _, v in version_positions(lines_):
            if v != newest:
                problems.append(
                    f"{name} : version « {v or 'illisible'} » dans une position "
                    f"possédée au lieu de {newest} (une seule version par README)"
                )

    if problems:
        print("❌ README désynchronisé du CHANGELOG :")
        for p in problems:
            print(f"   - {p}")
        print("   → lancer : python patch/sync-readme.py")
        return 1

    print(f"✔ README (FR et EN) alignés sur le CHANGELOG ({newest})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise les README FR et EN (liens d'installation, "
        "sections de version et section « Nouveautés ») avec "
        "CHANGELOG-twouich.md."
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

    fr_readme, fr_eol = read_text(README_PATH)
    en_readme, en_eol = read_text(README_EN_PATH)
    changelog, _ = read_text(CHANGELOG_PATH)
    entries = parse_changelog(changelog)

    if args.check:
        return check(fr_readme.split("\n"), en_readme.split("\n"), entries)

    newest = entries[0]["version"]
    fr_lines = fr_readme.split("\n")
    en_lines = en_readme.split("\n")

    # La traduction EN doit exister AVANT toute écriture : on échoue bruyant
    # plutôt que de poser du français dans le miroir anglais.
    if whats_new_en(entries[0]) is None:
        raise SystemExit(
            f"❌ traduction EN manquante pour {newest} : ajouter "
            f'WHATS_NEW_EN["{newest}"] dans patch/sync-readme.py, puis relancer.'
        )
    expected_fr = newest_section_fr(entries[0])
    expected_en = newest_section_en(entries[0])

    fr_lines = fix_link_block(
        fr_lines, newest, "Télécharger", FR_LINK_SENTENCE, "README.md"
    )
    en_lines = fix_link_block(
        en_lines, newest, "Download", EN_LINK_SENTENCE, "README.en.md"
    )
    fr_lines, inserted = insert_missing_sections(fr_lines, entries)
    fr_lines, fr_changed = upsert_newest_section(
        fr_lines, FR_SECTION_RE, expected_fr, "Nouveautés"
    )
    en_lines, en_changed = upsert_newest_section(
        en_lines, EN_SECTION_RE, expected_en, "What's new"
    )

    fr_result = "\n".join(fr_lines)
    en_result = "\n".join(en_lines)
    if fr_result != fr_readme:
        write_text(README_PATH, fr_result, fr_eol)
    if en_result != en_readme:
        write_text(README_EN_PATH, en_result, en_eol)

    if inserted:
        print(
            f"✔ sections insérées : {', '.join(inserted)} ; "
            f"liens pointés vers {newest}"
        )
    else:
        print(f"✔ liens pointés vers {newest} (aucune section manquante)")
    if fr_changed and en_changed:
        print("✔ sections « Nouveautés » régénérées (FR et EN)")
    elif fr_changed:
        print("✔ section « Nouveautés » régénérée (FR)")
    elif en_changed:
        print("✔ section « What's new » régénérée (EN)")
    else:
        print("✔ sections « Nouveautés » déjà à jour (FR et EN)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
