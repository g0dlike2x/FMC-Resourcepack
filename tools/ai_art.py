#!/usr/bin/env python3
"""
Erzeugt Bilder (Verzierungen fuer Menues) mit der OpenAI-Bild-API und bereitet sie fuers Pack auf.
Nur Standardbibliothek. Der Key kommt NIE in den Code oder ins Repo, sondern aus der Umgebungsvariable
OPENAI_API_KEY.

    python tools/ai_art.py gen <name> [anzahl]  Bild zu art/prompts.json[name] erzeugen -> art/raw/<name>.png
                                               (bei anzahl > 1: <name>_1.png, <name>_2.png ...)
    python tools/ai_art.py prep <name> [breite]  zuschneiden (transparenter Rand weg) und verkleinern -> art/<name>.png
                                               (ohne breite: "prep_width" aus prompts.json, sonst Originalgroesse)
    python tools/ai_art.py theme <theme>       alle Bilder eines Themes (warp, farmwelt, amethyst) erzeugen und
                                               aufbereiten: Rahmen, Ecke, Ornament, Titel
    python tools/ai_art.py jobs [job_x ...]    Job-Icons (job_* in prompts.json, mit "icon_size") erzeugen, als
                                               64 x 64 nach pack/assets/fmc/textures/font/art/ legen; danach
                                               tools/menu_kit.py (Eintraege JOB_* in tools/data/menu_items.txt)

Danach python tools/generate_icons.py ausfuehren und dist/preview_<theme>.png ansehen. Ein misslungenes Bild einfach
neu erzeugen (gen + prep) oder art/<name>.png loeschen, dann nimmt das Theme den gezeichneten Ersatz.

Rohbilder (art/raw/) sind gross und stehen nicht im Repo; die aufbereiteten Bilder in art/ schon, damit
generate_icons.py ohne API-Zugriff funktioniert.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

import amethyst_theme as am
import generate_icons as gi
import pngread

ROOT = gi.ROOT
ART = os.path.join(ROOT, "art")
RAW = os.path.join(ART, "raw")
PROMPTS = os.path.join(ART, "prompts.json")
MODEL = os.environ.get("FMC_IMAGE_MODEL", "gpt-image-1.5")


def _spec(name):
    specs = json.load(open(PROMPTS, encoding="utf-8"))
    if name not in specs:
        sys.exit("Kein Prompt fuer '%s' in art/prompts.json" % name)
    return specs[name]


def generate(name, count=1):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY ist nicht gesetzt.")
    spec = _spec(name)
    body = {
        "model": MODEL,
        "prompt": spec["prompt"],
        "size": spec.get("size", "1024x1024"),
        "quality": spec.get("quality", "medium"),
        "background": "transparent",
        "output_format": "png",
        "n": count,
    }
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %d: %s" % (e.code, e.read().decode()[:500].replace(key, "<key>")))
    os.makedirs(RAW, exist_ok=True)
    for i, item in enumerate(data["data"]):
        path = os.path.join(RAW, name + ("" if count == 1 else "_%d" % (i + 1)) + ".png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(item["b64_json"]))
        print(path)


def crop_alpha(rows, threshold=12, margin=2):
    h, w = len(rows), len(rows[0])
    ys = [y for y in range(h) if any(p[3] > threshold for p in rows[y])]
    xs = [x for x in range(w) if any(rows[y][x][3] > threshold for y in range(h))]
    if not ys or not xs:
        sys.exit("Bild ist leer/transparent.")
    y0, y1 = max(0, ys[0] - margin), min(h, ys[-1] + 1 + margin)
    x0, x1 = max(0, xs[0] - margin), min(w, xs[-1] + 1 + margin)
    return [row[x0:x1] for row in rows[y0:y1]]


ICON_DIR = os.path.join(ROOT, "pack", "assets", "fmc", "textures", "font", "art")


def prep_icon(name, size):
    """Menue-Icon: transparenten Rand weg, mittig auf ein Quadrat, auf size x size verkleinern -> direkt ins Pack
    (pack/assets/fmc/textures/font/art/<name>.png). Im Plugin ueber tools/data/menu_items.txt einbinden."""
    rows = crop_alpha(pngread.png_read(open(os.path.join(RAW, name + ".png"), "rb").read()), margin=0)
    h, w = len(rows), len(rows[0])
    side = max(w, h)
    square = [[(0, 0, 0, 0)] * side for _ in range(side)]
    ox, oy = (side - w) // 2, (side - h) // 2
    for y in range(h):
        square[oy + y][ox:ox + w] = rows[y]
    rows = am.resize(square, size, size) if size < side else square
    # Halbtransparente Kantenpixel der Verkleinerung haerter machen (wirkt im Spiel sonst ausgefranst)
    rows = [[(r, g, b, 0 if a < 40 else (255 if a > 200 else a)) for r, g, b, a in row] for row in rows]
    out = os.path.join(ICON_DIR, name + ".png")
    gi.write_png(out, rows)
    print(out, size, "x", size)


def prep(name, width=None):
    spec = _spec(name)
    if spec.get("icon_size"):
        prep_icon(name, spec["icon_size"])
        return
    if width is None:
        width = spec.get("prep_width")
    rows = pngread.png_read(open(os.path.join(RAW, name + ".png"), "rb").read())
    rows = crop_alpha(rows)
    h, w = len(rows), len(rows[0])
    if width and width < w:
        rows = am.resize(rows, width, max(1, round(h * width / w)))
    os.makedirs(ART, exist_ok=True)
    out = os.path.join(ART, name + ".png")
    gi.write_png(out, rows)
    print(out, len(rows[0]), "x", len(rows))


def theme_names(key):
    for th in am.THEMES:
        if th.key == key:
            return [th.panel_art, th.corner_art, th.banner_art] + [t.lower() + "_title" for t in th.titles]
    sys.exit("Unbekanntes Theme '%s' (bekannt: %s)" % (key, ", ".join(t.key for t in am.THEMES)))


if __name__ == "__main__":
    icon_groups = {"jobs": "job_", "casino": "casino_", "shop": "shop_"}
    if len(sys.argv) >= 2 and sys.argv[1] in icon_groups:
        # Alle Icons eines Typs erzeugen und ins Pack legen; danach tools/menu_kit.py
        prefix = icon_groups[sys.argv[1]]
        only = sys.argv[2:]
        for art_name in [n for n in json.load(open(PROMPTS, encoding="utf-8")) if n.startswith(prefix)]:
            if not only or art_name in only:
                out = os.path.join(ICON_DIR, art_name + ".png")
                if os.path.exists(out):
                    print("Skip (exists):", art_name)
                    continue
                generate(art_name)
                prep(art_name)
        sys.exit(0)
    if len(sys.argv) < 3 or sys.argv[1] not in ("gen", "prep", "theme"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "gen":
        generate(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    elif sys.argv[1] == "prep":
        prep(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    else:
        for art_name in theme_names(sys.argv[2]):
            generate(art_name)
            prep(art_name)
