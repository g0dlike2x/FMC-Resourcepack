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

Benoetigt icons.json (von generate_icons.py). Die Vanilla-Items stehen in tools/data/menu_items.txt; Textur, Breite
und Einfaerbung werden beim ersten Mal aus den Vanilla-Daten geladen (Netz) und in tools/data/menu_items.json
gespeichert. Schreibt ausserdem FMC-Plugin/.../ui/MenuItem.java (Pfad zum Plugin per Umgebungsvariable
FMC_PLUGIN_DIR aenderbar). Die Konstanten unten muessen zu ui/MenuFont.java passen.

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
import math
import os
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
ITEM_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "menu_items.txt")
ITEM_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "menu_items.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngread import png_read  # noqa: E402

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
MEDIUM_BASE = 0xF500          # + index: mittlere Groesse (MEDIUM Pixel, z. B. Job-Kacheln)
MEDIUM = 24
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

CORNER_R = CAP_W              # Eckenradius in Pixeln (hoechstens CAP_W, die Ecke liegt ganz in der Kante)


def ring(dx, dy):
    """0 = Aussenlinie, 1 = Rand, 2 = Glanzlinie, >= 3 Fuellung, < 0 aussen. Ecken rund mit Radius CORNER_R."""
    r = CORNER_R
    if dx < r and dy < r:
        cx, cy = r - dx - 0.5, r - dy - 0.5
        return math.floor(r - math.hypot(cx, cy))
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


# ── Vanilla-Items ───────────────────────────────────────────────────────────────────────────────────────────────
# Liste: tools/data/menu_items.txt ("MATERIAL" oder "MATERIAL textur/pfad", Reihenfolge = Zeichen, nur anhaengen).
# Textur, Breite und Einfaerbung werden einmal aus den Vanilla-Daten (github.com/misode/mcmeta) ermittelt und in
# tools/data/menu_items.json zwischengespeichert; danach braucht das Skript kein Netz mehr.

MCMETA = "https://raw.githubusercontent.com/misode/mcmeta/assets/assets/minecraft/"
TEXTURE_KEYS = ["layer0", "side", "all", "texture", "front", "cross", "plant", "crop", "top", "end", "pattern",
                "particle"]
GRASS_TINT = 0x7CBD6B


def fetch(path):
    import urllib.request
    with urllib.request.urlopen(MCMETA + path, timeout=30) as r:
        return r.read()


def fetch_json(path):
    try:
        return json.loads(fetch(path))
    except Exception:
        return None


def strip_ns(ref):
    return ref.split(":", 1)[1] if ":" in ref else ref


def first_model(node):
    """Erstes Modell eines items/*.json-Knotens und seine Einfaerbungen (select/condition: Rueckfallwert)."""
    if not isinstance(node, dict):
        return None, []
    kind = strip_ns(node.get("type", "model"))
    if kind == "model":
        return node.get("model"), node.get("tints", [])
    if kind == "special":
        return None, []    # Truhe, Koepfe, Schild ...: 3D-Modell ohne passende Textur (Textur in der Liste angeben)
    for key in ("fallback", "on_false", "on_true"):
        if key in node:
            found = first_model(node[key])
            if found[0]:
                return found
    for key in ("cases", "entries"):
        for entry in node.get(key, []):
            found = first_model(entry.get("model"))
            if found[0]:
                return found
    return None, []


def model_texture(model_id):
    """Die Textur, die am ehesten wie das Item aussieht (Item-Bild oder Seitenflaeche des Blocks)."""
    textures, ref, seen = {}, model_id, set()
    while ref and ref not in seen:
        seen.add(ref)
        model = fetch_json("models/" + strip_ns(ref) + ".json")
        if model is None:
            break
        for k, v in model.get("textures", {}).items():
            textures.setdefault(k, v)
        ref = model.get("parent")
    for key in TEXTURE_KEYS:
        value = textures.get(key)
        for _ in range(5):
            if isinstance(value, str) and value.startswith("#"):
                value = textures.get(value[1:])
        if isinstance(value, str):
            return strip_ns(value)
    return None


