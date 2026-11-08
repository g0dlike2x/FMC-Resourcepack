#!/usr/bin/env python3
"""
Panel-Themes fuer PanelMenu: Rahmen mit Glow, Eckverzierungen, Banner (Ornament + Titelbild), Karte mit Itembox,
dunkle Buttons mit farbiger Hervorhebung. Drei Themes (siehe THEMES):

    amethyst   lila, Kristalle und Truhe       /lager      Font fmc:icons     Dateien am_*
    warp       tuerkis, Enderperlen, Endportal  /warp       Font fmc:warp      Dateien wp_*
    farmwelt   gruen, Grasbloecke, Baum, Wasser /farmwelt   Font fmc:farmwelt  Dateien fw_*

Wird von generate_icons.py mit aufgerufen (write_all). Nur Standardbibliothek. Das Modul bekommt
generate_icons als Parameter "gi" uebergeben (Zeichenhilfen, Panel-Masse), damit es keine zirkulaere
Abhaengigkeit gibt.

Alle Themes benutzen dieselben Zeichen (unten); Amethyst liegt in der Font fmc:icons, jedes weitere Theme in einer
eigenen Font (assets/fmc/font/<font>.json). Das Plugin waehlt die Font ueber PanelTheme.

Zeichen (Private Use):
    U+ED00..U+F15F   Rahmenkacheln (oben / Mitte / unten / unten mit hoeher liegender Randlinie)
    U+F200..U+F40D   untere Eckverzierung, je Panelhoehe ein Zeichen links und rechts
    U+F500..U+F507   Ornament, Seitenverzierungen, Schliessen-X, Trennlinien, Symbol fuer die Itembox
    U+F510..U+F513   Karte           U+F520..U+F525  Buttons (normal / hervorgehoben)
    U+F580..         Titelbilder (siehe Theme.titles)
    U+F600..         Hintergrundbilder, je Hoehe (Theme.bg_heights) ein Block von BG_HEIGHT_STRIDE Zeichen

Bilder: art/<name>.png (KI-Bilder, siehe ai_art.py und art/prompts.json). Fehlt beim Warp- oder Farmwelt-Theme ein
Bild, zeichnet theme_art.py einen Ersatz (Eckverzierung, Ornament); ohne Rahmenbild gibt es den Kachelrahmen.
Beim Amethyst-Theme (Lager) muessen die Bilder da sein.

Aufbau des Menues (alles relativ zur Oberkante des Rahmens, 1 Zeile = 9 Pixel):
    AM_PAD_LINES Leerzeilen ueber dem Rahmen: Platz fuer das Ornament, das oben aus dem Rahmen ragt
    AM_HEADER_LINES Kopfzeilen: Ornament, Titelbild, Untertitel; danach die Karte
"""
import json
import math
import os

import pngread
import theme_art

# ── Zeichen ─────────────────────────────────────────────────────────────────
AM_TOP_BASE, AM_MID_BASE, AM_BOT_BASE, AM_BOT_VAR_BASE = 0xED00, 0xED10, 0xED80, 0xEE00
AM_CRYSTAL_BOT_BASE = 0xF200        # + 2 * (Panelhoehe - AM_CRYSTAL_BOT_MIN) + Seite (0 links, 1 rechts)
AM_CRYSTAL_BOT_MIN = 26
AM_ORNAMENT = "\uF500"
AM_CRYSTAL_TOP_L, AM_CRYSTAL_TOP_R = "\uF502", "\uF503"
AM_CLOSE = "\uF504"
AM_RULE_L, AM_RULE_R = "\uF505", "\uF506"
AM_CARD_CHEST = "\uF507"            # Symbol in der Itembox (beim Lager die Truhe)
AM_CARD_BASE = 0xF510
AM_BTN = ("\uF520", "\uF521", "\uF522")        # links, Mitte, rechts
AM_BTN_HI = ("\uF523", "\uF524", "\uF525")
AM_TITLE_BASE = 0xF580                          # + Index in Theme.titles

# ── Masse (GUI-Pixel) ───────────────────────────────────────────────────────
AM_PAD_LINES = 4
AM_HEADER_LINES = 4
AM_NAME_X = 44                 # Textbeginn in der Karte (rechts neben der Itembox)
AM_CARD_ICON_CENTER_X = 24     # Mitte der Itembox im Panel (Karte beginnt bei x = 8, Box also bei 12 bis 36)
AM_BTN_TOP, AM_BTN_BOTTOM = 3.0, 24.0           # sichtbarer Teil des Buttons in der 27 Pixel hohen Kachel
AM_BTN_BELOW_LABEL = 15        # Unterkante des Buttons unter der Oberkante der Textzeile (24 - 9)
AM_CENTER_PAD_LINES = 2
AM_BTN_LABEL_OFFSET = 2       # Zeilen von der Karte bis zur Beschriftung der ersten Button-Reihe (klassisch 3)

ORN_W, ORN_H, ORN_TEX = 96, 32, 2.5          # Ornament: Breite, Hoehe in GUI-Pixeln, Texturpixel je GUI-Pixel
ORN_ABOVE = 18                             # so weit ragt das Ornament ueber den Rahmen
CRY_TOP_W, CRY_TOP_H, CRY_TOP_Y = 11, 16, 14
CRY_BOT_W, CRY_BOT_H, CRY_BOT_OVER = 20, 28, 2
CRY_TEX = 4
TITLE_H, TITLE_TOP = 22, 7                # Titelbild: Hoehe, Oberkante im Rahmen
CLOSE_SIZE = 14
CLOSE_Y = 18                   # Oberkante des Schliessen-X unter der Rahmenoberkante (unter dem Eckkristall)


# ── Themes ──────────────────────────────────────────────────────────────────

class Theme:
    """Ein Theme: Farben, Bilder, Font und die Hoehen, fuer die es ein fertiges Hintergrundbild gibt.

    key          Name (auch fuer theme_art.FALLBACKS und dist/preview_<key>.png)
    java         Praefix der Konstanten in UiIcon.java
    files        Praefix der PNG-Dateien
    font         Font im Pack (fmc:<font>); "icons" = gemeinsame Icon-Font
    titles       Titelbilder (Text, Bild art/<text>_title.png, sonst Pixelschrift)
    title_max_w  hoechste Breite des Titelbilds in GUI-Pixeln
    panel_art    Rahmenbild (mit durchsichtiger Oeffnung) fuer das Hintergrundbild
    corner_art   Eckverzierung (oben klein, unten gross)
    banner_art   Ornament ueber der Mitte
    bg_heights   Rahmenhoehen, fuer die das Hintergrundbild gebaut wird (nur mit panel_art)
    card_icon    Icon (generate_icons.ICONS) in der Itembox der Karte
    art_required Bilder muessen da sein (sonst Ersatz aus theme_art.py)
    c            Farben
    preview      Inhalt von dist/preview_<key>.png
    """

    def __init__(self, **kw):
        self.__dict__.update(kw)


