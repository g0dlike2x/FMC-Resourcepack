#!/usr/bin/env python3
"""
Amethyst-Theme fuer PanelMenu (Rahmen mit lila Glow, Kristalle, Banner mit Truhe, Karte mit Itembox,
dunkle Buttons mit lila Hervorhebung). Erstes Menue im Theme: /lager.

Wird von generate_icons.py mit aufgerufen (write_all). Nur Standardbibliothek. Das Modul bekommt
generate_icons als Parameter "gi" uebergeben (Zeichenhilfen, Panel-Masse), damit es keine zirkulaere
Abhaengigkeit gibt.

Alle Dateien liegen in assets/fmc/textures/font/ui/ und beginnen mit "am_".
Zeichen (Private Use, Font fmc:icons):
    U+ED00..U+F15F   Rahmenkacheln (oben / Mitte / unten / unten mit hoeher liegender Randlinie)
    U+F200..U+F40D   untere Eckkristalle, je Panelhoehe ein Zeichen links und rechts
    U+F500..U+F507   Ornament (Truhe), Seitenkristalle, Schliessen-X, Trennlinien, Truhe fuer die Karte
    U+F510..U+F513   Karte           U+F520..U+F525  Buttons (normal / hervorgehoben)
    U+F580..         Titelbilder (siehe TITLES)

Aufbau des Menues (alles relativ zur Oberkante des Rahmens, 1 Zeile = 9 Pixel):
    AM_PAD_LINES Leerzeilen ueber dem Rahmen: Platz fuer die Truhe, die oben aus dem Rahmen ragt
    AM_HEADER_LINES Kopfzeilen: Truhe, Titelbild, Untertitel; danach die Karte
"""
import math
import os

# ── Zeichen ─────────────────────────────────────────────────────────────────
AM_TOP_BASE, AM_MID_BASE, AM_BOT_BASE, AM_BOT_VAR_BASE = 0xED00, 0xED10, 0xED80, 0xEE00
AM_CRYSTAL_BOT_BASE = 0xF200        # + 2 * (Panelhoehe - AM_CRYSTAL_BOT_MIN) + Seite (0 links, 1 rechts)
AM_CRYSTAL_BOT_MIN = 26
AM_ORNAMENT = "\uF500"
AM_CRYSTAL_TOP_L, AM_CRYSTAL_TOP_R = "\uF502", "\uF503"
AM_CLOSE = "\uF504"
AM_RULE_L, AM_RULE_R = "\uF505", "\uF506"
AM_CARD_CHEST = "\uF507"
AM_CARD_BASE = 0xF510
AM_BTN = ("\uF520", "\uF521", "\uF522")        # links, Mitte, rechts
AM_BTN_HI = ("\uF523", "\uF524", "\uF525")
AM_TITLE_BASE = 0xF580
TITLES = ["LAGER"]                              # je Titel ein Bild; Zeichen = AM_TITLE_BASE + Index

# ── Masse (GUI-Pixel) ───────────────────────────────────────────────────────
AM_PAD_LINES = 2
AM_HEADER_LINES = 4
AM_NAME_X = 48                 # Textbeginn in der Karte (rechts neben der Itembox)
AM_CARD_ICON_CENTER_X = 26     # Mitte der Itembox
AM_BTN_TOP, AM_BTN_BOTTOM = 3.0, 24.0           # sichtbarer Teil des Buttons in der 27 Pixel hohen Kachel
AM_BTN_BELOW_LABEL = 15        # Unterkante des Buttons unter der Oberkante der Textzeile (24 - 9)
AM_CENTER_PAD_LINES = 2

ORN_W, ORN_H, ORN_TEX = 84, 40, 3          # Ornament: Breite, Hoehe in GUI-Pixeln, Texturpixel je GUI-Pixel
ORN_ABOVE = 18                             # so weit ragt die Truhe ueber den Rahmen
CRY_TOP_W, CRY_TOP_H, CRY_TOP_Y = 14, 26, 14
CRY_BOT_W, CRY_BOT_H, CRY_BOT_OVER = 24, 26, 2
CRY_TEX = 4
TITLE_H, TITLE_TOP = 26, 4                 # Titelbild: Hoehe, Oberkante im Rahmen
CLOSE_SIZE = 14