def tint_of(tints):
    if not tints:
        return None
    t = tints[0]
    kind = strip_ns(t.get("type", ""))
    if kind == "grass":
        return GRASS_TINT
    value = t.get("value", t.get("default"))
    return value & 0xFFFFFF if isinstance(value, int) else None


def resolve_item(material, texture=None, tint=None):
    """{texture, width, tint} oder None (unbekannt oder animierte Textur)."""
    name = material.lower()
    if texture is None:
        item = fetch_json(f"items/{name}.json")
        if item is None:
            return None
        model, tints = first_model(item.get("model"))
        if not model:
            return None
        texture = model_texture(model)
        tint = tint_of(tints)
        if texture is None:
            return None
    try:
        if texture.startswith("fmc:"):
            # Eigenes Bild aus dem Pack (z. B. KI-Icons aus tools/ai_art.py): pack/assets/fmc/textures/<pfad>.png
            local = os.path.join(PACK, "assets", "fmc", "textures", *texture[4:].split("/")) + ".png"
            with open(local, "rb") as f:
                rows = png_read(f.read())
        else:
            rows = png_read(fetch(f"textures/{texture}.png"))
    except Exception:
        return None
    if len(rows) != len(rows[0]):
        return None    # animiert (Streifen aus mehreren Bildern), eine Schrift kann nur das ganze Bild zeigen
    width = 0
    for x in range(len(rows[0])):
        if any(row[x][3] != 0 for row in rows):
            width = x + 1
    if width == 0:
        return None
    return {"texture": texture, "width": width, "size": len(rows), "tint": tint}


