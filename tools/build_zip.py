#!/usr/bin/env python3
"""
Packt pack/ zu dist/FMC-Resourcepack.zip und gibt den SHA-1 aus.

    python tools/build_zip.py

Es wird bewusst nicht Compress-Archive benutzt: Windows PowerShell 5.1 schreibt
Backslashes in die ZIP-Pfade, damit laedt Minecraft das Pack nicht.
Die ZIP hat pack.mcmeta direkt im Wurzelverzeichnis (nicht in einem Unterordner).
"""
import hashlib
import os
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACK = os.path.join(ROOT, "pack")
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(DIST, "FMC-Resourcepack.zip")


def main():
    os.makedirs(DIST, exist_ok=True)
    files = []
    for folder, _, names in os.walk(PACK):
        for name in names:
            full = os.path.join(folder, name)
            files.append((full, os.path.relpath(full, PACK).replace(os.sep, "/")))
    files.sort(key=lambda f: f[1])

    # Feste Zeitstempel -> gleicher Inhalt ergibt immer denselben SHA-1
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for full, arc in files:
            info = zipfile.ZipInfo(arc, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(full, "rb") as f:
                z.writestr(info, f.read())

    with open(OUT, "rb") as f:
        sha1 = hashlib.sha1(f.read()).hexdigest()
    print(f"{OUT}\n{len(files)} Dateien\nSHA-1: {sha1}")


if __name__ == "__main__":
    main()