# ── Farben ──────────────────────────────────────────────────────────────────
FILL = "#130D27"
BORDER = "#A06BFF"
BORDER2 = "#4A2F96"
GLOW = "#7B3FE4"


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

def frame_tile(gi, kind, col, v=None):
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
    ic.paint(outer, gi.hexc(FILL))
    glow = gi.hexc(GLOW)

    def glow_fn(x, y):
        d = max(0.0, -outer(x, y))
        return (glow[0], glow[1], glow[2], 0.42 * max(0.0, 1.0 - d / 7.0) ** 2)
    ic.paint(outer, glow_fn)
    ic.paint(gi.sub(outer, inner), gi.hexc(BORDER))
    ic.paint(gi.sub(box(2.6, 2.0), box(3.4, 1.4)), gi.hexc(BORDER2, 0.85))
    return ic


# ── Kristalle ───────────────────────────────────────────────────────────────

def draw_crystal(gi, ic, bx, by, w, h, lean=0.0):
    """Ein Kristall: Fuss bei (bx, by), Breite w, Hoehe h, Spitze um lean seitlich versetzt."""
    bl, br = (bx - w / 2, by), (bx + w / 2, by)
    ls = (bx - w / 2 + lean * 0.35, by - h * 0.70)
    rs = (bx + w / 2 + lean * 0.35, by - h * 0.70)
    tip = (bx + lean, by - h)
    ridge = (bx, by)
    box = _bbox_poly([bl, br, ls, rs, tip], 2.5)
    ic.paint(gi.sd_poly([bl, ls, tip, rs, br]), gi.hexc("#1E0B4A"), grow=0.9, box=box)
    ic.paint(gi.sd_poly([bl, ls, tip, ridge]), gi.vgrad(by - h, by, gi.hexc("#E6CCFF"), gi.hexc("#9A62F5")), box=box)
    ic.paint(gi.sd_poly([ridge, tip, rs, br]), gi.vgrad(by - h, by, gi.hexc("#A877FF"), gi.hexc("#4F27B0")), box=box)
    ic.paint(gi.sd_seg(tip, ridge, 0.6), gi.hexc("#F4E8FF", 0.75), box=box)
    ic.paint(gi.sd_seg(ls, tip, 0.5), gi.hexc("#FFFFFF", 0.55), box=box)


def make_crystal_top(gi):
    ic = gi.Icon(CRY_TOP_W, CRY_TOP_H, scale=CRY_TEX, ss=3)
    draw_crystal(gi, ic, 4.0, 25.0, 5.0, 10.0, -1.5)
    draw_crystal(gi, ic, 8.5, 25.0, 8.0, 23.0, 0.8)
    return ic.render()


def make_crystal_bottom(gi):
    ic = gi.Icon(CRY_BOT_W, CRY_BOT_H, scale=CRY_TEX, ss=3)
    draw_crystal(gi, ic, 4.5, 25.0, 6.0, 11.0, -2.5)
    draw_crystal(gi, ic, 19.0, 25.0, 6.0, 14.0, 1.5)
    draw_crystal(gi, ic, 11.5, 25.0, 9.0, 23.0, -1.0)
    return ic.render()


# ── Ornament (Truhe mit Steinen und Ranken) ─────────────────────────────────