AMETHYST = Theme(
    key="amethyst", java="AM", files="am_", font="icons",
    titles=["LAGER"], title_max_w=80,
    panel_art="lager_panel", corner_art="lager_crystals", banner_art="lager_banner",
    bg_heights=[192], card_icon="chest", art_required=True,
    c=dict(
        fill="#130D27", border="#A06BFF", border2="#4A2F96", glow="#7B3FE4",
        bg_inner=("#1E1550", "#120C2C"), bg_glow="#7B3FE4",
        close_fill=("#2A1C57", "#170F33"), rule="#8E63E8",
        card_fill=("#2A1F55", "#170F30"), card_line=("#C79BFF", "#8A4DFF"),
        box="#7B55D6", box_fill=("#1D1340", "#0F0824"),
        btn_hi_border="#A46BFF", btn_hi_fill=("#33246B", "#1F1445"), btn_hi_glow="#9B5CFF",
        btn_border="#3D3262", btn_fill=("#1E1839", "#16112C"), btn_light="#2A2350",
        title_shadow="#3B1A8C", title_side="#6A35D6", title_top="#FFFFFF", title_bot="#D2B4FF",
        title_glow=(150, 90, 255), subtitle="#A98BE8"),
    preview=dict(
        subtitle="DEIN PERSOENLICHES LAGER", card=["Oak Log", "0 / 64"], bar=True, primary_last=True,
        buttons=[("minus", "-1"), ("minus", "-64"), ("arrow_up", "Auffuellen"), ("plus", "Einzahlen"),
                 ("double_up", "In SuperInv"), ("double_down", "Aus SuperInv"), ("settings", "Limit setzen")]),
)

WARP = Theme(
    key="warp", java="WP", files="wp_", font="warp",
    titles=["WARPS"], title_max_w=90,
    panel_art="warp_panel", corner_art="warp_corner", banner_art="warp_banner",
    bg_heights=[165, 192, 219], card_icon="ender_pearl", art_required=False,
    c=dict(
        fill="#0A1D21", border="#4FE6CC", border2="#16706A", glow="#1FB89E",
        bg_inner=("#103A3C", "#081A1D"), bg_glow="#1FB89E",
        close_fill=("#15484A", "#0B2427"), rule="#4FD6C0",
        card_fill=("#143C40", "#0A2023"), card_line=("#9AF7E6", "#2BB8A6"),
        box="#36A898", box_fill=("#0F3034", "#06171A"),
        btn_hi_border="#55E8CF", btn_hi_fill=("#1A4C4E", "#0E2C2F"), btn_hi_glow="#3FE6C8",
        btn_border="#28525A", btn_fill=("#12292E", "#0D1E22"), btn_light="#1B3A40",
        title_shadow="#0B4A44", title_side="#1F9A88", title_top="#FFFFFF", title_bot="#B4FFF0",
        title_glow=(60, 230, 200), subtitle="#7FD8C8"),
    preview=dict(
        subtitle="WAEHLE DEIN REISEZIEL", card=["Reiseziele", "Klicke zum Teleportieren"], bar=False,
        buttons=[("home", "Spawn"), ("grass", "Farmwelt"), ("cart", "Itemshop"), ("dice", "Casino"),
                 ("rod", "Angeln"), ("pickaxe", "Prison"), ("skull", "Geisterjagd")]),
)

FARMWELT = Theme(
    key="farmwelt", java="FW", files="fw_", font="farmwelt",
    titles=["FARMWELT"], title_max_w=120,
    panel_art="farmwelt_panel", corner_art="farmwelt_corner", banner_art="farmwelt_banner",
    bg_heights=[138], card_icon="grass", art_required=False,
    c=dict(
        fill="#0D1A0F", border="#8BD84F", border2="#2F6B22", glow="#4CAF3A",
        bg_inner=("#1A3A1C", "#0B170C"), bg_glow="#4CAF3A",
        close_fill=("#24502A", "#112814"), rule="#8BD84F",
        card_fill=("#1D3D20", "#0F2111"), card_line=("#C2F28A", "#4FA83A"),
        box="#5DAA45", box_fill=("#143018", "#08160A"),
        btn_hi_border="#8EDB52", btn_hi_fill=("#28502A", "#163018"), btn_hi_glow="#7BD14A",
        btn_border="#2E4E31", btn_fill=("#142A17", "#0E1F10"), btn_light="#1E3A21",
        title_shadow="#1E4A14", title_side="#3F8F2A", title_top="#FFFFFF", title_bot="#D4F7B0",
        title_glow=(120, 215, 80), subtitle="#A6DC84"),
    preview=dict(
        subtitle="WAEHLE DEINE FARMWELT", card=["Farmwelten", "Farmen, abbauen, erkunden"], bar=False,
        buttons=[("grass", "Farmwelt"), ("flame", "Nether"), ("ender_pearl", "End")]),
)

THEMES = [AMETHYST, WARP, FARMWELT]


# ── Hilfen ──────────────────────────────────────────────────────────────────

def resize(rows, tw, th):
    """Flaechengemittelte Groessenaenderung (mit Alpha-Gewichtung)."""
    sh, sw = len(rows), len(rows[0])
    out = []
    for ty in range(th):
        y0, y1 = ty * sh / th, (ty + 1) * sh / th
        orow = []
        for tx in range(tw):
            x0, x1 = tx * sw / tw, (tx + 1) * sw / tw
            sa = sr = sg = sb = tot = 0.0
            for sy in range(int(y0), min(sh, int(math.ceil(y1)))):
                wy = min(y1, sy + 1) - max(y0, sy)
                if wy <= 0:
                    continue
                for sx in range(int(x0), min(sw, int(math.ceil(x1)))):
                    wx = min(x1, sx + 1) - max(x0, sx)
                    if wx <= 0:
                        continue
                    r, g, b, a = rows[sy][sx]
                    wgt = wx * wy
                    tot += wgt
                    sa += a * wgt
                    sr += r * a * wgt
                    sg += g * a * wgt
                    sb += b * a * wgt
            orow.append((0, 0, 0, 0) if sa <= 0 else (round(sr / sa), round(sg / sa), round(sb / sa), round(sa / tot)))
        out.append(orow)
    return out


def flip(rows):
    return [row[::-1] for row in rows]


def _bbox_poly(pts, m=2.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)


def fancy(gi, ic, sdf, colors, box, outline=None, out=1.0, rim=True):
    """Wie Icon.shape (Umriss, Verlauf, Licht oben), aber nur im Rechteck box (schneller)."""
    top, bot = colors
    outline = outline or gi.darker(bot, 0.6)
    y0, y1 = box[1], box[3]
    ic.paint(sdf, outline, grow=out, box=(box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2))
    base = gi.vgrad(y0, y1, top, bot)
    mid = (y0 + y1) / 2

    def col(x, y):
        c = base(x, y)
        if rim and sdf(x, y) > -1.2:
            return gi.lighter(c, 0.35) if y < mid else gi.darker(c, 0.14)
        return c
    ic.paint(sdf, col, box=box)


# ── Rahmen ──────────────────────────────────────────────────────────────────

def frame_tile(gi, th, kind, col, v=None):
    """Kachel des Rahmens (kind: top / mid / bot; v = Zeile der unteren Randlinie bei den Varianten)."""
    u, w = gi.PANEL_UNIT, gi.PANEL_W
    ic = gi.Icon(gi.PANEL_TILE_W, u, scale=gi.PANEL_SCALE, ss=3)
    if kind == "top":
        y0, y1 = 0, 60
    elif kind == "mid":
        y0, y1 = -20, u + 20
    else:
        y0, y1 = -60, (u if v is None else v + 1)
    ox = col * gi.PANEL_TILE_W

    def box(inset, r):
        top = y0 + (inset if kind == "top" else 0)
        bot = y1 - (inset if kind == "bot" else 0)
        return gi._shift_x(gi.sd_box(inset, top, w - inset, bot, r), ox)

    outer, inner = box(0, 4.0), box(1.0, 3.0)
    ic.paint(outer, gi.hexc(th.c["fill"]))
    glow = gi.hexc(th.c["glow"])

    def glow_fn(x, y):
        d = max(0.0, -outer(x, y))
        return (glow[0], glow[1], glow[2], 0.42 * max(0.0, 1.0 - d / 7.0) ** 2)
    ic.paint(outer, glow_fn)
    ic.paint(gi.sub(outer, inner), gi.hexc(th.c["border"]))
    ic.paint(gi.sub(box(2.6, 2.0), box(3.4, 1.4)), gi.hexc(th.c["border2"], 0.85))
    return ic


