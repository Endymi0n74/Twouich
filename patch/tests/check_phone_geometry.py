"""Vérifie la séquence portrait générée par patch.py (bloc du lecteur).

Garde hors appareil pour le VerifyError du 05/10 : `v7` porte la référence
DisplayMetrics issue de getDisplayMetrics(), donc le test de plafond doit être
précédé d'une ÉCRITURE ENTIÈRE dans v7 — sinon ART rejette la classe entière
(`args to 'if' (Integer, Reference: android.util.DisplayMetrics) must be
integral`) et le lecteur ne s'ouvre plus du tout.
"""
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
if "sub-int v7, v9, v10" not in before or "sub-int/2addr v7, v11" not in before:
    problems.append("aucun entier ecrit dans v7 avant le test de plafond (VerifyError)")
elif before.rindex("sub-int/2addr v7, v11") < before.rindex("sub-int v7, v9, v10"):
    problems.append("calcul de la place dans le desordre")

after = seq[seq.index(":twouich_phone_video_fits"):]
if "sub-int v7, v9, v10" not in after:
    problems.append("hauteur du chat non recalculee apres le plafond de la video")

for problem in problems:
    print("KO :", problem)
print("OK" if not problems else "ECHEC")
sys.exit(1 if problems else 0)