def make_ornament(gi):
    ic = gi.Icon(ORN_W, ORN_H, scale=ORN_TEX, ss=3)
    cx = ORN_W / 2.0
    hexc = gi.hexc

    # Lila Schein hinter der Truhe
    glow = hexc("#9B5CFF")
    ic.paint(gi.sd_circle(cx, 17, 27),
             lambda x, y: (glow[0], glow[1], glow[2],
                           0.30 * max(0.0, 1.0 - math.hypot(x - cx, (y - 17) * 1.3) / 27.0) ** 2),
             box=(cx - 28, 0, cx + 28, ORN_H))

    stone = (hexc("#9C97AE"), hexc("#5E5A70"))
    seam = hexc("#2A2736", 0.6)

    def block(x0, y0, x1, y1):
        fancy(gi, ic, gi.sd_box(x0, y0, x1, y1, 1.2), stone, (x0, y0, x1, y1), outline=hexc("#24212F"), out=0.9)
        ym = (y0 + y1) / 2
        ic.paint(gi.sd_seg((x0 + 0.8, ym), (x1 - 0.8, ym), 0.7), seam, box=(x0, ym - 1, x1, ym + 1))
        ic.paint(gi.sd_seg((x0 + (x1 - x0) * 0.4, y0 + 0.8), (x0 + (x1 - x0) * 0.4, ym), 0.7), seam,
                 box=(x0, y0, x1, ym))
        ic.paint(gi.sd_seg((x0 + (x1 - x0) * 0.65, ym), (x0 + (x1 - x0) * 0.65, y1 - 0.8), 0.7), seam,
                 box=(x0, ym, x1, y1))

    # Steine links und rechts der Truhe (hinterer Block zuerst)
    block(cx - 31, 8, cx - 20, 29)
    block(cx - 40, 18, cx - 27, 29)
    block(cx + 20, 10, cx + 31, 29)
    block(cx + 27, 19, cx + 40, 29)

    # Truhe
    wood_body = (hexc("#5E3A22"), hexc("#34200F"))
    wood_lid = (hexc("#7A4A2C"), hexc("#412615"))
    gold = (hexc("#FFE08A"), hexc("#C98A1C"))
    gold_out = hexc("#5A3500")
    fancy(gi, ic, gi.sd_box(cx - 19, 13, cx + 19, 29, 2.0), wood_body, (cx - 19, 13, cx + 19, 29),
          outline=hexc("#1A0F08"), out=1.0)
    fancy(gi, ic, gi.sd_box(cx - 19, 4, cx + 19, 16, 6.0), wood_lid, (cx - 19, 4, cx + 19, 16),
          outline=hexc("#1A0F08"), out=1.0)
    # Holzmaserung
    for yy in (19.0, 23.0, 26.5):
        ic.paint(gi.sd_seg((cx - 17, yy), (cx + 17, yy), 0.5), hexc("#150A04", 0.35),
                 box=(cx - 18, yy - 1, cx + 18, yy + 1))
    # Goldbeschlag: Querband, Seitenstreifen, Lidkante
    fancy(gi, ic, gi.sd_box(cx - 19.4, 13.2, cx + 19.4, 16.2, 0.8), gold, (cx - 20, 13, cx + 20, 16.5),
          outline=gold_out, out=0.8, rim=False)
    for sx in (cx - 14.5, cx + 14.5):
        fancy(gi, ic, gi.sd_box(sx - 1.7, 5.0, sx + 1.7, 28.6, 0.7), gold, (sx - 2, 4.5, sx + 2, 29),
              outline=gold_out, out=0.8, rim=False)
    ic.paint(gi.sd_seg((cx - 14, 5.2), (cx + 14, 5.2), 0.8), hexc("#FFE9A8", 0.8), box=(cx - 15, 4, cx + 15, 7))
    # Schloss mit leuchtendem Schluesselloch
    fancy(gi, ic, gi.sd_box(cx - 4.5, 10.5, cx + 4.5, 21.0, 1.6), gold, (cx - 5, 10, cx + 5, 21.5),
          outline=gold_out, out=0.9)
    halo = hexc("#FFF3B0")
    ic.paint(gi.sd_circle(cx, 15.5, 3.2),
             lambda x, y: (halo[0], halo[1], halo[2], 0.55 * max(0.0, 1 - math.hypot(x - cx, y - 15.5) / 3.2)),
             box=(cx - 4, 11, cx + 4, 20))
    ic.paint(gi.sd_circle(cx, 15.2, 1.3), hexc("#3A2200"), box=(cx - 2, 13, cx + 2, 17))
    ic.paint(gi.sd_box(cx - 0.6, 15.4, cx + 0.6, 18.4, 0.2), hexc("#3A2200"), box=(cx - 2, 15, cx + 2, 19))

    # Ranken und Blaetter
    leaf = (hexc("#6CC46A"), hexc("#2E7A3A"))
    leaf_out = hexc("#14391C")
    vine = hexc("#2A6B32")
    vines = [
        [(cx - 33, 7), (cx - 26, 5), (cx - 20, 6), (cx - 12, 3.5)],
        [(cx + 33, 9), (cx + 26, 7), (cx + 19, 5), (cx + 11, 3)],
        [(cx - 36, 17), (cx - 38, 22), (cx - 36, 27)],
        [(cx + 36, 18), (cx + 38, 23), (cx + 35, 28)],
    ]
    for line in vines:
        for a, b in zip(line, line[1:]):
            ic.paint(gi.sd_seg(a, b, 0.9), vine, box=_bbox_poly([a, b], 1.5))
    leaves = [(-34, 7.5, -35), (-29, 4.5, 25), (-23, 7.5, -20), (-17, 5, 30), (-12, 2.8, -25), (-6.5, 2.2, 15),
              (-37, 15, 50), (-38.5, 21, -40), (-36, 26, 40), (-26, 22, 65), (-24, 14, -50),
              (34, 9.5, 30), (28, 6.5, -25), (22, 5, 20), (15, 3.2, -30), (9, 2.2, 20),
              (37.5, 17, -50), (38.5, 22, 45), (35.5, 27.5, -40), (30, 23, -65), (25, 15, 50)]
    for dx, y, ang in leaves:
        lx = cx + dx
        shape = gi.rot(gi.ellipse(lx, y, 3.4, 1.9), ang, lx, y)
        fancy(gi, ic, shape, leaf, (lx - 4.5, y - 4.5, lx + 4.5, y + 4.5), outline=leaf_out, out=0.7)
        ic.paint(gi.rot(gi.sd_seg((lx - 2.2, y), (lx + 2.2, y), 0.4), ang, lx, y), hexc("#BFF0B0", 0.7),
                 box=(lx - 4, y - 4, lx + 4, y + 4))
    return ic.render()


