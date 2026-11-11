#!/usr/bin/env python3
"""
Erzeugt die Fonts und Texturen fuer Menues mit freiem Layout (ui/Canvas im Plugin, Vorlage: /jobs).

Nur Standardbibliothek. Aufruf (aus dem Ordner FMC-Resourcepack):
    python tools/menu_kit.py

Schreibt:
    pack/assets/fmc/textures/font/menu/*.png   Kastenstreifen und Bloecke (weiss, per Textfarbe eingefaerbt)
    pack/assets/fmc/font/menu.json             fmc:menu   Kaesten (jede Reihe ein eigenes Zeichen je Zeile 0..ROWS-1)
    pack/assets/fmc/font/p0.json .. p8.json    fmc:p0..8  Vanilla-Text, alle Icons aus icons.json, Vanilla-Items,
                                                          Bloecke; um 0..8 Pixel nach unten versetzt
    pack/assets/fmc/font/b0.json .. b8.json    fmc:b0..8  doppelt grosse Vanilla-Schrift (Titel), ebenso versetzt

Benoetigt icons.json (von generate_icons.py) und liest die Item-Liste aus FMC-Plugin/.../ui/MenuItem.java
(Pfad zum Plugin per Umgebungsvariable FMC_PLUGIN_DIR aenderbar). Die Konstanten unten muessen zu ui/MenuFont.java
passen.

Wie es funktioniert:
  - Kaesten sind beliebig breit: linke Kante + Mittelstuecke (1, 2, 4 ... 128 Pixel) + rechte Kante, und beliebig
    hoch: oberer Streifen, n mittlere, unterer (je eine Textzeile = 9 Pixel). Jeder Streifen gibt es fuer jede
    Zeile ROW mit ascent 7 - 9 * ROW; das Plugin schreibt alle Kaesten in die erste Textzeile, so liegen sie unter
    allem anderen Inhalt.
  - Zwei Ebenen je Kasten: Fuellung (inkl. dunkler Aussenlinie) und Rand. Beide sind weiss und werden per Textfarbe
    eingefaerbt, daher braucht es keine Bilder je Farbe.
  - Minecraft misst die Breite eines Zeichens an der letzten nicht ganz durchsichtigen Spalte. Jede Textur bekommt
    dort notfalls einen Punkt mit Alpha 1 (den verwirft der Text-Shader, er ist unsichtbar), damit der Vorschub
    immer Bildbreite + 1 ist.
  - Vanilla-Text und -Items werden nicht kopiert: die Fonts verweisen auf minecraft:font/*.png und
    minecraft:item/*.png. Die Zeichenliste der Vanilla-Schrift liegt in tools/data/vanilla_font_default.json.
"""
import json
import os
import re
import struct
import sys
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACK = os.path.join(ROOT, "pack")
FONT_DIR = os.path.join(PACK, "assets", "fmc", "font")
TEX_DIR = os.path.join(PACK, "assets", "fmc", "textures", "font", "menu")
ICONS_JSON = os.path.join(FONT_DIR, "icons.json")
VANILLA_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vanilla_font_default.json")
PLUGIN_DIR = os.environ.get("FMC_PLUGIN_DIR", os.path.join(ROOT, "..", "FMC-Plugin"))
MENU_ITEM_JAVA = os.path.join(PLUGIN_DIR, "src", "main", "java", "com", "example", "myplugin", "ui", "MenuItem.java")

# ── Muss zu ui/MenuFont.java passen ─────────────────────────────────────────────────────────────────────────────
LINE = 9                      # Hoehe einer Textzeile
SHIFTS = 9                    # Versatz 0..8 Pixel -> Fonts p0..p8, b0..b8
ROWS = 32                     # Zeilen, in denen Kaesten liegen koennen
CAP_W = 4                     # Breite der Kastenkanten
MIDS = [1, 2, 4, 8, 16, 32, 64, 128]
BOX_TOP_ROW = 1               # erste sichtbare Reihe im oberen Streifen
BOX_BOTTOM_ROW = 7            # letzte sichtbare Reihe im unteren Streifen
BLOCK_HEIGHTS = [1, 3, 5]
BOX_BASE = 0xE000             # + ((ebene * 3 + streifen) * STUECKE + stueck) * ROWS + zeile
ITEM_BASE = 0xF000            # + 2 * index (gross), + 1 (klein)
BLOCK_BASE = 0xF400           # + hoehenindex * len(MIDS) + breitenindex
FILL, EDGE = 0, 1
TOP, MID, BOT = 0, 1, 2
PIECES = 2 + len(MIDS)        # links, rechts, Mittelstuecke

