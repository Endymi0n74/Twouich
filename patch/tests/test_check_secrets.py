#!/usr/bin/env python3
"""
test_check_secrets.py — verifie patch/check-secrets.py (hors reseau, hors appareil).

Un garde-fou qu'on ne prouve pas mordant ne garde rien. Ce test etablit trois
choses :

  1. **il ne crie pas au loup** : le depot reel passe, et les fichiers du
     garde-fou lui-meme ne declenchent aucune de ses regles ;
  2. **il mord sur chaque regle** : dix valeurs factices, une par regle, plantees
     dans un corpus : chacune est trouvee, une seule fois, sous le bon nom ;
  3. **il reste honnete sur ses limites** : l'exception `secret-scan: ok` fait
     taire la ligne qu'elle vise **et aucune autre**, la valeur trouvee est
     **masquee** dans le rapport (jamais recopiee), un fichier binaire est
     ignore, et un secret **assemble a l'execution** lui echappe — la technique
     qu'emploient `test_apk.py` et le garde-fou lui-meme. Cette limite est
     ecrite dans l'en-tete du scanner ; elle est verifiee ici pour qu'elle reste
     volontaire et non accidentelle.

Les valeurs factices sont construites a l'execution (`_fp` = fragments) : ce
fichier, versionne, ne contient donc aucun litteral qui ressemble a un secret,
et il est scanne comme les autres.

Usage :  python patch/tests/test_check_secrets.py
Sortie : 0 si toutes les verifications passent, 1 sinon.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCANNER = ROOT / "patch" / "check-secrets.py"

FAILED = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAILED
    if ok:
        print(f"  ✅ {label}")
    else:
        FAILED += 1
        print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))


def _fp(*parts: str) -> str:
    """Assemble une valeur factice sans jamais l'ecrire en clair ici."""
    return "".join(parts)


# ── Les dix regles, chacune avec une valeur factice -------------------------------------------------
FAKE = {
    "cle d'API Google": _fp("A", "Iza", "SyD") + ("TwouichFake" + "0" * 24),
    "identifiant Firebase": _fp("1:", "123456789012", ":android:", "0abcdef1234567890"),
    "URL de base Firebase": _fp("https://", "exemple-factice", ".firebase", "io.com"),
    "cle privee PEM": _fp("-" * 5, "BEGIN RSA PRIVATE KEY", "-" * 5),
    "jeton GitHub": _fp("gh", "p_") + "Z" * 40,
    "jeton Slack": _fp("xo", "xb-", "1234567890abcdef"),
    "cle AWS": _fp("AK", "IA", "ABCDEFGHIJKLMNOP"),
    "cle Stripe live": _fp("sk_", "live_", "abcdefghijklmnopqrstuvwx"),
    "jeton d'autorisation": 'authorization = "' + _fp("oau", "th:", "abcdefghijklmnopqrstuvwx") + '"',
    "litteral de secret": _fp("api", "_key", ' = "Twouich') + "Y" * 12 + '"',
}

# Lignes inoffentes : elles ressemblent de loin a un secret et ne doivent RIEN
# declencher. C'est la specificite du scanner, pas seulement sa sensibilite.
INNOCENT = (
    'KEY_PASS="${KEY_PASS:-}"',
    "password = os.environ.get('TWOUICH_KEY')",
    "api_key = require_secret()",
    "authorization = get_token()",
    "set token variable",
    "https://exemple.invalid/page",
    "1:1:android:x",
)


def load_scanner():
    spec = importlib.util.spec_from_file_location("check_secrets", SCANNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(*args: str, cwd: pathlib.Path | None = None) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable, str(SCANNER), *args], cwd=str(cwd or ROOT),
                          capture_output=True, env=env)
    return done.returncode, done.stdout.decode("utf-8", "replace")