# ── Titelbild (Pixelschrift mit Glow) ───────────────────────────────────────

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


def make_title(gi, text):
    """Titelbild: grosse Pixelbuchstaben (weiss ins Lila) mit Schattenkante und Glow."""
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
    paint_cells(0, 1.1, gi.hexc("#3B1A8C"), grow=0.5)          # Schattenkante unten
    paint_cells(0, 0.55, gi.hexc("#6A35D6"))
    top, bot = gi.hexc("#FFFFFF"), gi.hexc("#D2B4FF")
    y_a, y_b = y_start, y_start + 7 * cell
    paint_cells(0, 0, lambda x, y: gi.mixc(top, bot, min(1.0, max(0.0, (y - y_a) / (y_b - y_a)))))
    crisp = ic.render()

    # Glow: Alpha der Schrift weichzeichnen und lila einfaerben
    h, w = len(crisp), len(crisp[0])
    alpha = [[crisp[y][x][3] / 255.0 for x in range(w)] for y in range(h)]
    blurred = _blur_alpha(alpha, 5, passes=2)
    glow = [[(150, 90, 255, min(255, round(255 * min(1.0, blurred[y][x] * 2.6)))) for x in range(w)]
            for y in range(h)]
    gi.blend(glow, crisp, 0, 0)
    return glow


# ── Schliessen-X, Linien, Karte, Buttons ────────────────────────────────────

def make_close(gi):
    s = 4
    ic = gi.Icon(CLOSE_SIZE, CLOSE_SIZE, scale=s, ss=3)
    box = gi.sd_box(0.6, 0.6, CLOSE_SIZE - 0.6, CLOSE_SIZE - 0.6, 3.0)
    ic.paint(box, gi.hexc(BORDER))
    ic.paint(gi.sd_box(1.8, 1.8, CLOSE_SIZE - 1.8, CLOSE_SIZE - 1.8, 2.0), gi.vgrad(1, 13, gi.hexc("#2A1C57"), gi.hexc("#170F33")))
    ic.paint(gi.sd_seg((4.3, 4.3), (9.7, 9.7), 1.7), gi.hexc("#FFFFFF"))
    ic.paint(gi.sd_seg((9.7, 4.3), (4.3, 9.7), 1.7), gi.hexc("#FFFFFF"))
    return ic.render()


def make_rule(gi, left):
    """Trennlinie neben dem Untertitel: laeuft zum Titel hin aus (left: links, blendet nach rechts aus)."""
    w, h = 40, 4
    ic = gi.Icon(w, h, scale=2, ss=2)
    c = gi.hexc("#8E63E8")
    if left:
        ic.paint(gi.sd_box(0, 1.5, w, 2.5, 0.0), lambda x, y: (c[0], c[1], c[2], 0.9 * (x / w) ** 1.5))
    else:
        ic.paint(gi.sd_box(0, 1.5, w, 2.5, 0.0), lambda x, y: (c[0], c[1], c[2], 0.9 * (1 - x / w) ** 1.5))
    return ic.render()