# Abstandszeichen wie in icons.json (UiKit.space)
SPACERS = {"\uF801": -1, "\uF808": -2, "\uF809": -4, "\uF80A": -8, "\uF80B": -16, "\uF80C": -32,
           "\uF802": 1, "\uF803": 2, "\uF804": 4, "\uF805": 8, "\uF806": 16, "\uF807": 32}

# Aussehen der Kaesten (Grauwerte, die Farbe kommt aus der Textfarbe)
OUTLINE_V = 90                # dunkle Aussenlinie (Fuellebene, also abgedunkelte Fuellfarbe)
FILL_A = 238                  # Deckkraft der Fuellung
EDGE_BOTTOM_V = 200           # unterer Rand etwas dunkler (wirkt plastisch)
GLOW_A = 70                   # helle Linie innen am Rand
FAR = 99
CLEAR = (0, 0, 0, 0)


# ── PNG ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def write_png(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h, w = len(rows), len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def keep_width(rows):
    """Unsichtbarer Punkt in der rechten Spalte, falls sie sonst leer ist (siehe Kopfkommentar)."""
    last = len(rows[0]) - 1
    if all(row[last][3] == 0 for row in rows):
        rows[0][last] = (0, 0, 0, 1)
    return rows


# ── Kaesten ─────────────────────────────────────────────────────────────────────────────────────────────────────

def ring(dx, dy):
    """0 = Aussenlinie, 1 = Rand, 2 = Glanzlinie, >= 3 Fuellung, < 0 aussen. Ecken um 1 Pixel abgeschraegt."""
    if dx < 2 and dy < 2:
        return dx + dy - 1
    return min(dx, dy)


def box_pixel(layer, dx, dy, bottom):
    r = ring(dx, dy)
    if r < 0:
        return CLEAR
    if layer == FILL:
        if r == 0:
            return (OUTLINE_V, OUTLINE_V, OUTLINE_V, 255)
        return (255, 255, 255, FILL_A)
    if r == 1:
        v = EDGE_BOTTOM_V if bottom and dy <= dx else 255
        return (v, v, v, 255)
    if r == 2:
        return (255, 255, 255, GLOW_A)
    return CLEAR


def strip_dy(strip, row):
    """Abstand der Pixelreihe zum oberen/unteren Kastenrand (None = ausserhalb) und ob es der untere ist."""
    if strip == TOP:
        return (None if row < BOX_TOP_ROW else row - BOX_TOP_ROW), False
    if strip == BOT:
        return (None if row > BOX_BOTTOM_ROW else BOX_BOTTOM_ROW - row), True
    return FAR, False


def piece_dx(piece):
    if piece == 0:
        return list(range(CAP_W))
    if piece == 1:
        return [CAP_W - 1 - c for c in range(CAP_W)]
    return [FAR] * MIDS[piece - 2]


def render_piece(layer, strip, piece):
    rows = []
    for row in range(LINE):
        dy, bottom = strip_dy(strip, row)
        rows.append([CLEAR if dy is None else box_pixel(layer, dx, dy, bottom) for dx in piece_dx(piece)])
    return keep_width(rows)


def box_char(layer, strip, piece, row):
    return chr(BOX_BASE + ((layer * 3 + strip) * PIECES + piece) * ROWS + row)


def menu_font():
    providers = [{"type": "space", "advances": SPACERS}]
    for layer in (FILL, EDGE):
        for strip in (TOP, MID, BOT):
            for piece in range(PIECES):
                name = f"box_{layer}_{strip}_{piece}.png"
                write_png(os.path.join(TEX_DIR, name), render_piece(layer, strip, piece))
                for row in range(ROWS):
                    providers.append({"type": "bitmap", "file": f"fmc:font/menu/{name}",
                                      "ascent": 7 - LINE * row, "height": LINE,
                                      "chars": [box_char(layer, strip, piece, row)]})
    return providers


# ── Bloecke, Items, Icons, Text ─────────────────────────────────────────────────────────────────────────────────