def main() -> int:
    scanner = load_scanner()

    # ── 1. Il ne crie pas au loup ────────────────────────────────────────
    print("1. Le depot reel est propre (et le garde-fou ne se denonce pas lui-meme)")
    code, out = run_cli("--quiet")
    check("depot reel : exit 0", code == 0, f"exit {code} — {out.strip()[:120]}")
    own = [p for p in (SCANNER, pathlib.Path(__file__)) if p.is_file()]
    bare = [str(p.relative_to(ROOT)) for p in own if scanner.scan_file(p)]
    check("la source du garde-fou et celle de ce test ne declenchent aucune regle",
          not bare, ", ".join(bare))
    tracked = [str(p) for p in own if p.is_file()]
    check("les deux fichiers sont bien versionnes", len(tracked) == 2)
    check("le scan du depot a bien lu des fichiers",
          (lambda t: len(t) > 50 if t else False)(scanner.tracked_files(ROOT)))

    # ── 2. Il mord, regle par regle ──────────────────────────────────────
    print("\n2. Chaque regle mord sur sa valeur factice")
    corpus = "\n".join(FAKE[name] for name in FAKE) + "\n"
    findings = scanner.scan_text(corpus)
    found_rules = [rule for _, rule, _ in findings]
    for name in FAKE:
        check(f"{name} : trouvee une fois",
              found_rules.count(name) == 1, f"trouvée {found_rules.count(name)} fois")
    check("aucune regle ne deborde sur une autre ligne", len(findings) == len(FAKE),
          f"{len(findings)} trouvaille(s) pour {len(FAKE)} valeur(s)")

    print("\n2b. Les lignes inoffentes ne declenchent rien")
    innocent = scanner.scan_text("\n".join(INNOCENT) + "\n")
    check("aucune trouvaille sur les sept lignes inoffentes", not innocent,
          "; ".join(f"{rule} ({line})" for line, rule, _ in innocent))

    # ── 3. Il reste honnete sur ses limites ──────────────────────────────
    print("\n3. Masquage, exceptions et limites")
    value = FAKE["cle AWS"]
    masked = scanner.scan_text(f"trouve {value} ici")[0][2]
    check("la valeur est masquee dans le rapport", value not in masked, masked)
    check("le masque dit la longueur exacte", str(len(value)) in masked, masked)

    # Valeur neutre : elle ne declenche que la regle des etiquettes, ce qui
    # isole l'effet de l'exception (une cle AWS, elle, en declencherait deux).
    plain = _fp("Twouich", "FakeValue", "0" * 6)
    planted = f'api_key = "{plain}"'
    excuse_line = planted + "  secret-scan: ok aiguille de test"
    above_line = f"# secret-scan: ok aiguille de test\n{planted}"
    two_above = f"# secret-scan: ok aiguille de test\n# commentaire\n{planted}"
    check("la ligne plante mord sans exception", len(scanner.scan_text(planted)) == 1)
    check("exception sur la meme ligne : silence", not scanner.scan_text(excuse_line))
    check("exception sur la ligne precedente : silence", not scanner.scan_text(above_line))
    check("exception deux lignes plus haut : le scanner mord toujours",
          len(scanner.scan_text(two_above)) == 1)
    check("l'exception ne fait taire que la ligne qu'elle couvre",
          not scanner.scan_text(above_line + "\n" + excuse_line)
          and len(scanner.scan_text("# secret-scan: ok aiguille\n" + corpus)) == len(FAKE) - 1)

    assembled = _fp("A", "Iza", "SyD") + ("Fake" + "0" * 24)
    check("limite assumee : une valeur assemblee a l'execution echappe au scanner",
          not scanner.scan_text(f'cle = "{assembled}"'))

    # ── 4. Le comportement de la ligne de commande ──────────────────────
    print("\n4. Ligne de commande")
    with tempfile.TemporaryDirectory() as tmp:
        tree = pathlib.Path(tmp)
        (tree / "propre.txt").write_text("rien a signaler\n", encoding="utf-8")
        (tree / "fake.bin").write_bytes(b"\x00\x01" + FAKE["cle AWS"].encode() + b"\x00")
        code_ok, _ = run_cli("--path", str(tree), "--quiet")
        check("arbre propre (et binaire ignore) : exit 0", code_ok == 0)

        (tree / "fuite.cfg").write_text(f"aws = {FAKE['cle AWS']}\n", encoding="utf-8")
        code_ko, report = run_cli("--path", str(tree))
        check("arbre avec un secret plante : exit 1", code_ko == 1, f"exit {code_ko}")
        check("le rapport nomme le fichier, la ligne et la regle",
              "fuite.cfg:1" in report and "[cle AWS]" in report)
        check("le rapport ne recopie jamais la valeur", FAKE["cle AWS"] not in report)
        code_quiet, quiet = run_cli("--path", str(tree), "--quiet")
        check("--quiet : en-tete supprime, trouvaille et verdict conserves",
              code_quiet == 1 and "check-secrets —" not in quiet
              and "fuite.cfg" in quiet)

        code_usage, _ = run_cli("--path", str(tree / "absent"), "--quiet")
        check("chemin introuvable : exit 2 (erreur d'usage)", code_usage == 2)
        code_staged, _ = run_cli("--staged", "--quiet", "--path", str(tree))
        check("--staged hors depot git : exit 2", code_staged == 2)

    code_staged_here, _ = run_cli("--staged", "--quiet")
    check("--staged dans le depot : exit 0 (index propre)", code_staged_here == 0)

    print()
    if FAILED:
        print(f"❌ verdict : {FAILED} verification(s) en echec")
        return 1
    print("✅ verdict : garde-fou conforme — il mord sur les dix regles, "
          "laisse passer les lignes inoffentes et dit ses limites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
