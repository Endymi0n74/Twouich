"""Vérifie la séquence portrait générée par patch.py (bloc du lecteur)."""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("twpatch", HERE / "patch.py")
patch = importlib.util.module_from_spec(spec)
sys.argv = ["patch.py", "--decoded", "x", "--version-code", "165",
            "--version-name", "v1.0.18", "--apk-name", "x.apk",
            "--release-date", "2026.10.04"]
spec.loader.exec_module(patch)

seq = patch.PHONE_GEO_TAIL
print("--- sequence portrait generee ---")
print(seq)

problems = []
first_test = min([seq.index(k) for k in ("if-ge v10, v7", "if-lt v10, v7") if k in seq])
before = seq[:first_test]
if "View;->getHeight()I" not in before or "move-result v11" not in before:
    problems.append("hauteur du compositeur reel absente avant la geometrie")
if "DisplayMetrics;->density:F" not in before or "0x42800000" not in before:
    problems.append("repli en dp/densite absent avant la premiere mesure")
if "sub-int v7, v9, v11" not in before:
    problems.append("hauteur disponible avant la video non initialisee")

after = seq[seq.index(":twouich_phone_video_fits"):]
if "sub-int v7, v9, v10" not in after:
    problems.append("hauteur du chat non recalculee apres le plafond de la video")
if "sub-int/2addr v7, v11" not in after:
    problems.append("hauteur reelle du compositeur non deduite de la zone du chat")
if "if-ge v7, v3, :twouich_phone_room" not in seq:
    problems.append("garde de place minimale pour le chat absent")

for problem in problems:
    print("KO :", problem)
print("OK" if not problems else "ECHEC")
sys.exit(1 if problems else 0)