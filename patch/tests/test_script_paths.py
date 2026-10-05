#!/usr/bin/env python3
"""
test_script_paths.py — aucun script ne doit dépendre du répertoire courant.

Pourquoi ce test existe
-----------------------
Le 05/10/2026, pendant la publication de la v1.0.18, une écriture annoncée comme
réussie s'est retrouvée dans le mauvais répertoire : le chemin avait été résolu
depuis la racine du workspace (`D:\Codex`) et non depuis le dépôt. Aucun code
n'avait échoué, aucun message d'erreur — le fichier visé par le projet était
resté intact pendant qu'un jumeau hors sujet apparaissait à côté. Le défaut n'a
été vu que parce qu'un **test** avait relu le fichier.

Ce test fixe la propriété générale qui rend ce genre d'accident possible :
**un script ne doit jamais dépendre du répertoire courant de celui qui
l'appelle.** Il est donc soit ancré, soit il ne prend ses chemins que dans ses
arguments.

Les trois règles
----------------
R1 « racine morte » — un script qui *calcule* sa racine depuis sa propre
    localisation doit s'en servir. Une racine calculée puis jamais lue promet un
    ancrage qu'elle n'assure pas : c'est une faute que rien d'autre ne voit.
    (Le 05/10, `device-ui.sh` calculait `ROOT` depuis `BASH_SOURCE` et ne
    l'utilisait nulle part.)

R2 « littéral non ancré » — un littéral de chemin du dépôt (`work/`, `dist/`,
    `keys/`, `tools/`, `patch/`) cité **hors guillemets** est un chemin que le
    shell résout depuis le répertoire courant. Un script qui en contient un doit
    être ancré. Hors guillemets, parce que dans une chaîne c'est du texte affiché
    à l'utilisateur, pas un chemin : `echo "usage: bash patch/device-ui.sh …"`
    n'a rien à voir avec une ouverture de fichier.

R3 « python non ancré » — même règle côté Python, sur le code **exécutable** :
    commentaires et docstrings sont retirés (via `ast` + `tokenize`), et un
    littéral de chemin dans du vrai code exige `__file__`. Pas d'échappement
    « j'utilise argparse » : importer `argparse` ne rend pas un script insensible
    au répertoire courant.

R4 « preuve comportementale » — les règles ci-dessus sont de l'analyse statique,
    donc faillibles : un guards qui ne sait que compter des chaînes ne prouve
    rien. R4 **exécute** les scripts jouables depuis un répertoire étranger et
    exige la sortie 0. C'est cette partie qui attrape ce que l'analyse laisse
    passer.

Limites assumées
----------------
R4 ne rejoue que ce qui ne demande ni appareil, ni build, ni réseau — les
scripts lents ou matériels (`test_device_ui.sh`, `test_brand.py`, `build.sh`,
`device-ui.sh`) restent couverts par la seule analyse statique.
"""
from __future__ import annotations

import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patch"

# Un chemin du dépôt. L'absence de / devant exclut « foo/dist/ » ou « a-dist/ ».
LITERAL = re.compile(r'(?<![\w/.-])(work|dist|keys|tools|patch)/')
QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')