# ── Bilder ──────────────────────────────────────────────────────────────────

def load_art(gi, name, required=True):
    """Aufbereitetes Bild aus art/<name>.png (zugeschnitten, transparenter Hintergrund)."""
    path = os.path.join(gi.ROOT, "art", name + ".png")
    if not os.path.exists(path):
        if required:
            raise SystemExit("Bild fehlt: %s (erzeugen mit: python tools/ai_art.py gen %s, dann prep)" % (path, name))
        return None
    with open(path, "rb") as f:
        return pngread.png_read(f.read())


def fit(gi, rows, tw, th, align="center"):
    """Passt das Bild unter Beibehaltung des Seitenverhaeltnisses in tw x th Pixel ein (align: center / bottom)."""
    h, w = len(rows), len(rows[0])
    k = min(tw / w, th / h)
    nw, nh = max(1, round(w * k)), max(1, round(h * k))
    small = resize(rows, nw, nh)
    out = gi.blank(tw, th)
    gi.blend(out, small, (tw - nw) // 2, th - nh if align == "bottom" else (th - nh) // 2)
    return out


def _art_or_fallback(gi, th, art_name, fallback, tw, tht):
    art = load_art(gi, art_name, required=th.art_required)
    if art is not None:
        return fit(gi, art, tw, tht, "bottom")
    print("  %s: %s.png fehlt, gezeichneter Ersatz" % (th.key, art_name))
    return theme_art.FALLBACKS[th.key][fallback](tw, tht)


def make_crystal_top(gi, th):
    return _art_or_fallback(gi, th, th.corner_art, "corner_small", CRY_TOP_W * CRY_TEX, CRY_TOP_H * CRY_TEX)


def make_crystal_bottom(gi, th):
    return _art_or_fallback(gi, th, th.corner_art, "corner", CRY_BOT_W * CRY_TEX, CRY_BOT_H * CRY_TEX)


def make_ornament(gi, th):
    return _art_or_fallback(gi, th, th.banner_art, "banner", round(ORN_W * ORN_TEX), round(ORN_H * ORN_TEX))


# -- Hintergrundbild fuer Menues fester Hoehe: KI-Rahmen aus art/<panel_art>.png --
#
# Der Rahmen (Ornament oben, Verzierungen in den Ecken) ist ein Bild mit transparenter Oeffnung. Es wird so skaliert,
# dass die Oeffnung genau 256 Pixel breit ist (= Breite der Textzeilen), in der Mitte senkrecht gedehnt (dort sind nur
# die geraden Seitenlinien), das Innere wird mit Verlauf und Schein gefuellt, und das Ganze in Kacheln geschnitten.
# Die Kacheln stehen alle in der ersten Zeile (wie die Rahmenkacheln), die Zeichen werden ueber ascent nach unten
# versetzt. Das Bild ragt links und rechts ueber die 256 Pixel hinaus (der Dialogtext ist 300 Pixel breit).
# Pro Hoehe in Theme.bg_heights gibt es einen eigenen Satz Kacheln (Zeichen BG_BASE + i * BG_HEIGHT_STRIDE + ...).

BG_BASE = 0xF600
BG_HEIGHT_STRIDE = 32
BG_COLS, BG_TILE_W, BG_TILE_H = 4, 69, 85      # 4 x 69 = 276 Pixel breit, Kacheln 85 hoch (x 3 = 255 Texturpixel)
BG_LEFT, BG_TOP = -10, -31       # linke / obere Kante des Bildes in Zeilenkoordinaten (Oberkante Rahmen = 0)
BG_TEX = 3                       # Texturpixel je GUI-Pixel


def _alpha_at(rows, x, y):
    return rows[y][x][3]


def _flood_transparent(rows, sx, sy, thr=8):
    """Zusammenhaengender durchsichtiger Bereich ab (sx, sy) als bytearray (1 = dazugehoerig)."""
    h, w = len(rows), len(rows[0])
    seen = bytearray(w * h)
    if rows[sy][sx][3] > thr:
        raise SystemExit("Startpunkt der Fuellung liegt nicht in der Rahmenoeffnung")
    stack = [(sx, sy)]
    seen[sy * w + sx] = 1
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and rows[ny][nx][3] <= thr:
                seen[ny * w + nx] = 1
                stack.append((nx, ny))
    return seen


def make_background(gi, th, src, panel_h):
    """Hintergrundbild fuer die Rahmenhoehe panel_h. Liefert (Kacheln als Liste [reihe][spalte], Gesamtbild)."""
    sh, sw = len(src), len(src[0])
    seen = _flood_transparent(src, sw // 2, sh // 2)
    xs = [i % sw for i in range(sw * sh) if seen[i]]
    ys = [i // sw for i in range(sw * sh) if seen[i]]
    o_l, o_r, o_t, o_b = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    if o_r - o_l < 0.7 * sw or o_b - o_t < 0.4 * sh:
        raise SystemExit("%s: Rahmenoeffnung nicht gefunden (Rahmen nicht geschlossen?)" % th.panel_art)
    # Aussenkante des Randes in einer Spalte zwischen Eckverzierung und Ornament
    col = o_l + int(0.2 * (o_r - o_l))
    t_src = o_t
    while t_src > 0 and _alpha_at(src, col, t_src - 1) > 40:
        t_src -= 1
    k = BG_TEX * 256.0 / (o_r - o_l)                    # Texturpixel je Bildpixel
    cut1 = o_t + int(0.15 * (o_b - o_t))
    cut2 = o_b - int(0.30 * (o_b - o_t))

    tw, tht = BG_TILE_W * BG_TEX, BG_TILE_H * BG_TEX
    x0 = -BG_LEFT * BG_TEX - round(o_l * k)
    y0 = -BG_TOP * BG_TEX - round(t_src * k)
    new_w = round(sw * k)
    top = resize([r for r in src[:cut1]], new_w, round(cut1 * k))
    bot_y = (panel_h - BG_TOP) * BG_TEX - round((o_b - cut2) * k)
    mid_h = bot_y - (y0 + len(top))
    if mid_h < 10:
        raise SystemExit("%s: Mittelteil des Hintergrunds zu klein (%d)" % (th.panel_art, mid_h))
    mid = resize(src[cut1:cut2], new_w, mid_h)
    bot = resize(src[cut2:], new_w, round((sh - cut2) * k))
    # So viele Kachelreihen, dass auch die unteren Verzierungen ganz drin sind
    rows_n = max(1, -(-(bot_y + len(bot)) // tht))
    cw, ch = BG_COLS * tw, rows_n * tht
    frame = gi.blank(cw, ch)
    for rows, y in ((top, y0), (mid, y0 + len(top)), (bot, bot_y)):
        gi.blend(frame, rows, x0, y)

    # Inneres fuellen: durchsichtiger Bereich in der Mitte (leicht aufgeweitet, damit der Rand sauber ueberdeckt)
    fh, fw = len(frame), len(frame[0])
    inside = _flood_transparent(frame, fw // 2, int((panel_h / 2 - BG_TOP) * BG_TEX))
    grown = bytearray(inside)
    for _ in range(2):
        nxt = bytearray(grown)
        for i in range(fw * fh):
            if grown[i]:
                for j in (i - 1, i + 1, i - fw, i + fw):
                    if 0 <= j < fw * fh:
                        nxt[j] = 1
        grown = nxt
    alpha = [[frame[y][x][3] / 255.0 for x in range(fw)] for y in range(fh)]
    near = _blur_alpha(alpha, 9, passes=2)
    top_c, bot_c, glow_c = gi.hexc(th.c["bg_inner"][0]), gi.hexc(th.c["bg_inner"][1]), gi.hexc(th.c["bg_glow"])
    y_a, y_b = (-BG_TOP) * BG_TEX, (panel_h - BG_TOP) * BG_TEX
    cx = fw / 2.0
    for y in range(fh):
        t = min(1.0, max(0.0, (y - y_a) / float(y_b - y_a)))
        base = gi.mixc(top_c, bot_c, t)
        row = frame[y]
        for x in range(fw):
            if not grown[y * fw + x]:
                continue
            g = min(1.0, near[y][x] * 2.0) * 0.55
            vig = 0.10 * ((x - cx) / (fw / 2.0)) ** 2
            r = base[0] * (1 - g - vig) + glow_c[0] * g
            gr = base[1] * (1 - g - vig) + glow_c[1] * g
            b = base[2] * (1 - g - vig) + glow_c[2] * g
            fr, fg, fb, fa = row[x]
            a = fa / 255.0
            row[x] = (round(fr * a + r * (1 - a)), round(fg * a + gr * (1 - a)), round(fb * a + b * (1 - a)), 255)

    tiles = []
    for r in range(rows_n):
        line = []
        for c in range(BG_COLS):
            rows = [frame[r * tht + yy][c * tw:(c + 1) * tw] for yy in range(tht)]
            if all(rows[yy][-1][3] == 0 for yy in range(tht)):
                rows[0][-1] = (0, 0, 0, 1)         # unsichtbarer Pixel: damit alle Kacheln gleich breit zaehlen
            line.append(rows)
        tiles.append(line)
    return tiles, frame


# -- Titelbild: Bild aus art/<text>_title.png, sonst Pixelschrift mit Glow --

FONT5X7 = {
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    "/": "00001 00001 00010 00100 01000 10000 10000",
    "%": "11001 11010 00010 00100 01000 01011 10011",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}


def _blur_alpha(alpha, radius, passes=2):
    h, w = len(alpha), len(alpha[0])
    cur = alpha
    for _ in range(passes):
        tmp = [[0.0] * w for _ in range(h)]
        for y in range(h):
            row, acc = cur[y], 0.0
            window = 2 * radius + 1
            for x in range(-radius, radius + 1):
                if 0 <= x < w:
                    acc += row[x]
            for x in range(w):
                tmp[y][x] = acc / window
                nx, ox_ = x + radius + 1, x - radius
                if nx < w:
                    acc += row[nx]
                if ox_ >= 0:
                    acc -= row[ox_]
        out = [[0.0] * w for _ in range(h)]
        for x in range(w):
            acc = 0.0
            window = 2 * radius + 1
            for y in range(-radius, radius + 1):
                if 0 <= y < h:
                    acc += tmp[y][x]
            for y in range(h):
                out[y][x] = acc / window
                ny, oy = y + radius + 1, y - radius
                if ny < h:
                    acc += tmp[ny][x]
                if oy >= 0:
                    acc -= tmp[oy][x]
        cur = out
    return cur


def make_title(gi, th, text):
    """Titelbild: art/<text>_title.png (KI-Bild) in TITLE_H Pixeln Hoehe; ohne Bild grosse Pixelbuchstaben
    (weiss in die Themenfarbe) mit Schattenkante und Glow."""
    art = load_art(gi, text.lower() + "_title", required=False)
    if art is not None:
        w_gui = min(th.title_max_w, round(TITLE_H * len(art[0]) / len(art)))
        k = 3 if w_gui * 3 <= 256 else 2                 # Texturpixel je GUI-Pixel (Bild bleibt unter 256 Pixel)
        return fit(gi, art, w_gui * k, TITLE_H * k)
    cell = 1.5
    n = len(text)
    tw = (n * 5 + (n - 1)) * cell
    margin = 9
    width = int(math.ceil(tw + 2 * margin))
    ic = gi.Icon(width, TITLE_H, scale=2, ss=3)
    x_start = (width - tw) / 2.0
    y_start = (TITLE_H - 7 * cell) / 2.0 - 1.0
    cells = []
    for i, ch in enumerate(text):
        rows = FONT5X7[ch].split()
        for ry, line in enumerate(rows):
            for rx, bit in enumerate(line):
                if bit == "1":
                    cells.append((x_start + (i * 6 + rx) * cell, y_start + ry * cell))

    def paint_cells(dx, dy, color, grow=0.0):
        for (x, y) in cells:
            ic.paint(gi.sd_box(x + dx, y + dy, x + dx + cell, y + dy + cell, 0.0), color, grow=grow,
                     box=(x + dx - 1, y + dy - 1, x + dx + cell + 1, y + dy + cell + 1))
    paint_cells(0, 1.1, gi.hexc(th.c["title_shadow"]), grow=0.5)          # Schattenkante unten
    paint_cells(0, 0.55, gi.hexc(th.c["title_side"]))
    top, bot = gi.hexc(th.c["title_top"]), gi.hexc(th.c["title_bot"])
    y_a, y_b = y_start, y_start + 7 * cell
    paint_cells(0, 0, lambda x, y: gi.mixc(top, bot, min(1.0, max(0.0, (y - y_a) / (y_b - y_a)))))
    crisp = ic.render()

    # Glow: Alpha der Schrift weichzeichnen und in der Themenfarbe einfaerben
    h, w = len(crisp), len(crisp[0])
    alpha = [[crisp[y][x][3] / 255.0 for x in range(w)] for y in range(h)]
    blurred = _blur_alpha(alpha, 5, passes=2)
    gr, gg, gb = th.c["title_glow"]
    glow = [[(gr, gg, gb, min(255, round(255 * min(1.0, blurred[y][x] * 2.6)))) for x in range(w)]
            for y in range(h)]
    gi.blend(glow, crisp, 0, 0)
    return glow


# ── Schliessen-X, Linien, Karte, Buttons ────────────────────────────────────

def make_close(gi, th):
    s = 4
    ic = gi.Icon(CLOSE_SIZE, CLOSE_SIZE, scale=s, ss=3)
    box = gi.sd_box(0.6, 0.6, CLOSE_SIZE - 0.6, CLOSE_SIZE - 0.6, 3.0)
    ic.paint(box, gi.hexc(th.c["border"]))
    ic.paint(gi.sd_box(1.8, 1.8, CLOSE_SIZE - 1.8, CLOSE_SIZE - 1.8, 2.0),
             gi.vgrad(1, 13, gi.hexc(th.c["close_fill"][0]), gi.hexc(th.c["close_fill"][1])))
    ic.paint(gi.sd_seg((4.3, 4.3), (9.7, 9.7), 1.7), gi.hexc("#FFFFFF"))
    ic.paint(gi.sd_seg((9.7, 4.3), (4.3, 9.7), 1.7), gi.hexc("#FFFFFF"))
    return ic.render()


def make_rule(gi, th, left):
    """Trennlinie neben dem Untertitel: laeuft zum Titel hin aus (left: links, blendet nach rechts aus)."""
    w, h = 40, 4
    ic = gi.Icon(w, h, scale=2, ss=2)
    c = gi.hexc(th.c["rule"])
    if left:
        ic.paint(gi.sd_box(0, 1.5, w, 2.5, 0.0), lambda x, y: (c[0], c[1], c[2], 0.9 * (x / w) ** 1.5))
    else:
        ic.paint(gi.sd_box(0, 1.5, w, 2.5, 0.0), lambda x, y: (c[0], c[1], c[2], 0.9 * (1 - x / w) ** 1.5))
    return ic.render()


def make_card_tile(gi, th, col):
    ic = gi.Icon(gi.CARD_TILE_W, gi.CARD_H, scale=gi.PANEL_SCALE, ss=3)
    ox = col * gi.CARD_TILE_W
    w, h = gi.CARD_W, gi.CARD_H
    card = gi._shift_x(gi.sd_box(0, 0, w, h, 3.5), ox)
    ic.paint(card, gi.vgrad(0, h, gi.hexc(th.c["card_fill"][0]), gi.hexc(th.c["card_fill"][1])))
    glow = gi.hexc(th.c["glow"])
    ic.paint(card, lambda x, y: (glow[0], glow[1], glow[2], 0.35 * max(0.0, 1 - max(0.0, -card(x, y)) / 5.0) ** 2))
    inner = gi._shift_x(gi.sd_box(1.3, 1.3, w - 1.3, h - 1.3, 2.4), ox)
    line0, line1 = gi.hexc(th.c["card_line"][0]), gi.hexc(th.c["card_line"][1])
    ic.paint(gi.sub(card, inner), lambda x, y: gi.mixc(line0, line1, (x + ox) / w))
    # Itembox links
    cx = AM_CARD_ICON_CENTER_X - gi.CARD_X          # Mitte der Box in Kartenkoordinaten
    bx0, by0, bx1, by1 = cx - 12, 5, cx + 12, 29
    box = gi._shift_x(gi.sd_box(bx0, by0, bx1, by1, 3.0), ox)
    box_in = gi._shift_x(gi.sd_box(bx0 + 1, by0 + 1, bx1 - 1, by1 - 1, 2.2), ox)
    ic.paint(box, gi.hexc(th.c["box"]))
    ic.paint(box_in, gi.vgrad(by0, by1, gi.hexc(th.c["box_fill"][0]), gi.hexc(th.c["box_fill"][1])))
    return ic


def make_button_tile(gi, th, kind, primary):
    w = gi.BTN_MID_W if kind == "mid" else gi.BTN_END_W
    ic = gi.Icon(w, gi.BTN_H, scale=gi.PANEL_SCALE, ss=3)
    x0 = 0 if kind == "left" else -200
    x1 = w if kind == "right" else 200
    top, bot = AM_BTN_TOP, AM_BTN_BOTTOM
    outer = gi.sd_box(x0, top, x1, bot, 3)
    inner = gi.sd_box(x0 + 1, top + 1, x1 - 1, bot - 1, 2.2)
    c = th.c
    if primary:
        ic.paint(outer, gi.hexc(c["btn_hi_border"]))
        ic.paint(inner, gi.vgrad(top + 1, bot - 1, gi.hexc(c["btn_hi_fill"][0]), gi.hexc(c["btn_hi_fill"][1])))
        glow = gi.hexc(c["btn_hi_glow"])
        ic.paint(inner, lambda x, y: (glow[0], glow[1], glow[2], 0.30 * max(0.0, 1 - (-inner(x, y)) / 4.0) ** 2))
    else:
        ic.paint(outer, gi.hexc(c["btn_border"]))
        ic.paint(inner, gi.vgrad(top + 1, bot - 1, gi.hexc(c["btn_fill"][0]), gi.hexc(c["btn_fill"][1])))
        ic.paint(gi.inter(inner, gi.above(top + 2.0)), gi.hexc(c["btn_light"]))
    return ic


# ── Alles schreiben ─────────────────────────────────────────────────────────

def write_all(gi, pack, write_png, providers, rendered):
    """Schreibt alle Themes. providers: Font-Eintraege von fmc:icons (Amethyst haengt sich dort an, die anderen
    Themes bekommen eine eigene Font). rendered: gerenderte Icons (fuer die Itembox der Karte).
    Liefert {key: Masse fuer UiIcon.java}."""
    infos = {}
    for th in THEMES:
        if th.font == "icons":
            infos[th.key] = write_theme(gi, th, pack, write_png, providers, rendered)
        else:
            own = []
            infos[th.key] = write_theme(gi, th, pack, write_png, own, rendered)
            path = os.path.join(pack, "assets", "fmc", "font", th.font + ".json")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"providers": own}, f, indent=2)
                f.write("\n")
    # Gleiche Zeichnung -> gleicher Vorschub; das Plugin nimmt fuer diese Teile die AM_-Werte
    for key in ("panel_adv", "bg_adv", "close_adv", "rule_adv", "card_adv", "btn_end_adv", "btn_mid_adv"):
        values = {info[key] for info in infos.values() if info.get(key) is not None}
        assert len(values) == 1, "Themes haben verschiedene Vorschuebe fuer %s: %s" % (key, values)
    return infos


def write_theme(gi, th, pack, write_png, providers, rendered):
    print("Theme %s (Font fmc:%s)" % (th.key, th.font))
    ui_dir = os.path.join(pack, "assets", "fmc", "textures", "font", "ui")
    os.makedirs(ui_dir, exist_ok=True)
    for old in os.listdir(ui_dir):
        if old.startswith(th.files):
            os.remove(os.path.join(ui_dir, old))
    pre = th.files

    def out(name, rows):
        write_png(os.path.join(ui_dir, pre + name), rows)

    def prov(name, ascent, height, char, folder="ui"):
        assert ascent <= height, f"{name}: ascent {ascent} > height {height}"
        providers.append({"type": "bitmap", "file": f"fmc:font/{folder}/{pre}{name}", "ascent": ascent,
                          "height": height, "chars": [char]})

    info = {"theme": th}
    u, cols, rows_max = gi.PANEL_UNIT, gi.PANEL_COLS, gi.PANEL_ROWS_MAX

    # Rahmen
    tiles = []
    for kind in ("top", "mid", "bot"):
        for c in range(cols):
            rows = frame_tile(gi, th, kind, c).render()
            tiles.append(rows)
            out(f"panel_{kind}_{c}.png", rows)
    for c in range(cols):
        prov(f"panel_top_{c}.png", gi.PANEL_ASCENT, u, chr(AM_TOP_BASE + c))
    for r in range(1, rows_max):
        for kind, base in (("mid", AM_MID_BASE), ("bot", AM_BOT_BASE)):
            for c in range(cols):
                prov(f"panel_{kind}_{c}.png", gi.PANEL_ASCENT - r * u, u, chr(base + r * cols + c))
    for v in range(gi.PANEL_BOT_VAR_MIN, u - 1):
        for c in range(cols):
            rows = frame_tile(gi, th, "bot", c, v).render()
            tiles.append(rows)
            out(f"panel_botv_{v}_{c}.png", rows)
        for r in range(1, rows_max):
            for c in range(cols):
                idx = ((v - gi.PANEL_BOT_VAR_MIN) * rows_max + r) * cols + c
                prov(f"panel_botv_{v}_{c}.png", gi.PANEL_ASCENT - r * u, u, chr(AM_BOT_VAR_BASE + idx))
    info["panel_adv"] = gi.single_advance(tiles, u, th.key + "-Panel")

    # Eckverzierungen (oben klein, unten gross)
    top_l = make_crystal_top(gi, th)
    out("crystal_top_l.png", top_l)
    out("crystal_top_r.png", flip(top_l))
    prov("crystal_top_l.png", gi.PANEL_ASCENT - CRY_TOP_Y, CRY_TOP_H, AM_CRYSTAL_TOP_L)
    prov("crystal_top_r.png", gi.PANEL_ASCENT - CRY_TOP_Y, CRY_TOP_H, AM_CRYSTAL_TOP_R)
    info["crystal_top_adv"] = gi.glyph_advance(top_l, CRY_TOP_H)
    bot_l = make_crystal_bottom(gi, th)
    out("crystal_bot_l.png", bot_l)
    out("crystal_bot_r.png", flip(bot_l))
    height_max = rows_max * u
    for yb in range(AM_CRYSTAL_BOT_MIN, height_max + 1):
        ascent = gi.PANEL_ASCENT - (yb + CRY_BOT_OVER - CRY_BOT_H)
        base = AM_CRYSTAL_BOT_BASE + 2 * (yb - AM_CRYSTAL_BOT_MIN)
        prov("crystal_bot_l.png", ascent, CRY_BOT_H, chr(base))
        prov("crystal_bot_r.png", ascent, CRY_BOT_H, chr(base + 1))
    info["crystal_bot_adv"] = gi.glyph_advance(bot_l, CRY_BOT_H)

    # Hintergrundbilder fuer Menues fester Hoehe (nur mit Rahmenbild)
    info["bg"] = []                     # (Hoehe, Reihen, Basiszeichen)
    info["bg_adv"] = None
    bg_canvas = {}
    src = load_art(gi, th.panel_art, required=th.art_required)
    if src is None:
        print("  %s: %s.png fehlt, Kachelrahmen statt Hintergrundbild" % (th.key, th.panel_art))
    bg_all = []
    for i, panel_h in enumerate(th.bg_heights if src is not None else []):
        assert i * BG_HEIGHT_STRIDE + BG_HEIGHT_STRIDE <= 0x200, "zu viele Hintergrundhoehen"
        try:
            bg_tiles, canvas = make_background(gi, th, src, panel_h)
        except SystemExit as e:
            if th.art_required:
                raise
            # Unbrauchbares KI-Bild (z. B. Rahmen nicht geschlossen): lieber Kachelrahmen als ein kaputter Build
            print("  WARNUNG %s: %s -> Kachelrahmen statt Hintergrundbild" % (th.key, e))
            break
        assert len(bg_tiles) * BG_COLS <= BG_HEIGHT_STRIDE, "Hintergrund zu hoch"
        base = BG_BASE + i * BG_HEIGHT_STRIDE
        for r, line in enumerate(bg_tiles):
            for c, tile in enumerate(line):
                out(f"bg_{panel_h}_{r}_{c}.png", tile)
                prov(f"bg_{panel_h}_{r}_{c}.png", gi.PANEL_ASCENT - (BG_TOP + BG_TILE_H * r), BG_TILE_H,
                     chr(base + r * BG_COLS + c))
                bg_all.append(tile)
        info["bg"].append((panel_h, len(bg_tiles), base))
        bg_canvas[panel_h] = canvas
        print("  Hintergrund %d Pixel: %d Kachelreihen" % (panel_h, len(bg_tiles)))
    if bg_all:
        info["bg_adv"] = gi.single_advance(bg_all, BG_TILE_H, th.key + "-Hintergrund")

    # Ornament, Titel, X, Linien, Karte, Buttons
    orn = make_ornament(gi, th)
    out("ornament.png", orn)
    prov("ornament.png", gi.PANEL_ASCENT + ORN_ABOVE, ORN_H, AM_ORNAMENT)
    info["ornament_adv"] = gi.glyph_advance(orn, ORN_H)
    info["titles"] = []
    title_rows = []
    for i, text in enumerate(th.titles):
        rows = make_title(gi, th, text)
        title_rows.append(rows)
        out(f"title_{text.lower()}.png", rows)
        prov(f"title_{text.lower()}.png", gi.PANEL_ASCENT - TITLE_TOP, TITLE_H, chr(AM_TITLE_BASE + i))
        info["titles"].append((text, chr(AM_TITLE_BASE + i), gi.glyph_advance(rows, TITLE_H)))
    close = make_close(gi, th)
    out("close.png", close)
    prov("close.png", gi.PANEL_ASCENT - CLOSE_Y, CLOSE_SIZE, AM_CLOSE)
    info["close_adv"] = gi.glyph_advance(close, CLOSE_SIZE)
    rule_l = make_rule(gi, th, True)
    out("rule_l.png", rule_l)
    out("rule_r.png", make_rule(gi, th, False))
    prov("rule_l.png", 4, 4, AM_RULE_L)
    prov("rule_r.png", 4, 4, AM_RULE_R)
    info["rule_adv"] = gi.glyph_advance(rule_l, 4)
    # Symbol in der Itembox der Karte (Bild des Icons, 18 Pixel gross, mittig in der Karte)
    providers.append({"type": "bitmap", "file": f"fmc:font/icons/{th.card_icon}.png", "ascent": -7, "height": 18,
                      "chars": [AM_CARD_CHEST]})
    info["card_glyph_adv"] = gi.glyph_advance(rendered[th.card_icon], 18)

    card = []
    for c in range(gi.CARD_COLS):
        rows = make_card_tile(gi, th, c).render()
        card.append(rows)
        out(f"card_{c}.png", rows)
        prov(f"card_{c}.png", gi.CARD_ASCENT, gi.CARD_H, chr(AM_CARD_BASE + c))
    info["card_adv"] = gi.single_advance(card, gi.CARD_H, th.key + "-Karte")

    btn = {}
    for primary, chars, prefix in ((False, AM_BTN, "btn"), (True, AM_BTN_HI, "btn_hi")):
        for kind, char in zip(("left", "mid", "right"), chars):
            rows = make_button_tile(gi, th, kind, primary).render()
            btn[(primary, kind)] = rows
            out(f"{prefix}_{kind}.png", rows)
            prov(f"{prefix}_{kind}.png", gi.BTN_ASCENT, gi.BTN_H, char)
    info["btn_end_adv"] = gi.single_advance([btn[(p, "left")] for p in (False, True)]
                                            + [btn[(p, "right")] for p in (False, True)], gi.BTN_H,
                                            th.key + "-Button-Enden")
    info["btn_mid_adv"] = gi.single_advance([btn[(p, "mid")] for p in (False, True)], gi.BTN_H,
                                            th.key + "-Button-Mitte")

    write_preview(gi, th, os.path.join(gi.ROOT, "dist", "preview_%s.png" % th.key), {
        "orn": orn, "top_l": top_l, "bot_l": bot_l, "close": close, "rule_l": rule_l,
        "title": title_rows[0] if title_rows else None, "card": card, "btn": btn, "bg": bg_canvas})
    return info


def preview_height(n_buttons):
    """Rahmenhoehe eines Theme-Menues mit Banner, Karte und n Buttons in 2 Spalten (wie PanelMenu)."""
    rows = -(-n_buttons // 2)
    last_label = AM_HEADER_LINES + 4 + AM_BTN_LABEL_OFFSET + 3 * (rows - 1)
    return last_label * 9 + AM_BTN_BELOW_LABEL + 6


def write_preview(gi, th, path, parts):
    """Zeichnet das Menue des Themes aus den fertigen Bildern (Naeherung: Text in einer einfachen Pixelschrift statt
    der Minecraft-Schrift, Positionen wie in PanelMenu). Nur zum Anschauen, landet in dist/."""
    S, W, u = 4, gi.PANEL_W, gi.PANEL_UNIT
    pv = th.preview
    labels = pv["buttons"]
    fh = preview_height(len(labels))
    pad = AM_PAD_LINES * 9
    ox = 12                                    # Rand links/rechts: das Hintergrundbild ragt ueber die 256 Pixel hinaus
    sheet = gi.blank((W + 2 * ox) * S, (pad + fh + 14) * S, (11, 8, 22, 255))

    def put(rows, tex_per_gui, x, y):
        tw, th_ = round(len(rows[0]) * S / tex_per_gui), round(len(rows) * S / tex_per_gui)
        gi.blend(sheet, resize(rows, tw, th_), round((x + ox) * S), round(y * S))

    def rect(x, y, w, h, color):
        for yy in range(round(y * S), round((y + h) * S)):
            for xx in range(round((x + ox) * S), round((x + ox + w) * S)):
                if 0 <= yy < len(sheet) and 0 <= xx < len(sheet[0]):
                    sheet[yy][xx] = color

    def text(s, x, y, color=(255, 255, 255, 255), spacing=1):
        for ch in s.upper():
            pat = FONT5X7.get(ch, FONT5X7[" "]).split()
            for cy, line in enumerate(pat):
                for cx, bit in enumerate(line):
                    if bit == "1":
                        rect(x + cx, y + cy, 1, 1, color)
            x += 6 + spacing
        return x

    def icon(name, x, y, size=14):
        path_ = os.path.join(gi.ICON_DIR, name + ".png")
        with open(path_, "rb") as f:
            put(pngread.png_read(f.read()), 32.0 / size, x, y)

    # Rahmen
    rows_n, v = (fh - 1) // u + 1, (fh - 1) % u
    cache = {}
    bg = parts["bg"].get(fh)
    if bg:
        put(bg, BG_TEX, BG_LEFT, pad + BG_TOP)
        rows_n = 0
    for r in range(rows_n):
        kind = "top" if r == 0 else ("mid" if r < rows_n - 1 else "bot")
        for c in range(gi.PANEL_COLS):
            key = (kind, c)
            if key not in cache:
                cache[key] = frame_tile(gi, th, kind, c, v if kind == "bot" and v != u - 1 else None).render()
            put(cache[key], gi.PANEL_SCALE, c * gi.PANEL_TILE_W, pad + r * u)

    # Karte
    card_top = pad + AM_HEADER_LINES * 9 + 6
    for c, rows in enumerate(parts["card"]):
        put(rows, gi.PANEL_SCALE, gi.CARD_X + c * gi.CARD_TILE_W, card_top)
    icon(th.card_icon, AM_CARD_ICON_CENTER_X - 9, card_top + 8, 18)
    base = pad + AM_HEADER_LINES * 9 + 9
    text(pv["card"][0], AM_NAME_X, base + 1)
    sub_c = gi.hexc(th.c["subtitle"])
    gray = (170, 170, 170, 255)
    if pv["bar"]:
        icon(th.card_icon, AM_NAME_X, base + 8, 9)
        end = text("0", AM_NAME_X + 11, base + 10, (255, 255, 85, 255))
        text("/ 64", end + 2, base + 10, gray)
        text("0%", 240 - 14, base + 10)
        rect(AM_NAME_X, base + 20, 192, 4, (58, 53, 80, 255))
    else:
        text(pv["card"][1], AM_NAME_X, base + 10, gray)

    # Buttons (Raster wie in PanelMenu: 2 Spalten, letzte Reihe mittig, letzter Button hervorgehoben)
    for i, (ic_name, label) in enumerate(labels):
        row, col = i // 2, i % 2
        single = i == len(labels) - 1 and len(labels) % 2 == 1
        x = (W - 118) // 2 if single else 9 + col * 120
        top = pad + (AM_HEADER_LINES + 4 + AM_BTN_LABEL_OFFSET + 3 * row - 1) * 9
        primary = i == len(labels) - 1 and pv.get("primary_last", False)
        for kind, dx in (("left", 0), ("right", 59)):
            put(parts["btn"][(primary, kind)], gi.PANEL_SCALE, x + dx, top)
        icon(ic_name, x + 8, top + 9 - 1)
        text(label, x + 8 + 18, top + 9 + 1)
        icon("chevron", x + 118 - 8 - 8, top + 9 + 0, 9)

    # Verzierungen (mit Hintergrundbild stecken Ecken und Ornament schon darin)
    if not bg:
        put(parts["top_l"], CRY_TEX, 2, pad + CRY_TOP_Y)
        put(flip(parts["top_l"]), CRY_TEX, W - 2 - CRY_TOP_W, pad + CRY_TOP_Y)
        put(parts["bot_l"], CRY_TEX, 1, pad + fh + CRY_BOT_OVER - CRY_BOT_H)
        put(flip(parts["bot_l"]), CRY_TEX, W - 1 - CRY_BOT_W, pad + fh + CRY_BOT_OVER - CRY_BOT_H)
        put(parts["orn"], ORN_TEX, (W - ORN_W) / 2, pad - ORN_ABOVE)
    if parts["title"] is not None:
        put(parts["title"], len(parts["title"]) / TITLE_H, (W - len(parts["title"][0]) * TITLE_H / len(parts["title"])) / 2,
            pad + TITLE_TOP)
    put(parts["close"], 4, 226, pad + CLOSE_Y)

    # Untertitel mit Linien
    sub = pv["subtitle"]
    sw = len(sub) * 7 - 1
    start = (W - sw) // 2
    put(parts["rule_l"], 2, start - 46, pad + 27 + 3)
    put(flip(parts["rule_l"]), 2, start + sw + 6, pad + 27 + 3)
    text(sub, start, pad + 27 + 1, (round(sub_c[0]), round(sub_c[1]), round(sub_c[2]), 255))
    gi.write_png(path, sheet)


# ── Java ────────────────────────────────────────────────────────────────────

def lit(c):
    return "\"\\u%04X\"" % ord(c)


def _const(name, value, doc=None):
    out = []
    if doc:
        out.append("    /** %s */" % doc)
    out.append("    public static final int %s = %d;" % (name, value))
    return out


def _bg_lines(p, info):
    """Hintergrundbilder eines Themes: Rahmenhoehen, Kachelreihen und Basiszeichen (gleiche Reihenfolge)."""
    hs = ", ".join(str(h) for h, _, _ in info["bg"])
    rs = ", ".join(str(r) for _, r, _ in info["bg"])
    bs = ", ".join("0x%04X" % b for _, _, b in info["bg"])
    return ["    /** Rahmenhoehen mit fertigem Hintergrundbild; dazu Kachelreihen und Basiszeichen (Zeichen = Basis + "
            "Reihe * AM_BG_COLS + Spalte). */",
            "    public static final int[] %s_BG_HEIGHTS = {%s};" % (p, hs),
            "    public static final int[] %s_BG_ROWS = {%s};" % (p, rs),
            "    public static final int[] %s_BG_BASES = {%s};" % (p, bs)]


def _titles(p, info):
    L = []
    for text, char, adv in info["titles"]:
        L.append("    /** Titelbild \"%s\". */" % text)
        L.append("    public static final String %s_TITLE_%s = %s;" % (p, text.upper(), lit(char)))
        L += _const("%s_TITLE_%s_ADVANCE" % (p, text.upper()), adv)
    return L


def java_lines(infos):
    """Konstanten fuer UiIcon.java (im Enum-Rumpf)."""
    info = infos[AMETHYST.key]
    const = _const
    L = ["", "    // ── Panel-Themes (siehe tools/amethyst_theme.py); Amethyst liegt in fmc:icons ──"]
    L.append("    public static final char AM_TOP_BASE = (char) 0x%04X;" % AM_TOP_BASE)
    L.append("    public static final char AM_MID_BASE = (char) 0x%04X;" % AM_MID_BASE)
    L.append("    public static final char AM_BOT_BASE = (char) 0x%04X;" % AM_BOT_BASE)
    L.append("    public static final char AM_BOT_VAR_BASE = (char) 0x%04X;" % AM_BOT_VAR_BASE)
    L += const("AM_PANEL_TILE_ADVANCE", info["panel_adv"])
    L += const("AM_BG_COLS", BG_COLS)
    L += const("AM_BG_TILE_W", BG_TILE_W, "Breite einer Kachel in Pixeln (Spalte c steht bei AM_BG_LEFT + c * AM_BG_TILE_W).")
    L += const("AM_BG_TILE_ADVANCE", info["bg_adv"])
    L += const("AM_BG_LEFT", BG_LEFT, "Linke Kante des Bildes (negativ: es ragt links ueber die 256 Pixel hinaus).")
    L += _bg_lines("AM", info)
    L.append("    /** Unterer Eckkristall: Basis + 2 * (Panelhoehe - AM_CRYSTAL_BOT_MIN) + Seite (0 links, 1 rechts). */")
    L.append("    public static final char AM_CRYSTAL_BOT_BASE = (char) 0x%04X;" % AM_CRYSTAL_BOT_BASE)
    L += const("AM_CRYSTAL_BOT_MIN", AM_CRYSTAL_BOT_MIN)
    L += const("AM_CRYSTAL_BOT_ADVANCE", info["crystal_bot_adv"])
    L += const("AM_CRYSTAL_BOT_W", CRY_BOT_W)
    L.append("    public static final String AM_CRYSTAL_TOP_L = %s;" % lit(AM_CRYSTAL_TOP_L))
    L.append("    public static final String AM_CRYSTAL_TOP_R = %s;" % lit(AM_CRYSTAL_TOP_R))
    L += const("AM_CRYSTAL_TOP_ADVANCE", info["crystal_top_adv"])
    L += const("AM_CRYSTAL_TOP_W", CRY_TOP_W)
    L.append("    public static final String AM_ORNAMENT = %s;" % lit(AM_ORNAMENT))
    L += const("AM_ORNAMENT_ADVANCE", info["ornament_adv"])
    L += const("AM_ORNAMENT_W", ORN_W)
    L.append("    public static final String AM_CLOSE = %s;" % lit(AM_CLOSE))
    L += const("AM_CLOSE_ADVANCE", info["close_adv"])
    L.append("    public static final String AM_RULE_L = %s;" % lit(AM_RULE_L))
    L.append("    public static final String AM_RULE_R = %s;" % lit(AM_RULE_R))
    L += const("AM_RULE_ADVANCE", info["rule_adv"])
    L += const("AM_RULE_W", 40)
    L.append("    /** Truhe (18 Pixel) in der Itembox der Karte; Vorschub wie das Icon CHEST in 18 Pixeln Hoehe. */")
    L.append("    public static final String AM_CARD_CHEST = %s;" % lit(AM_CARD_CHEST))
    L += const("AM_CARD_CHEST_ADVANCE", info["card_glyph_adv"])
    L.append("    public static final char AM_CARD_BASE = (char) 0x%04X;" % AM_CARD_BASE)
    L += const("AM_CARD_TILE_ADVANCE", info["card_adv"])
    L.append("    public static final String AM_BTN_LEFT = %s;" % lit(AM_BTN[0]))
    L.append("    public static final String AM_BTN_MID = %s;" % lit(AM_BTN[1]))
    L.append("    public static final String AM_BTN_RIGHT = %s;" % lit(AM_BTN[2]))
    L.append("    public static final String AM_BTN_HI_LEFT = %s;" % lit(AM_BTN_HI[0]))
    L.append("    public static final String AM_BTN_HI_MID = %s;" % lit(AM_BTN_HI[1]))
    L.append("    public static final String AM_BTN_HI_RIGHT = %s;" % lit(AM_BTN_HI[2]))
    L += const("AM_BTN_END_ADVANCE", info["btn_end_adv"])
    L += const("AM_BTN_MID_ADVANCE", info["btn_mid_adv"])
    L += const("AM_BTN_BELOW_LABEL", AM_BTN_BELOW_LABEL, "Unterkante des Buttons unter der Oberkante der Textzeile.")
    L += const("AM_PAD_LINES", AM_PAD_LINES, "Leerzeilen ueber dem Rahmen (Platz fuer das Ornament).")
    L += const("AM_HEADER_LINES", AM_HEADER_LINES, "Kopfzeilen mit Banner (Ornament, Titel, Untertitel).")
    L += const("AM_NAME_X", AM_NAME_X, "Textbeginn in der Karte.")
    L += const("AM_CARD_ICON_CENTER_X", AM_CARD_ICON_CENTER_X, "Mitte der Itembox in der Karte.")
    L += const("AM_CENTER_PAD_LINES", AM_CENTER_PAD_LINES)
    L += const("AM_BTN_LABEL_OFFSET", AM_BTN_LABEL_OFFSET, "Zeilen von der Karte bis zur Beschriftung der ersten Button-Reihe.")
    L += const("AM_CRYSTAL_TOP_Y", CRY_TOP_Y, "Oberkante der Seitenkristalle unter der Rahmenoberkante.")
    L += const("AM_CRYSTAL_BOT_H", CRY_BOT_H)
    L += const("AM_CRYSTAL_BOT_OVER", CRY_BOT_OVER, "So weit ragt der untere Kristall ueber die Unterkante.")
    L.append("    /** Farbe des Untertitels im Banner. */")
    L.append("    public static final int AM_SUBTITLE_COLOR = 0x%s;" % AMETHYST.c["subtitle"].lstrip("#").upper())
    L += _titles("AM", info)

    for th in THEMES:
        if th is AMETHYST:
            continue
        p, ti = th.java, infos[th.key]
        L += ["", "    // ── Theme \"%s\" (Font fmc:%s, gleiche Zeichen wie AM_; hier nur, was abweicht) ──" % (th.key, th.font)]
        L += _bg_lines(p, ti)
        L += const("%s_CRYSTAL_TOP_ADVANCE" % p, ti["crystal_top_adv"])
        L += const("%s_CRYSTAL_BOT_ADVANCE" % p, ti["crystal_bot_adv"])
        L += const("%s_ORNAMENT_ADVANCE" % p, ti["ornament_adv"])
        L.append("    /** Icon \"%s\" (18 Pixel) in der Itembox der Karte. */" % th.card_icon)
        L.append("    public static final String %s_CARD_GLYPH = %s;" % (p, lit(AM_CARD_CHEST)))
        L += const("%s_CARD_GLYPH_ADVANCE" % p, ti["card_glyph_adv"])
        L.append("    public static final int %s_SUBTITLE_COLOR = 0x%s;" % (p, th.c["subtitle"].lstrip("#").upper()))
        L += _titles(p, ti)
    return L