def read_menu_items():
    """[(MATERIAL, info oder None)] in fester Reihenfolge; ergaenzt den Zwischenspeicher bei Bedarf."""
    entries = []
    with open(ITEM_LIST, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                parts = line.split()
                entries.append((parts[0].upper(), parts[1] if len(parts) > 1 else None,
                                int(parts[2], 16) if len(parts) > 2 else None))
    cache = {}
    if os.path.exists(ITEM_CACHE):
        with open(ITEM_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    changed = False
    for material, texture, tint in entries:
        cached = cache.get(material) or {}
        local = texture is not None and texture.startswith("fmc:")   # eigene Bilder immer neu messen
        if not local and material in cache and (texture is None
                                                or (cached.get("texture") == texture and cached.get("tint") == tint)):
            continue
        print(f"  ermittle {material} ...")
        cache[material] = resolve_item(material, texture, tint)
        changed = True
    if changed:
        with open(ITEM_CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, indent=1, sort_keys=True)
            f.write("\n")
    if len(entries) > min((BLOCK_BASE - ITEM_BASE) // 2, 0xF800 - MEDIUM_BASE):
        sys.exit("Zu viele Items fuer den Zeichenbereich")
    return [(m, cache.get(m)) for m, _, _ in entries]


def item_providers(items, shift):
    out = []
    for i, (_, info) in enumerate(items):
        if not info:
            continue
        for char, height in ((ITEM_BASE + 2 * i, 32), (ITEM_BASE + 2 * i + 1, 16), (MEDIUM_BASE + i, MEDIUM)):
            tex = info["texture"] if ":" in info["texture"] else "minecraft:" + info["texture"]
            out.append({"type": "bitmap", "file": f"{tex}.png", "ascent": 7 - shift,
                        "height": height, "chars": [chr(char)]})
    return out


def write_menu_item_java(items):
    """ui/MenuItem.java: ein Eintrag je aufloesbarem Item, Zeichen = Position in der Liste."""
    lines = []
    for i, (material, info) in enumerate(items):
        if not info:
            continue
        # Minecraft: Vorschub = (Breite * Skalierung) + 1, die Skalierung ist Zielhoehe / Bildhoehe
        big = int(0.5 + info["width"] * 32 / info["size"]) + 1
        small = int(0.5 + info["width"] * 16 / info["size"]) + 1
        medium = int(0.5 + info["width"] * MEDIUM / info["size"]) + 1
        tint = info.get("tint")
        lines.append(f"    {material}({i}, {big}, {small}, {medium}, "
                     f"{'0x%06X' % tint if tint is not None else '-1'})")
    body = ",\n".join(lines) + ";"
    java = f"""package com.example.myplugin.ui;

import org.bukkit.Material;

import java.util.Locale;

/**
 * GENERIERT von FMC-Resourcepack/tools/menu_kit.py - nicht von Hand aendern.
 * Neue Items: in FMC-Resourcepack/tools/data/menu_items.txt unten anhaengen, dann das Skript ausfuehren.
 *
 * <p>Vanilla-Itembilder als Schriftzeichen fuer {{@link Canvas}}: gross (32 Pixel) und klein (16 Pixel). Das Pack
 * verweist direkt auf die Texturen des Spiels; Bloecke zeigen eine Seitenflaeche. Graue Texturen (Laub, Gras) werden
 * ueber {{@link #tint()}} eingefaerbt.
 */
public enum MenuItem {{
{body}

    private final int index;
    private final int bigAdvance;
    private final int smallAdvance;
    private final int mediumAdvance;
    private final int tint;

    MenuItem(int index, int bigAdvance, int smallAdvance, int mediumAdvance, int tint) {{
        this.index = index;
        this.bigAdvance = bigAdvance;
        this.smallAdvance = smallAdvance;
        this.mediumAdvance = mediumAdvance;
        this.tint = tint;
    }}

    /** Zeichen der mittleren Variante ({{@value MenuFont#MEDIUM}} x {{@value MenuFont#MEDIUM}}). */
    public String medium() {{
        return String.valueOf((char) (MenuFont.MEDIUM_BASE + index));
    }}

    public int mediumAdvance() {{
        return mediumAdvance;
    }}

    /** Zeichen und Vorschub fuer eine Groesse (16, {{@value MenuFont#MEDIUM}} oder 32). */
    public String glyph(int size) {{
        return size >= 32 ? big() : size == MenuFont.MEDIUM ? medium() : small();
    }}

    public int advance(int size) {{
        return size >= 32 ? bigAdvance : size == MenuFont.MEDIUM ? mediumAdvance : smallAdvance;
    }}

    /** Zeichen der grossen Variante (32 x 32). */
    public String big() {{
        return String.valueOf((char) (MenuFont.ITEM_BASE + 2 * index));
    }}

    /** Zeichen der kleinen Variante (16 x 16). */
    public String small() {{
        return String.valueOf((char) (MenuFont.ITEM_BASE + 2 * index + 1));
    }}

    public int bigAdvance() {{
        return bigAdvance;
    }}

    public int smallAdvance() {{
        return smallAdvance;
    }}

    /** Farbe, mit der das Bild eingefaerbt wird (0xFFFFFF = unveraendert). */
    public int tint() {{
        return tint < 0 ? 0xFFFFFF : tint;
    }}

    /** Das Item zu einem Material, oder {{@code fallback}}, wenn es kein Bild dafuer gibt. */
    public static MenuItem of(Material material, MenuItem fallback) {{
        if (material == null) {{
            return fallback;
        }}
        try {{
            return valueOf(material.name().toUpperCase(Locale.ROOT));
        }} catch (IllegalArgumentException e) {{
            return fallback;
        }}
    }}
}}
"""
    os.makedirs(os.path.dirname(MENU_ITEM_JAVA), exist_ok=True)
    with open(MENU_ITEM_JAVA, "w", encoding="utf-8", newline="\n") as f:
        f.write(java)


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
        if any(ITEM_BASE <= ord(c) <= 0xF80F for row in chars for c in row):
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
    write_menu_item_java(items)
    found = sum(1 for _, info in items if info)
    print(f"fmc:menu mit {count} Eintraegen, p0..p{SHIFTS - 1} und b0..b{SHIFTS - 1} geschrieben, "
          f"{found} von {len(items)} Vanilla-Items, MenuItem.java aktualisiert.")
    for name, info in items:
        if not info:
            print(f"  ohne Bild: {name}")


if __name__ == "__main__":
    main()