checks: list[tuple[str, bool, str]] = []
skipped: list[tuple[str, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    checks.append((label, bool(ok), detail))


def _scripts(suffix: str) -> list[Path]:
    return sorted(
        p for p in PATCH.rglob(f"*{suffix}")
        if "__pycache__" not in p.parts and p.is_file()
    )


def _code_lines_python(src: str) -> list[str] | None:
    """Lignes de code exécutable : ni commentaire, ni docstring."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    drop: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False) is not None:
                first = node.body[0]
                drop.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                drop.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        pass
    return [line for n, line in enumerate(src.splitlines(), 1) if n not in drop]


def _body_lines_shell(src: str) -> list[str]:
    """Lignes utiles : on retire les commentaires, pas le code."""
    return [l for l in src.splitlines() if not l.strip().startswith("#")]


# ── R1 / R2 : shell ────────────────────────────────────────────────────────
def rules_shell() -> None:
    scripts = _scripts(".sh")
    check(f"R2 le dépôt contient des scripts shell à auditer ({len(scripts)})", bool(scripts))

    for path in scripts:
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8", errors="replace")
        body = _body_lines_shell(src)

        computes = "BASH_SOURCE" in src
        uses = any(re.search(r'\$\{?ROOT\b', l) for l in body)

        if computes:
            check(f"R1 {rel} : racine calculée ET utilisée", uses,
                  "racine calculée depuis BASH_SOURCE mais jamais référencée — "
                  "une promesse d'ancrage que rien n'assure")
        else:
            check(f"R1 {rel} : pas de racine morte", True, "")

        unquoted = [l for l in body if LITERAL.search(QUOTED.sub("", l))]
        anchored = computes and uses
        detail = ""
        if unquoted and not anchored:
            where = "L%d" % (body.index(unquoted[0]) + 1)
            detail = (f"{where} : littéral hors guillemets sans ancrage — il se résout "
                      f"depuis le répertoire courant de celui qui appelle le script")
        check(f"R2 {rel} : {len(unquoted)} littéral(aux) de chemin, ancrage présent",
              (not unquoted) or anchored, detail)


# ── R3 : python ────────────────────────────────────────────────────────────
def rules_python() -> None:
    scripts = _scripts(".py")
    check(f"R3 le dépôt contient des scripts python à auditer ({len(scripts)})", bool(scripts))

    for path in scripts:
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8", errors="replace")
        code = _code_lines_python(src)
        if code is None:
            check(f"R3 {rel} : python analysable", False, "SyntaxError — fichier illisible")
            continue
        # Pas de filtrage « hors guillemets » ici : en Python un chemin est presque
        # toujours une chaîne (« pathlib.Path("work/decoded") »), et le retirer de
        # l'analyse rendrait la règle inerte. Les docstrings et commentaires, eux,
        # sont déjà écartés plus haut.
        hits = [l for l in code if LITERAL.search(l)]
        anchored = "__file__" in src
        check(f"R3 {rel} : {len(hits)} littéral(aux) de chemin, ancrage __file__",
              (not hits) or anchored,
              "littéral de chemin dans du code exécutable sans __file__ : "
              "le script dépend du répertoire courant")


# ── R4 : preuve comportementale ─────────────────────────────────────────────
# Choisis pour couvrir shell et python, rester rapide (~11 s) et ne demander
# ni appareil, ni build, ni réseau.
BEHAVIOURAL: list[tuple[str, list[str | Path]]] = [
    ("check-secrets.py", [sys.executable, ROOT / "patch" / "check-secrets.py"]),
    ("sync-readme.py --check", [sys.executable, ROOT / "patch" / "sync-readme.py", "--check"]),
    ("test_sanitizer.py", [sys.executable, ROOT / "patch" / "tests" / "test_sanitizer.py"]),
    ("test_update_check.py", [sys.executable, ROOT / "patch" / "tests" / "test_update_check.py"]),
    ("test_smali_branches.py", [sys.executable, ROOT / "patch" / "tests" / "test_smali_branches.py"]),
    ("test_radar.py", [sys.executable, ROOT / "patch" / "tests" / "test_radar.py"]),
    ("test_normalize_apk.py", [sys.executable, ROOT / "patch" / "tests" / "test_normalize_apk.py"]),
    ("test_check_secrets.py", [sys.executable, ROOT / "patch" / "tests" / "test_check_secrets.py"]),
    ("check_phone_geometry.py", [sys.executable, ROOT / "patch" / "tests" / "check_phone_geometry.py"]),
]


def _posix_script(p: Path) -> tuple[str, str] | None:
    """(interpréteur, chemin du script dans l'espace de noms de cet interpréteur).

    Rejouer un script shell suppose un shell capable de l'ouvrir, et le « bash »
    que trouve un Python sous Windows n'est pas forcément le bon : ici, `bash`
    désigne le lanceur **WSL**, dont l'espace de noms est « /mnt/d/... » — lui
    passer un chemin Git échoue sur une conversion de montage, sans rapport avec
    l'ancrage qu'on veut vérifier. D'où une découverte explicite du shell, et le
    chemin du dépôt rendu dans SON espace de noms.

    None si aucun shell connu n'est disponible : le cas est alors déclaré non
    applicable — jamais « OK » en silence.
    """
    if os.name == "nt":
        for cand in (r"C:\Program Files\Git\bin\bash.exe",
                     r"C:\Program Files\Git\usr\bin\bash.exe",
                     r"C:\Program Files (x86)\Git\bin\bash.exe"):
            if Path(cand).exists():
                posix = p.as_posix()
                m = re.match(r'^([A-Za-z]):/(.*)$', posix)
                if not m:
                    return None
                return cand, f"/{m.group(1).lower()}/{m.group(2)}"
        return None
    bash = shutil.which("bash")
    return (bash, str(p)) if bash else None


def rule_behavioural() -> None:
    check(f"R4 au moins un script rejoué hors répertoire", bool(BEHAVIOURAL))
    # ignore_cleanup_errors : sous Windows, un shell lance avec cwd= garde la
    # poignée du repertoire pendant sa sortie, et le rmtree échoue en PermissionError.
    # Un répertoire temporaire laissé derrière ne mérite pas de faire échouer le test.
    with tempfile.TemporaryDirectory(prefix="twouich-cwd-", ignore_cleanup_errors=True) as elsewhere:
        for label, argv in BEHAVIOURAL:
            argv = [a.as_posix() if isinstance(a, Path) else a for a in argv]
            try:
                proc = subprocess.run(
                    argv, cwd=elsewhere, capture_output=True, text=True,
                    timeout=300, encoding="utf-8", errors="replace",
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                check(f"R4 {label} depuis un répertoire étranger", False, str(exc))
                continue
            tail = (proc.stderr or proc.stdout).strip().splitlines()
            detail = f"sortie {proc.returncode} alors que le répertoire courant n'est pas le dépôt"
            if tail:
                detail += " — " + tail[-1][:110]
            check(f"R4 {label} depuis un répertoire étranger", proc.returncode == 0, detail)

        shell = _posix_script(ROOT / "patch" / "tests" / "test_analyzer.sh")
        if shell is None:
            skipped.append(("test_analyzer.sh", "aucun bash Git ou POSIX trouvable"))
        else:
            exe, script_posix = shell
            try:
                proc = subprocess.run([exe, script_posix], cwd=elsewhere, capture_output=True,
                                      text=True, timeout=300, encoding="utf-8", errors="replace")
            except (OSError, subprocess.TimeoutExpired) as exc:
                check("R4 test_analyzer.sh depuis un répertoire étranger", False, str(exc))
            else:
                tail = (proc.stderr or proc.stdout).strip().splitlines()
                detail = f"sortie {proc.returncode} alors que le répertoire courant n'est pas le dépôt"
                if tail:
                    detail += " — " + tail[-1][:110]
                check("R4 test_analyzer.sh depuis un répertoire étranger", proc.returncode == 0, detail)


def main() -> int:
    rules_shell()
    rules_python()
    rule_behavioural()

    width = max(len(label) for label, _, _ in checks)
    failed = 0
    for label, ok, detail in checks:
        print(f"[{'OK ' if ok else 'KO '}] {label.ljust(width)}")
        if not ok:
            failed += 1
            if detail:
                print(f"        -> {detail}")
    if skipped:
        print()
        for label, why in skipped:
            print(f"[N/A] {label} — non applicable : {why}")
    print(f"\n{len(checks) - failed}/{len(checks)} verifications passees")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())