def make_card_tile(gi, col):
    ic = gi.Icon(gi.CARD_TILE_W, gi.CARD_H, scale=gi.PANEL_SCALE, ss=3)
    ox = col * gi.CARD_TILE_W
    w, h = gi.CARD_W, gi.CARD_H
    card = gi._shift_x(gi.sd_box(0, 0, w, h, 3.5), ox)
    ic.paint(card, gi.vgrad(0, h, gi.hexc("#2A1F55"), gi.hexc("#170F30")))
    glow = gi.hexc(GLOW)
    ic.paint(card, lambda x, y: (glow[0], glow[1], glow[2], 0.35 * max(0.0, 1 - max(0.0, -card(x, y)) / 5.0) ** 2))
    inner = gi._shift_x(gi.sd_box(1.3, 1.3, w - 1.3, h - 1.3, 2.4), ox)
    ic.paint(gi.sub(card, inner), lambda x, y: gi.mixc(gi.hexc("#C79BFF"), gi.hexc("#8A4DFF"), (x + ox) / w))
    # Itembox links
    bx0, by0, bx1, by1 = AM_CARD_ICON_CENTER_X - 13, 4, AM_CARD_ICON_CENTER_X + 13, 30
    box = gi._shift_x(gi.sd_box(bx0, by0, bx1, by1, 3.0), ox)
    box_in = gi._shift_x(gi.sd_box(bx0 + 1, by0 + 1, bx1 - 1, by1 - 1, 2.2), ox)
    ic.paint(box, gi.hexc("#7B55D6"))
    ic.paint(box_in, gi.vgrad(by0, by1, gi.hexc("#1D1340"), gi.hexc("#0F0824")))
    return ic


def make_button_tile(gi, kind, primary):
    w = gi.BTN_MID_W if kind == "mid" else gi.BTN_END_W
    ic = gi.Icon(w, gi.BTN_H, scale=gi.PANEL_SCALE, ss=3)
    x0 = 0 if kind == "left" else -200
    x1 = w if kind == "right" else 200
    top, bot = AM_BTN_TOP, AM_BTN_BOTTOM
    outer = gi.sd_box(x0, top, x1, bot, 3)
    inner = gi.sd_box(x0 + 1, top + 1, x1 - 1, bot - 1, 2.2)
    if primary:
        ic.paint(outer, gi.hexc("#A46BFF"))
        ic.paint(inner, gi.vgrad(top + 1, bot - 1, gi.hexc("#33246B"), gi.hexc("#1F1445")))
        glow = gi.hexc("#9B5CFF")
        ic.paint(inner, lambda x, y: (glow[0], glow[1], glow[2], 0.30 * max(0.0, 1 - (-inner(x, y)) / 4.0) ** 2))
    else:
        ic.paint(outer, gi.hexc("#3D3262"))
        ic.paint(inner, gi.vgrad(top + 1, bot - 1, gi.hexc("#1E1839"), gi.hexc("#16112C")))
        ic.paint(gi.inter(inner, gi.above(top + 2.0)), gi.hexc("#2A2350"))
    return ic


# ── Alles schreiben ─────────────────────────────────────────────────────────