def write_blocks():
    """Weisse Rechtecke; das Bild ist immer eine Zeile hoch (ascent darf nicht groesser als die Hoehe sein),
    das Rechteck sitzt oben darin."""
    for h in BLOCK_HEIGHTS:
        for w in MIDS:
            rows = [[(255, 255, 255, 255) if y < h else CLEAR for _ in range(w)] for y in range(LINE)]
            write_png(os.path.join(TEX_DIR, f"block_{h}_{w}.png"), rows)


def block_providers(shift):
    out = []
    for hi, h in enumerate(BLOCK_HEIGHTS):
        for wi, w in enumerate(MIDS):
            out.append({"type": "bitmap", "file": f"fmc:font/menu/block_{h}_{w}.png", "ascent": 7 - shift,
                        "height": LINE, "chars": [chr(BLOCK_BASE + hi * len(MIDS) + wi)]})
    return out


def read_menu_items():
    with open(MENU_ITEM_JAVA, encoding="utf-8") as f:
        source = f.read()
    items = re.findall(r'^\s+([A-Z0-9_]+)\("([a-z0-9_/]+)",\s*(\d+)\)[,;]', source, re.MULTILINE)
    if not items:
        sys.exit(f"Keine Items in {MENU_ITEM_JAVA} gefunden")
    return items


def item_providers(items, shift):
    out = []
    for i, (_, texture, _) in enumerate(items):
        for offset, height in ((0, 32), (1, 16)):
            out.append({"type": "bitmap", "file": f"minecraft:{texture}.png", "ascent": 7 - shift,
                        "height": height, "chars": [chr(ITEM_BASE + 2 * i + offset)]})
    return out


def icon_providers(shift):
    """Alle Icons (klein und gross) aus icons.json, mit denselben Zeichen, versetzt."""
    with open(ICONS_JSON, encoding="utf-8") as f:
        source = json.load(f)["providers"]
    out = []
    for p in source:
        if p.get("type") != "bitmap" or not p.get("file", "").startswith("fmc:font/icons/"):
            continue
        if p.get("height") not in (9, 14):
            continue
        chars = p["chars"]
        if any(ITEM_BASE <= ord(c) < BLOCK_BASE + 0x100 or 0xF800 <= ord(c) <= 0xF80F for row in chars for c in row):
            continue
        out.append({"type": "bitmap", "file": p["file"], "ascent": p["ascent"] - shift,
                    "height": p["height"], "chars": chars})
    return out


def text_providers(scale, shift):
    """Vanilla-Schrift (ohne Unifont), skaliert. Die Grundlinie bleibt bei allen Teilen gleich:
    ascent = 7 - shift - scale * (7 - vanilla_ascent)."""
    with open(VANILLA_FONT, encoding="utf-8") as f:
        source = json.load(f)["providers"]
    out = []
    for p in source:
        if p.get("type") != "bitmap":
            continue
        height = p.get("height", 8)
        ascent = 7 - shift - scale * (7 - p["ascent"])
        if ascent > height * scale:
            sys.exit(f"ascent {ascent} > Hoehe {height * scale} in {p['file']}")
        out.append({"type": "bitmap", "file": p["file"], "ascent": ascent, "height": height * scale,
                    "chars": p["chars"]})
    space = {" ": 4 * scale - (scale - 1), "\u200c": 0}
    space.update(SPACERS)
    return [{"type": "space", "advances": space}] + out


def write_font(name, providers):
    path = os.path.join(FONT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"providers": providers}, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    return path


def main():
    items = read_menu_items()
    boxes = menu_font()
    count = len(boxes)
    write_font("menu", boxes)
    write_blocks()
    for shift in range(SHIFTS):
        write_font(f"p{shift}", text_providers(1, shift) + icon_providers(shift) + item_providers(items, shift)
                   + block_providers(shift))
        write_font(f"b{shift}", text_providers(2, shift))
    print(f"fmc:menu mit {count} Eintraegen, p0..p{SHIFTS - 1} und b0..b{SHIFTS - 1} geschrieben, "
          f"{len(items)} Vanilla-Items:")
    for i, (name, texture, _) in enumerate(items):
        print(f"  U+{ITEM_BASE + 2 * i:04X}  {name}  ({texture})")


if __name__ == "__main__":
    main()