def write_all(gi, pack, write_png, providers, chest_rows):
    """Schreibt die PNGs, haengt die Font-Eintraege an providers an, liefert die Masse fuer UiIcon.java.
    chest_rows: gerendertes Icon "chest" (fuer die Itembox der Karte)."""
    ui_dir = os.path.join(pack, "assets", "fmc", "textures", "font", "ui")
    os.makedirs(ui_dir, exist_ok=True)
    for old in os.listdir(ui_dir):
        if old.startswith("am_"):
            os.remove(os.path.join(ui_dir, old))

    def out(name, rows):
        write_png(os.path.join(ui_dir, name), rows)

    def prov(name, ascent, height, char, folder="ui"):
        assert ascent <= height, f"{name}: ascent {ascent} > height {height}"
        providers.append({"type": "bitmap", "file": f"fmc:font/{folder}/{name}", "ascent": ascent,
                          "height": height, "chars": [char]})

    info = {}
    u, cols, rows_max = gi.PANEL_UNIT, gi.PANEL_COLS, gi.PANEL_ROWS_MAX

    # Rahmen
    tiles = []
    for kind in ("top", "mid", "bot"):
        for c in range(cols):
            rows = frame_tile(gi, kind, c).render()
            tiles.append(rows)
            out(f"am_panel_{kind}_{c}.png", rows)
    for c in range(cols):
        prov(f"am_panel_top_{c}.png", gi.PANEL_ASCENT, u, chr(AM_TOP_BASE + c))
    for r in range(1, rows_max):
        for kind, base in (("mid", AM_MID_BASE), ("bot", AM_BOT_BASE)):
            for c in range(cols):
                prov(f"am_panel_{kind}_{c}.png", gi.PANEL_ASCENT - r * u, u, chr(base + r * cols + c))
    for v in range(gi.PANEL_BOT_VAR_MIN, u - 1):
        for c in range(cols):
            rows = frame_tile(gi, "bot", c, v).render()
            tiles.append(rows)
            out(f"am_panel_botv_{v}_{c}.png", rows)
        for r in range(1, rows_max):
            for c in range(cols):
                idx = ((v - gi.PANEL_BOT_VAR_MIN) * rows_max + r) * cols + c
                prov(f"am_panel_botv_{v}_{c}.png", gi.PANEL_ASCENT - r * u, u, chr(AM_BOT_VAR_BASE + idx))
    info["panel_adv"] = gi.single_advance(tiles, u, "Amethyst-Panel")

    # Kristalle
    top_l = make_crystal_top(gi)
    out("am_crystal_top_l.png", top_l)
    out("am_crystal_top_r.png", flip(top_l))
    prov("am_crystal_top_l.png", gi.PANEL_ASCENT - CRY_TOP_Y, CRY_TOP_H, AM_CRYSTAL_TOP_L)
    prov("am_crystal_top_r.png", gi.PANEL_ASCENT - CRY_TOP_Y, CRY_TOP_H, AM_CRYSTAL_TOP_R)
    info["crystal_top_adv"] = gi.glyph_advance(top_l, CRY_TOP_H)
    bot_l = make_crystal_bottom(gi)
    out("am_crystal_bot_l.png", bot_l)
    out("am_crystal_bot_r.png", flip(bot_l))
    height_max = rows_max * u
    for yb in range(AM_CRYSTAL_BOT_MIN, height_max + 1):
        ascent = gi.PANEL_ASCENT - (yb + CRY_BOT_OVER - CRY_BOT_H)
        base = AM_CRYSTAL_BOT_BASE + 2 * (yb - AM_CRYSTAL_BOT_MIN)
        prov("am_crystal_bot_l.png", ascent, CRY_BOT_H, chr(base))
        prov("am_crystal_bot_r.png", ascent, CRY_BOT_H, chr(base + 1))
    info["crystal_bot_adv"] = gi.glyph_advance(bot_l, CRY_BOT_H)

    # Ornament, Titel, X, Linien, Karte, Buttons
    orn = make_ornament(gi)
    out("am_ornament.png", orn)
    prov("am_ornament.png", gi.PANEL_ASCENT + ORN_ABOVE, ORN_H, AM_ORNAMENT)
    info["ornament_adv"] = gi.glyph_advance(orn, ORN_H)
    info["titles"] = []
    for i, text in enumerate(TITLES):
        rows = make_title(gi, text)
        out(f"am_title_{text.lower()}.png", rows)
        prov(f"am_title_{text.lower()}.png", gi.PANEL_ASCENT - TITLE_TOP, TITLE_H, chr(AM_TITLE_BASE + i))
        info["titles"].append((text, chr(AM_TITLE_BASE + i), gi.glyph_advance(rows, TITLE_H)))
    close = make_close(gi)
    out("am_close.png", close)
    prov("am_close.png", gi.X_BIG_ASCENT, CLOSE_SIZE, AM_CLOSE)
    info["close_adv"] = gi.glyph_advance(close, CLOSE_SIZE)
    rule_l = make_rule(gi, True)
    out("am_rule_l.png", rule_l)
    out("am_rule_r.png", make_rule(gi, False))
    prov("am_rule_l.png", 4, 4, AM_RULE_L)
    prov("am_rule_r.png", 4, 4, AM_RULE_R)
    info["rule_adv"] = gi.glyph_advance(rule_l, 4)
    # Truhe in der Itembox der Karte (Bild des Icons "chest", 18 Pixel gross, mittig in der Karte)
    providers.append({"type": "bitmap", "file": "fmc:font/icons/chest.png", "ascent": -7, "height": 18,
                      "chars": [AM_CARD_CHEST]})
    info["card_chest_adv"] = gi.glyph_advance(chest_rows, 18)

    card = []
    for c in range(gi.CARD_COLS):
        rows = make_card_tile(gi, c).render()
        card.append(rows)
        out(f"am_card_{c}.png", rows)
        prov(f"am_card_{c}.png", gi.CARD_ASCENT, gi.CARD_H, chr(AM_CARD_BASE + c))
    info["card_adv"] = gi.single_advance(card, gi.CARD_H, "Amethyst-Karte")

    btn = {}
    for primary, chars, prefix in ((False, AM_BTN, "am_btn"), (True, AM_BTN_HI, "am_btn_hi")):
        for kind, char in zip(("left", "mid", "right"), chars):
            rows = make_button_tile(gi, kind, primary).render()
            btn[(primary, kind)] = rows
            out(f"{prefix}_{kind}.png", rows)
            prov(f"{prefix}_{kind}.png", gi.BTN_ASCENT, gi.BTN_H, char)
    info["btn_end_adv"] = gi.single_advance([btn[(p, "left")] for p in (False, True)]
                                            + [btn[(p, "right")] for p in (False, True)], gi.BTN_H, "AM-Button-Enden")
    info["btn_mid_adv"] = gi.single_advance([btn[(p, "mid")] for p in (False, True)], gi.BTN_H, "AM-Button-Mitte")
    return info


def lit(c):
    return "\"\\u%04X\"" % ord(c)


def java_lines(info):
    """Konstanten fuer UiIcon.java (im Enum-Rumpf)."""
    def const(name, value, doc=None):
        out = []
        if doc:
            out.append("    /** %s */" % doc)
        out.append("    public static final int %s = %d;" % (name, value))
        return out

    L = ["", "    // ── Amethyst-Theme (siehe tools/amethyst_theme.py) ──"]
    L.append("    public static final char AM_TOP_BASE = (char) 0x%04X;" % AM_TOP_BASE)
    L.append("    public static final char AM_MID_BASE = (char) 0x%04X;" % AM_MID_BASE)
    L.append("    public static final char AM_BOT_BASE = (char) 0x%04X;" % AM_BOT_BASE)
    L.append("    public static final char AM_BOT_VAR_BASE = (char) 0x%04X;" % AM_BOT_VAR_BASE)
    L += const("AM_PANEL_TILE_ADVANCE", info["panel_adv"])
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
    L += const("AM_CARD_CHEST_ADVANCE", info["card_chest_adv"])
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
    L += const("AM_PAD_LINES", AM_PAD_LINES, "Leerzeilen ueber dem Rahmen (Platz fuer die Truhe).")
    L += const("AM_HEADER_LINES", AM_HEADER_LINES, "Kopfzeilen mit Banner (Truhe, Titel, Untertitel).")
    L += const("AM_NAME_X", AM_NAME_X, "Textbeginn in der Karte.")
    L += const("AM_CARD_ICON_CENTER_X", AM_CARD_ICON_CENTER_X, "Mitte der Itembox in der Karte.")
    L += const("AM_CENTER_PAD_LINES", AM_CENTER_PAD_LINES)
    L += const("AM_CRYSTAL_TOP_Y", CRY_TOP_Y, "Oberkante der Seitenkristalle unter der Rahmenoberkante.")
    L += const("AM_CRYSTAL_BOT_H", CRY_BOT_H)
    L += const("AM_CRYSTAL_BOT_OVER", CRY_BOT_OVER, "So weit ragt der untere Kristall ueber die Unterkante.")
    for text, char, adv in info["titles"]:
        L.append("    /** Titelbild \"%s\" (Pixelschrift mit Glow). */" % text)
        L.append("    public static final String AM_TITLE_%s = %s;" % (text.upper(), lit(char)))
        L += const("AM_TITLE_%s_ADVANCE" % text.upper(), adv)
    return L
