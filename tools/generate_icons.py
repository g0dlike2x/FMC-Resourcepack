#!/usr/bin/env python3
"""
Erzeugt die Icon-PNGs und die Font-Definition fuers FMC-Resourcepack.

Nur Standardbibliothek (kein Pillow noetig). Aufruf (aus dem Ordner FMC-Resourcepack):

    python tools/generate_icons.py

Schreibt:
    pack/assets/fmc/textures/font/icons/<name>.png   (32x32, farbig, mit Kantenglaettung)
    pack/assets/fmc/font/icons.json
    pack/pack.png
    dist/preview.png                                 (Kontaktbogen, nicht Teil des Packs)

Die Zeichen-Zuordnung steht in ICONS weiter unten. Im Plugin wird ein Icon so benutzt:

    Component.text("\\uE005").font(Key.key("fmc:icons"))

Die Icons sind fertig eingefaerbt und sollten mit WEISSER Textfarbe benutzt werden,
sonst werden sie von der Textfarbe getoent.

Zeichentechnik: Jedes Icon wird 4x ueberabgetastet (128x128) aus Signed-Distance-Formen
gezeichnet und auf 32x32 heruntergerechnet. Das ergibt glatte Kanten, Farbverlaeufe,
Umrisse und Glanzlichter, ohne dass ein Grafikprogramm noetig ist.
"""
import json
import math
import multiprocessing
import os
import struct
import sys
import zlib

import amethyst_theme
import chest_textures
import ui_textures

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACK = os.path.join(ROOT, "pack")
ICON_DIR = os.path.join(PACK, "assets", "fmc", "textures", "font", "icons")
FONT_JSON = os.path.join(PACK, "assets", "fmc", "font", "icons.json")

N = 32          # Kantenlaenge der fertigen Icons in Pixeln
SS = 4          # Ueberabtastung pro Achse

# Darstellung im Spiel: Hoehe eines Icons in Text-Pixeln (normale Schrift = 8) und
# Abstand der Oberkante zur Grundlinie. Bei 9/8 sitzt das Icon mittig zu Grossbuchstaben.
# Wirkt sich nur auf icons.json aus, die PNGs bleiben gleich.
GLYPH_HEIGHT = 9
GLYPH_ASCENT = 8

# Grosse Variante jedes Icons (fuer Dialog-Buttons): eigenes Zeichen BIG_ICON_BASE + Index.
# Hoehe 14, Oberkante 10 ueber der Grundlinie = mittig zur normalen Schrift.
BIG_ICON_BASE = 0xEC00
BIG_ICON_HEIGHT = 14
BIG_ICON_ASCENT = 10


# ── Farben ──────────────────────────────────────────────────────────────────

def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mixc(c0, c1, t):
    return tuple(c0[i] + (c1[i] - c0[i]) * t for i in range(4))


def darker(c, f):
    return (c[0] * (1 - f), c[1] * (1 - f), c[2] * (1 - f), c[3])


def lighter(c, f):
    return (c[0] + (255 - c[0]) * f, c[1] + (255 - c[1]) * f, c[2] + (255 - c[2]) * f, c[3])


def vgrad(y0, y1, c0, c1):
    span = float(y1 - y0)

    def f(x, y):
        return mixc(c0, c1, min(1.0, max(0.0, (y - y0) / span)))
    return f


WHITE = hexc("#FFFFFF")
RED = (hexc("#FF7B7B"), hexc("#D32F2F"))
GREEN = (hexc("#82EE82"), hexc("#1E9B3C"))
BLUE = (hexc("#6FCEFF"), hexc("#1E6FD6"))
GOLD = (hexc("#FFE675"), hexc("#EE9A12"))
STEEL = (hexc("#E6ECF3"), hexc("#7B899D"))
DARKGRAY = (hexc("#8795A8"), hexc("#3E4856"))
SILVER = (hexc("#FFFFFF"), hexc("#9AA6B5"))
BRONZE = (hexc("#F2B583"), hexc("#A8612A"))
BROWN = (hexc("#D9A066"), hexc("#8A5326"))
PURPLE = (hexc("#D08CFF"), hexc("#7A2CC0"))
ORANGE = (hexc("#FFC45F"), hexc("#E8601C"))
TEAL = (hexc("#82F0EA"), hexc("#12858F"))
CYAN = (hexc("#A2F4FF"), hexc("#2FA8D4"))
CREAM = (hexc("#FFF7DE"), hexc("#E2C48A"))
HEART = (hexc("#FF8A9A"), hexc("#D01F3C"))
WOOD_OUT = hexc("#4A2A0E")


# ── Signed-Distance-Formen (Einheiten = Pixel des fertigen Icons) ───────────
# Negativ = innen, 0 = Kante, positiv = aussen.

def dist_to_segment(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def point_in_polygon(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def sd_circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def sd_ring(cx, cy, r0, r1):
    mid, hw = (r0 + r1) / 2, (r1 - r0) / 2
    return lambda x, y: abs(math.hypot(x - cx, y - cy) - mid) - hw


def sd_arc(cx, cy, r0, r1, a0, a1):
    """Ring-Ausschnitt von Winkel a0 bis a1 (Grad, gegen den Uhrzeigersinn, 0 = rechts, 90 = oben)."""
    mid, hw, span = (r0 + r1) / 2, (r1 - r0) / 2, a1 - a0

    def f(x, y):
        rd = abs(math.hypot(x - cx, y - cy) - mid) - hw
        rel = (math.degrees(math.atan2(-(y - cy), x - cx)) - a0) % 360
        if rel <= span:
            return rd
        return max(rd, math.radians(min(rel - span, 360 - rel)) * mid)
    return f


def sd_seg(p0, p1, w):
    return lambda x, y: dist_to_segment(x, y, p0, p1) - w / 2


def sd_box(x0, y0, x1, y1, r=0.0):
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2

    def f(x, y):
        qx, qy = abs(x - cx) - (hx - r), abs(y - cy) - (hy - r)
        return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r
    return f


def sd_poly(pts):
    n = len(pts)
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]

    def f(x, y):
        d = min(dist_to_segment(x, y, a, b) for a, b in edges)
        return -d if point_in_polygon(x, y, pts) else d
    return f


def union(*fs):
    return lambda x, y: min(f(x, y) for f in fs)


def inter(a, b):
    return lambda x, y: max(a(x, y), b(x, y))


def sub(a, b):
    return lambda x, y: max(a(x, y), -b(x, y))


def rnd(f, r):
    """Rundet die Ecken einer Form ab, waechst dabei um r (Eingabe also um r verkleinern)."""
    return lambda x, y: f(x, y) - r


def mirror(f):
    return lambda x, y: f(N - x, y)


def ellipse(cx, cy, a, b):
    k = min(a, b)
    return lambda x, y: (math.hypot((x - cx) / a, (y - cy) / b) - 1.0) * k


def rot(f, deg, cx=16.0, cy=16.0):
    """Dreht eine Form um (cx, cy); positive Grad = im Uhrzeigersinn."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)

    def g(x, y):
        dx, dy = x - cx, y - cy
        return f(cx + c * dx + s * dy, cy - s * dx + c * dy)
    return g


def shift(f, dx, dy):
    return lambda x, y: f(x - dx, y - dy)


# Halbebenen: "innen", wenn die Bedingung gilt
def above(v):      # y <= v
    return lambda x, y: y - v


def below(v):      # y >= v
    return lambda x, y: v - y


def left_of(v):    # x <= v
    return lambda x, y: x - v


def right_of(v):   # x >= v
    return lambda x, y: v - x


def star_pts(cx, cy, ro, ri, n=5, start=-90):
    pts = []
    for k in range(n * 2):
        r = ro if k % 2 == 0 else ri
        a = math.radians(start + k * 180.0 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def scale_pts(pts, k, cx, cy):
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]


def sparkle_pts(cx, cy, r):
    k = 0.22
    return [(cx, cy - r), (cx + r * k, cy - r * k), (cx + r, cy), (cx + r * k, cy + r * k),
            (cx, cy + r), (cx - r * k, cy + r * k), (cx - r, cy), (cx - r * k, cy - r * k)]


# ── Zeichenflaeche ──────────────────────────────────────────────────────────

class Icon:
    """Zeichenflaeche. Koordinaten sind "Einheiten"; ein Icon ist N x N Einheiten gross und wird mit
    1 Pixel pro Einheit ausgegeben. Fuer groessere Flaechen (Panel) lassen sich Breite/Hoehe in Einheiten,
    Pixel pro Einheit (scale) und Ueberabtastung (ss) angeben."""

    def __init__(self, w=N, h=N, scale=1, ss=SS):
        self.w, self.h, self.scale, self.ss = w, h, scale, ss
        self.mw = w * scale * ss
        self.mh = h * scale * ss
        size = self.mw * self.mh
        self.R = [0.0] * size
        self.G = [0.0] * size
        self.B = [0.0] * size
        self.A = [0.0] * size

    def paint(self, sdf, color, grow=0.0, box=None):
        S, m = self.scale * self.ss, self.mw
        x0, y0, x1, y1 = box if box else (0, 0, self.w, self.h)
        i0, i1 = max(0, int(x0 * S)), min(self.mw, int(math.ceil(x1 * S)))
        j0, j1 = max(0, int(y0 * S)), min(self.mh, int(math.ceil(y1 * S)))
        is_fn = callable(color)
        R, G, B, A = self.R, self.G, self.B, self.A
        for j in range(j0, j1):
            y = (j + 0.5) / S
            base = j * m
            for i in range(i0, i1):
                x = (i + 0.5) / S
                if sdf(x, y) <= grow:
                    c = color(x, y) if is_fn else color
                    sa = c[3]
                    if sa <= 0:
                        continue
                    k = base + i
                    da = A[k]
                    oa = sa + da * (1 - sa)
                    w = da * (1 - sa)
                    R[k] = (c[0] * sa + R[k] * w) / oa
                    G[k] = (c[1] * sa + G[k] * w) / oa
                    B[k] = (c[2] * sa + B[k] * w) / oa
                    A[k] = oa

    def shape(self, sdf, colors, y0, y1, outline=None, out=1.1, rim=True):
        """Gefuellte Form mit Umriss, vertikalem Farbverlauf und Licht/Schatten am Rand."""
        top, bot = colors
        outline = outline or darker(bot, 0.6)
        box = (0, max(0, y0 - 3), self.w, min(self.h, y1 + 3))
        self.paint(sdf, outline, grow=out, box=box)
        base = vgrad(y0, y1, top, bot)
        mid = (y0 + y1) / 2

        def col(x, y):
            c = base(x, y)
            if rim and sdf(x, y) > -1.5:
                return lighter(c, 0.38) if y < mid else darker(c, 0.14)
            return c
        self.paint(sdf, col, box=box)

    def gloss(self, clip, y0, y1, strength=0.35):
        """Weisses Glanzlicht auf der oberen Haelfte einer Form."""
        cut = y0 + (y1 - y0) * 0.5
        region = inter(clip, lambda x, y: y - cut)

        def col(x, y):
            return (255, 255, 255, strength * max(0.0, 1 - (y - y0) / (cut - y0)))
        self.paint(region, col, box=(0, y0 - 1, self.w, cut + 1))

    def sparkle(self, cx, cy, r, alpha=0.95):
        self.paint(sd_poly(sparkle_pts(cx, cy, r)), (255, 255, 255, alpha),
                   box=(cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1))

    def render(self):
        """Rechnet auf (w*scale) x (h*scale) Pixel herunter. Rueckgabe: Zeilen aus (r, g, b, a) mit 0-255."""
        S, m = self.ss, self.mw
        rows = []
        for py in range(self.h * self.scale):
            row = []
            for px in range(self.w * self.scale):
                sa = sr = sg = sb = 0.0
                for dy in range(S):
                    base = (py * S + dy) * m + px * S
                    for dx in range(S):
                        k = base + dx
                        a = self.A[k]
                        if a > 0:
                            sa += a
                            sr += self.R[k] * a
                            sg += self.G[k] * a
                            sb += self.B[k] * a
                if sa <= 0:
                    row.append((0, 0, 0, 0))
                else:
                    row.append((round(sr / sa), round(sg / sa), round(sb / sa),
                                min(255, round(255 * sa / (S * S)))))
            rows.append(row)
        return rows


# ── PNG-Ausgabe und Hilfen ──────────────────────────────────────────────────

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


def blank(w, h, color=(0, 0, 0, 0)):
    return [[color] * w for _ in range(h)]


def scale_nearest(rows, f):
    return [[rows[y // f][x // f] for x in range(len(rows[0]) * f)] for y in range(len(rows) * f)]


def blend(dst, src, ox, oy):
    """Legt src (mit Alpha) auf dst."""
    for y, row in enumerate(src):
        for x, (r, g, b, a) in enumerate(row):
            if a == 0:
                continue
            dy, dx = oy + y, ox + x
            if not (0 <= dy < len(dst) and 0 <= dx < len(dst[0])):
                continue
            dr, dg, db, da = dst[dy][dx]
            sa, ba = a / 255.0, da / 255.0
            oa = sa + ba * (1 - sa)
            dst[dy][dx] = (round((r * sa + dr * ba * (1 - sa)) / oa),
                           round((g * sa + dg * ba * (1 - sa)) / oa),
                           round((b * sa + db * ba * (1 - sa)) / oa),
                           round(255 * oa))


# ── Icons ───────────────────────────────────────────────────────────────────

def icon_back(colors=RED, flip=False):
    ic = Icon()
    head = sd_poly([(6.0, 16.0), (16.0, 6.4), (16.0, 25.6)])
    tail = sd_box(14.0, 11.8, 27.5, 20.2, 1.0)
    shape = rnd(union(head, tail), 1.2)
    if flip:
        shape = mirror(shape)
    ic.shape(shape, colors, 4.0, 28.0)
    return ic


def icon_next():
    return icon_back(GREEN, flip=True)


def icon_refresh():
    ic = Icon()
    cx, cy = 15.5, 17.2
    ring = sd_arc(cx, cy, 5.6, 10.8, 75, 370)
    a = math.radians(75)
    bx, by = cx + 8.2 * math.cos(a), cy - 8.2 * math.sin(a)       # Mitte der Pfeilbasis
    dx, dy = math.sin(a), math.cos(a)                              # Laufrichtung (im Uhrzeigersinn)
    rx, ry = math.cos(a), -math.sin(a)                             # radiale Richtung
    hw, ln = 6.4, 8.8
    head = sd_poly([(bx + rx * hw, by + ry * hw), (bx - rx * hw, by - ry * hw), (bx + dx * ln, by + dy * ln)])
    ic.shape(union(ring, head), BLUE, 3.0, 29.0)
    return ic


def icon_check():
    ic = Icon()
    s = union(sd_seg((6.0, 17.0), (12.5, 23.5), 5.6), sd_seg((12.5, 23.5), (26.5, 8.5), 5.6))
    ic.shape(s, GREEN, 5.0, 27.0)
    return ic


def icon_close():
    ic = Icon()
    s = union(sd_seg((7.0, 7.0), (25.0, 25.0), 5.6), sd_seg((25.0, 7.0), (7.0, 25.0), 5.6))
    ic.shape(s, RED, 4.0, 28.0)
    return ic


def _coin(ic, rim_top, rim_bot, face_top, face_bot, groove, outline):
    """Muenze mit gerieffeltem Rand und vertiefter Flaeche; Praegung kommt vom Aufrufer."""
    cx = cy = 16.0
    coin = sd_circle(cx, cy, 14.2)
    ic.paint(coin, outline, grow=1.1)

    def rim(x, y):
        base = vgrad(2, 30, rim_top, rim_bot)(x, y)
        k = int((math.atan2(y - cy, x - cx) + math.pi) / (2 * math.pi) * 28)
        return darker(base, 0.16) if k % 2 else base
    ic.paint(coin, rim)
    ic.paint(sd_circle(cx, cy, 11.9), groove)
    ic.paint(sd_circle(cx, cy, 11.0), vgrad(5, 27, face_top, face_bot))
    return coin


def _emboss(ic, sdf, dark_top, dark_bot, light, y0, y1):
    """Praegung: heller Schatten rechts unten, dunkle Form darueber."""
    ic.paint(shift(sdf, 0.7, 0.9), light)
    ic.paint(sdf, vgrad(y0, y1, dark_top, dark_bot))


def icon_tokens(scale=1):
    ic = Icon(scale=scale)
    coin = _coin(ic, hexc("#FFE680"), hexc("#E8940F"), hexc("#F2A917"), hexc("#FFDB55"),
                 hexc("#B96C00"), hexc("#6B3F00"))
    t = [(9.6, 9.6), (22.4, 9.6), (22.4, 13.4), (17.9, 13.4), (17.9, 23.2), (14.1, 23.2), (14.1, 13.4), (9.6, 13.4)]
    _emboss(ic, sd_poly(t), hexc("#C27800"), hexc("#8C5200"), hexc("#FFF2A8", 0.9), 9, 23)
    ic.gloss(coin, 2.0, 30.0, 0.22)
    ic.sparkle(9.0, 8.0, 3.2)
    return ic


def icon_juwelen():
    ic = Icon()
    g0, g1, g2, g3 = (2.5, 12.5), (11.0, 12.5), (21.0, 12.5), (29.5, 12.5)
    t0, t1, b = (9.0, 5.0), (23.0, 5.0), (16.0, 28.5)
    whole = sd_poly([g0, t0, t1, g3, b])
    ic.paint(whole, hexc("#33085C"), grow=1.2)
    facets = [
        ([g0, t0, g1], "#E7BEFF"),
        ([t0, t1, g2, g1], "#D08BFF"),
        ([t1, g3, g2], "#B056F0"),
        ([g0, g1, b], "#A044E6"),
        ([g1, g2, b], "#8A2ED0"),
        ([g2, g3, b], "#6D1CAA"),
    ]
    for pts, col in facets:
        ic.paint(sd_poly(pts), hexc(col))
    line = hexc("#4B0F82", 0.55)
    for a, c in [(g0, g3), (t0, g1), (t1, g2), (g1, b), (g2, b)]:
        ic.paint(sd_seg(a, c, 0.7), line, box=(0, 0, N, N))
    ic.sparkle(10.5, 8.8, 3.4)
    return ic


def icon_search():
    ic = Icon()
    handle = sd_seg((21.0, 21.0), (27.5, 27.5), 5.4)
    ic.shape(handle, (hexc("#B9763A"), hexc("#6E3B14")), 18.0, 30.0)
    cx = cy = 13.0
    ic.shape(sd_ring(cx, cy, 6.6, 10.4), STEEL, 2.0, 24.0, outline=hexc("#2F3A4A"))
    lens = sd_circle(cx, cy, 6.6)
    ic.paint(lens, vgrad(6, 20, hexc("#D6F3FF", 0.85), hexc("#7FCBF2", 0.85)))
    ic.sparkle(10.6, 10.4, 2.8, 0.9)
    return ic


def _badge(ic, colors):
    badge = sd_circle(16, 16, 14.0)
    ic.shape(badge, colors, 2.0, 30.0)
    ic.gloss(badge, 2.0, 30.0, 0.3)
    return badge


def icon_info():
    ic = Icon()
    _badge(ic, BLUE)
    shadow = hexc("#0F3F7F", 0.5)
    ic.paint(sd_circle(16.4, 9.9, 2.4), shadow)
    ic.paint(sd_box(13.9, 14.3, 18.9, 25.3, 1.2), shadow)
    ic.paint(sd_circle(16, 9.4, 2.4), WHITE)
    ic.paint(sd_box(13.5, 13.8, 18.5, 24.8, 1.2), WHITE)
    return ic


def icon_warning():
    ic = Icon()
    tri = rnd(sd_poly([(16.0, 6.0), (26.6, 24.2), (5.4, 24.2)]), 2.4)
    ic.shape(tri, GOLD, 2.0, 27.0, outline=hexc("#6B3F00"))
    dark = hexc("#4A2A00")
    ic.paint(sd_box(14.3, 10.8, 17.7, 19.2, 1.4), dark)
    ic.paint(sd_circle(16, 22.0, 1.9), dark)
    return ic


def _lock(colors, open_lock):
    ic = Icon()
    steel = (hexc("#F0F3F7"), hexc("#7B899D"))
    if open_lock:
        cy = 9.2
        shackle = union(sd_arc(16, cy, 4.0, 7.6, 0, 180), sd_box(8.4, cy, 12.0, 17.0))
        ic.shape(shackle, steel, 1.0, 16.0, outline=hexc("#2F3A4A"))
    else:
        cy = 13.2
        shackle = union(sd_arc(16, cy, 4.0, 7.6, 0, 180), sd_box(8.4, cy, 12.0, 17.0), sd_box(20.0, cy, 23.6, 17.0))
        ic.shape(shackle, steel, 5.0, 17.0, outline=hexc("#2F3A4A"))
    body = sd_box(5.5, 14.5, 26.5, 29.0, 3.0)
    ic.shape(body, colors, 14.5, 29.0)
    dark = darker(colors[1], 0.65)
    ic.paint(sd_circle(16, 20.4, 2.4), dark)
    ic.paint(sd_box(14.9, 21.0, 17.1, 25.6, 0.8), dark)
    return ic


def icon_lock():
    return _lock(RED, False)


def icon_unlock():
    return _lock(GREEN, True)


def icon_settings():
    ic = Icon()
    cx = cy = 16.0
    parts = [sd_circle(cx, cy, 10.2)]
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        parts.append(sd_seg((cx + 8.4 * math.cos(a), cy + 8.4 * math.sin(a)),
                            (cx + 12.0 * math.cos(a), cy + 12.0 * math.sin(a)), 5.0))
    gear = sub(union(*parts), sd_circle(cx, cy, 4.8))
    ic.shape(gear, STEEL, 2.0, 30.0, outline=hexc("#2F3A4A"))
    ic.paint(sd_ring(cx, cy, 4.8, 6.4), hexc("#5A687C", 0.5))
    return ic


def _toggle(colors, on):
    ic = Icon()
    pill = sd_box(2.0, 8.0, 30.0, 24.0, 8.0)
    ic.shape(pill, colors, 8.0, 24.0)
    kx = 22.0 if on else 10.0
    knob = sd_circle(kx, 16.0, 5.6)
    ic.shape(knob, (hexc("#FFFFFF"), hexc("#CBD5DD")), 10.4, 21.6, outline=darker(colors[1], 0.5))
    return ic


def icon_toggle_on():
    return _toggle(GREEN, True)


def icon_toggle_off():
    return _toggle(RED, False)


def icon_plus():
    ic = Icon()
    _badge(ic, GREEN)
    shadow = hexc("#0B5A22", 0.45)
    ic.paint(sd_box(13.8, 8.8, 18.8, 24.8, 1.3), shadow)
    ic.paint(sd_box(8.0, 14.6, 24.0, 19.6, 1.3), shadow)
    ic.paint(sd_box(13.5, 8.0, 18.5, 24.0, 1.3), WHITE)
    ic.paint(sd_box(8.0, 13.5, 24.0, 18.5, 1.3), WHITE)
    return ic


def icon_minus():
    ic = Icon()
    _badge(ic, RED)
    ic.paint(sd_box(8.0, 14.6, 24.0, 19.6, 1.3), hexc("#6B1010", 0.45))
    ic.paint(sd_box(8.0, 13.5, 24.0, 18.5, 1.3), WHITE)
    return ic


def icon_bank():
    ic = Icon()
    marble = (hexc("#FFFFFF"), hexc("#D3C8B2"))
    edge = hexc("#7A6A4A")
    ic.shape(rnd(sd_poly([(16.0, 5.0), (27.0, 11.0), (5.0, 11.0)]), 1.4), GOLD, 3.0, 12.5,
             outline=hexc("#6B3F00"))
    ic.paint(sd_circle(16, 9.2, 1.7), hexc("#9C5A00"))
    ic.shape(sd_box(4.0, 13.0, 28.0, 15.4, 0.6), marble, 13.0, 15.4, outline=edge, out=0.9, rim=False)
    for cx in (7.6, 13.2, 18.8, 24.4):
        ic.shape(sd_box(cx - 1.8, 15.6, cx + 1.8, 24.6, 0.5), marble, 15.6, 24.6, outline=edge, out=0.9, rim=False)
    ic.shape(sd_box(2.5, 24.8, 29.5, 28.8, 1.2), GOLD, 24.8, 28.8, outline=hexc("#6B3F00"), out=0.9)
    return ic


def icon_star():
    ic = Icon()
    cx, cy, ro, ri = 16.0, 17.0, 14.0, 6.2
    pts = []
    for k in range(10):
        r = ro if k % 2 == 0 else ri
        a = math.radians(-90 + k * 36)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    star = rnd(sd_poly(pts), 0.0)
    ic.shape(star, GOLD, 2.5, 30.0, outline=hexc("#7A4300"), out=1.2)
    # rechte Haelfte leicht abdunkeln (Facetteneffekt); innen, wenn x >= 16
    ic.paint(inter(star, lambda x, y: 16.0 - x), (120, 60, 0, 0.16))
    ic.sparkle(11.0, 12.0, 3.0)
    return ic


def icon_clock():
    ic = Icon()
    rim = sd_circle(16, 16, 14.0)
    ic.shape(rim, BLUE, 2.0, 30.0, outline=hexc("#0F2F66"))
    face = sd_circle(16, 16, 10.8)
    ic.paint(face, hexc("#0F2F66", 0.55), grow=0.9)
    ic.paint(face, vgrad(5, 27, hexc("#FFFFFF"), hexc("#D5E2F0")))
    dark = hexc("#1B2F55")
    for (x, y, w, h) in [(15.1, 6.0, 1.8, 3.0), (15.1, 23.0, 1.8, 3.0), (6.0, 15.1, 3.0, 1.8), (23.0, 15.1, 3.0, 1.8)]:
        ic.paint(sd_box(x, y, x + w, y + h, 0.4), dark)
    ic.paint(sd_seg((16, 16), (16, 8.6), 2.2), dark)
    ic.paint(sd_seg((16, 16), (21.2, 19.0), 2.2), dark)
    ic.paint(sd_circle(16, 16, 1.9), hexc("#E04848"))
    ic.sparkle(9.0, 8.6, 2.6, 0.7)
    return ic


def icon_booster():
    ic = Icon()
    bolt = rnd(sd_poly([(19.6, 3.4), (8.6, 17.6), (15.0, 17.6), (12.6, 28.6), (23.4, 13.4), (17.2, 13.4)]), 1.0)
    ic.shape(bolt, GOLD, 2.0, 30.0, outline=hexc("#7A3F00"), out=1.2)
    ic.sparkle(12.4, 11.0, 2.8, 0.85)
    return ic


# ── Batch 2: Prison, Angeln, Clan, Shops, Allgemeines ───────────────────────

def icon_pickaxe():
    ic = Icon()
    ic.shape(sd_seg((6.5, 26.5), (22.5, 10.5), 3.6), BROWN, 8.0, 28.5, outline=WOOD_OUT)
    ic.shape(sd_arc(14.0, 18.0, 8.6, 12.4, -12, 102), CYAN, 4.0, 24.0, outline=hexc("#0F4A66"))
    return ic


def icon_shard():
    ic = Icon()
    amber = (hexc("#FFF29A"), hexc("#E8A100"))
    out = hexc("#6B4300")
    small = rnd(sd_poly([(7.5, 15.5), (11.0, 20.0), (10.0, 28.0), (5.0, 28.0), (4.0, 20.0)]), 0.8)
    ic.shape(small, (hexc("#FFE680"), hexc("#D98F00")), 14.0, 29.0, outline=out)
    big = rnd(sd_poly([(17.0, 3.5), (23.0, 10.5), (21.0, 28.0), (12.0, 28.0), (10.0, 10.5)]), 1.0)
    ic.shape(big, amber, 2.0, 29.0, outline=out)
    ic.paint(inter(big, left_of(16.5)), (255, 255, 255, 0.28))
    ic.paint(inter(big, right_of(16.5)), (90, 40, 0, 0.18))
    ic.paint(sd_seg((16.5, 4.5), (16.5, 27.0), 0.7), hexc("#8A5A00", 0.45))
    ic.sparkle(13.0, 11.0, 3.0)
    return ic


def icon_minepoints():
    ic = Icon()
    hexa = rnd(sd_poly([(16 + 12.4 * math.cos(math.radians(60 * k)), 16 + 12.4 * math.sin(math.radians(60 * k)))
                        for k in range(6)]), 1.6)
    ic.shape(hexa, TEAL, 1.5, 30.5)
    for dy in (0.0, 6.0):
        s = union(sd_seg((9.5, 17.0 + dy), (16, 10.5 + dy), 3.2), sd_seg((16, 10.5 + dy), (22.5, 17.0 + dy), 3.2))
        ic.paint(shift(s, 0.0, 0.9), hexc("#04474D", 0.5))
        ic.paint(s, WHITE)
    return ic


def icon_percent():
    ic = Icon()
    _badge(ic, BLUE)
    parts = union(sd_ring(11.2, 11.2, 1.5, 3.7), sd_ring(20.8, 20.8, 1.5, 3.7), sd_seg((21.5, 10.0), (10.5, 22.0), 2.8))
    ic.paint(shift(parts, 0.4, 0.8), hexc("#0F3F7F", 0.5))
    ic.paint(parts, WHITE)
    return ic


def icon_flame():
    ic = Icon()
    outer = union(sd_circle(16, 20.5, 9.2), sd_poly([(17.5, 2.5), (25.0, 18.0), (7.5, 18.0)]))
    ic.shape(rnd(outer, 0.0), (hexc("#FFB347"), hexc("#E5321A")), 2.0, 30.0, outline=hexc("#6B1408"))
    inner = union(sd_circle(16, 22.8, 5.2), sd_poly([(16.5, 11.0), (21.2, 22.0), (11.5, 22.0)]))
    ic.paint(inner, vgrad(11, 28, hexc("#FFF6A8"), hexc("#FFC93C")))
    return ic


def icon_moneybag():
    ic = Icon()
    sack = (hexc("#E9BC7C"), hexc("#A8702F"))
    body = union(ellipse(16.0, 21.0, 11.4, 9.0),
                 sd_poly([(11.5, 9.5), (20.5, 9.5), (24.0, 17.0), (8.0, 17.0)]))
    ic.shape(body, sack, 9.0, 30.5, outline=WOOD_OUT)
    flare = rnd(sd_poly([(9.5, 4.5), (22.5, 4.5), (19.8, 9.5), (12.2, 9.5)]), 1.2)
    ic.shape(flare, (hexc("#F2CE94"), hexc("#B98040")), 2.5, 11.5, outline=WOOD_OUT)
    ic.shape(sd_seg((10.8, 10.4), (21.2, 10.4), 2.8), RED, 8.5, 12.5, outline=hexc("#5E0A1B"), out=0.8, rim=False)
    ic.shape(sd_circle(16.0, 21.6, 5.8), GOLD, 15.5, 27.5, outline=hexc("#7A4A00"), out=0.9)
    ic.paint(sd_ring(16.0, 21.6, 2.5, 3.4), hexc("#B96C00"))
    ic.sparkle(9.5, 18.5, 2.2, 0.8)
    return ic


def icon_chest():
    ic = Icon()
    wood = (hexc("#D9A066"), hexc("#8A5326"))
    ic.shape(sd_box(3.5, 14.0, 28.5, 28.5, 2.0), wood, 14.0, 28.5, outline=WOOD_OUT)
    ic.shape(sd_box(3.5, 5.0, 28.5, 16.0, 5.0), (hexc("#E8B27A"), hexc("#A8672F")), 5.0, 16.0, outline=WOOD_OUT)
    ic.paint(sd_seg((4.5, 15.0), (27.5, 15.0), 1.2), hexc("#3A200B", 0.8))
    for x in (8.0, 24.0):
        ic.shape(sd_box(x - 1.6, 5.5, x + 1.6, 28.0, 0.6), GOLD, 5.5, 28.0, outline=hexc("#6B3F00"), out=0.8, rim=False)
    ic.shape(sd_box(13.0, 12.0, 19.0, 20.0, 1.5), GOLD, 12.0, 20.0, outline=hexc("#6B3F00"), out=0.9)
    ic.paint(sd_circle(16, 15.4, 1.3), hexc("#4A2A00"))
    ic.paint(sd_box(15.4, 15.6, 16.6, 18.4, 0.3), hexc("#4A2A00"))
    return ic


def icon_pass():
    ic = Icon()
    ticket = sub(sub(sd_box(2.0, 7.5, 30.0, 24.5, 3.0), sd_circle(2.0, 16.0, 3.2)), sd_circle(30.0, 16.0, 3.2))
    ic.shape(ticket, PURPLE, 7.5, 24.5)
    for y in (10.0, 13.2, 16.4, 19.6):
        ic.paint(sd_box(22.0, y, 23.4, y + 1.8, 0.3), hexc("#FFFFFF", 0.75))
    star = star_pts(12.0, 16.2, 6.2, 2.7)
    ic.paint(shift(sd_poly(star), 0.4, 0.8), hexc("#3E0F6B", 0.5))
    ic.paint(sd_poly(star), hexc("#FFE675"))
    return ic


def icon_quest():
    ic = Icon()
    ic.shape(sd_box(7.0, 5.5, 25.0, 26.5, 1.5), CREAM, 5.5, 26.5, outline=hexc("#6B4A1E"))
    roll = (hexc("#E8C789"), hexc("#B38848"))
    ic.shape(sd_seg((5.5, 5.5), (26.5, 5.5), 5.0), roll, 3.0, 8.0, outline=hexc("#6B4A1E"))
    ic.shape(sd_seg((5.5, 26.5), (26.5, 26.5), 5.0), roll, 24.0, 29.0, outline=hexc("#6B4A1E"))
    ink = hexc("#8A5A22")
    for y, x1 in ((11.5, 21.0), (15.5, 19.0), (19.5, 21.0)):
        ic.paint(sd_seg((10.5, y), (x1, y), 1.7), ink)
    ic.paint(sd_seg((10.0, 22.8), (12.0, 24.6), 1.6), hexc("#2E9B3C"))
    return ic


def icon_book():
    ic = Icon()
    ic.shape(sd_box(8.0, 5.0, 27.5, 28.0, 2.0), CREAM, 5.0, 28.0, outline=hexc("#6B4A1E"), rim=False)
    cover = (hexc("#6FA0FF"), hexc("#2447B8"))
    ic.shape(sd_box(4.5, 3.0, 24.0, 26.0, 2.0), cover, 3.0, 26.0)
    ic.paint(sd_box(4.5, 3.0, 8.5, 26.0, 1.5), hexc("#1B3590", 0.55))
    gold_star = star_pts(16.5, 14.0, 5.2, 2.3)
    ic.paint(shift(sd_poly(gold_star), 0.4, 0.8), hexc("#0F2060", 0.5))
    ic.paint(sd_poly(gold_star), hexc("#FFE675"))
    ic.paint(sd_seg((12.0, 22.0), (21.0, 22.0), 1.4), hexc("#FFE675", 0.9))
    return ic


def icon_trophy():
    ic = Icon()
    ic.shape(sd_arc(7.5, 10.5, 2.8, 5.2, 90, 270), GOLD, 5.0, 16.0, outline=hexc("#7A4300"))
    ic.shape(sd_arc(24.5, 10.5, 2.8, 5.2, -90, 90), GOLD, 5.0, 16.0, outline=hexc("#7A4300"))
    cup = rnd(sd_poly([(9.0, 4.5), (23.0, 4.5), (22.5, 12.0), (19.5, 17.0), (12.5, 17.0), (9.5, 12.0)]), 1.2)
    ic.shape(cup, GOLD, 3.0, 18.5, outline=hexc("#7A4300"))
    ic.shape(sd_box(13.5, 17.5, 18.5, 23.5, 0.5), (hexc("#F2B93A"), hexc("#C27800")), 17.5, 23.5, outline=hexc("#7A4300"), out=0.9)
    ic.shape(sd_box(8.5, 23.0, 23.5, 28.5, 1.6), (hexc("#C98A2A"), hexc("#7A4A00")), 23.0, 28.5, outline=hexc("#4A2A00"), out=0.9)
    star = star_pts(16.0, 10.6, 4.6, 2.0)
    ic.paint(sd_poly(star), hexc("#FFFFFF", 0.9))
    ic.sparkle(11.5, 8.0, 2.4, 0.8)
    return ic


def icon_crown():
    ic = Icon()
    body = rnd(sd_poly([(4.5, 21.5), (4.5, 9.5), (10.8, 15.0), (16.0, 6.5), (21.2, 15.0), (27.5, 9.5), (27.5, 21.5)]), 1.0)
    ic.shape(body, GOLD, 4.0, 24.0, outline=hexc("#7A4300"))
    ic.shape(sd_box(4.0, 21.0, 28.0, 27.8, 1.5), (hexc("#F2B93A"), hexc("#C27800")), 21.0, 27.8, outline=hexc("#7A4300"), out=0.9)
    for (x, y, col) in ((4.6, 8.6, "#E04848"), (16.0, 5.4, "#3D8BFF"), (27.4, 8.6, "#E04848")):
        ic.shape(sd_circle(x, y, 2.3), (lighter(hexc(col), 0.4), hexc(col)), y - 2.3, y + 2.3, outline=hexc("#4A2A00"), out=0.8, rim=False)
    for (x, col) in ((9.5, "#3D8BFF"), (16.0, "#E04848"), (22.5, "#3D8BFF")):
        ic.paint(sd_circle(x, 24.4, 1.7), hexc(col))
    return ic


def _medal(colors):
    ic = Icon()
    ic.shape(sd_poly([(7.0, 1.5), (14.0, 1.5), (21.0, 16.0), (14.0, 16.0)]), RED, 1.5, 16.0, rim=False)
    ic.shape(sd_poly([(18.0, 1.5), (25.0, 1.5), (18.0, 16.0), (11.0, 16.0)]), BLUE, 1.5, 16.0, rim=False)
    disc = sd_circle(16.0, 20.5, 9.6)
    ic.shape(disc, colors, 10.5, 30.5)
    ic.paint(sd_ring(16.0, 20.5, 6.8, 7.8), darker(colors[1], 0.2))
    star = star_pts(16.0, 20.8, 5.0, 2.2)
    ic.paint(shift(sd_poly(star), 0.4, 0.7), darker(colors[1], 0.45))
    ic.paint(sd_poly(star), lighter(colors[0], 0.55))
    return ic


def icon_medal_gold():
    return _medal(GOLD)


def icon_medal_silver():
    return _medal(SILVER)


def icon_medal_bronze():
    return _medal(BRONZE)


def icon_fish():
    ic = Icon()
    fin = (hexc("#FF9B3D"), hexc("#D9560F"))
    out = hexc("#6B2A08")
    ic.shape(rnd(sd_poly([(20.0, 16.0), (28.0, 8.5), (26.8, 16.0), (28.0, 23.5)]), 0.8), fin, 7.0, 25.0, outline=out)
    ic.shape(rnd(sd_poly([(9.0, 9.5), (14.5, 4.0), (19.0, 9.5)]), 0.8), fin, 3.0, 10.0, outline=out)
    ic.shape(rnd(sd_poly([(12.0, 22.5), (15.5, 27.5), (19.0, 22.5)]), 0.8), fin, 22.0, 28.0, outline=out)
    body = ellipse(13.5, 16.0, 12.0, 8.0)
    ic.shape(body, (hexc("#FFC15E"), hexc("#F0701C")), 8.0, 24.0, outline=out)
    ic.paint(inter(body, inter(left_of(18.2), right_of(15.6))), (255, 255, 255, 0.85))
    ic.paint(inter(body, inter(left_of(13.0), right_of(11.4))), (255, 255, 255, 0.7))
    ic.paint(sd_circle(7.6, 14.2, 2.3), WHITE)
    ic.paint(sd_circle(7.3, 14.4, 1.2), hexc("#1B2F55"))
    return ic


def icon_rod():
    ic = Icon()
    line = union(sd_seg((23.5, 6.0), (28.0, 14.0), 1.1), sd_seg((28.0, 14.0), (28.0, 19.5), 1.1))
    hook = sd_arc(26.1, 19.5, 1.0, 2.8, 180, 360)
    ic.paint(union(line, hook), hexc("#2F3A4A"), grow=0.7)
    ic.paint(union(line, hook), hexc("#F2F6FA"))
    ic.shape(sd_seg((4.0, 28.0), (23.5, 6.0), 3.8), BROWN, 4.0, 29.0, outline=WOOD_OUT)
    ic.shape(sd_circle(10.0, 22.0, 4.4), DARKGRAY, 17.0, 27.0, outline=hexc("#1F2630"), out=0.9)
    ic.paint(sd_circle(10.0, 22.0, 1.5), hexc("#1F2630"))
    ic.sparkle(18.0, 12.0, 2.0, 0.6)
    return ic


def icon_pearl():
    ic = Icon()
    # Muschel als Unterlage
    fan = union(inter(sd_circle(16.0, 27.0, 14.0), above(27.0)), sd_box(12.0, 26.0, 20.0, 30.0, 1.5))
    ic.shape(fan, (hexc("#FFE3E8"), hexc("#E58FA3")), 13.0, 30.0, outline=hexc("#7A2D44"))
    rib = hexc("#9C3F5C", 0.55)
    for k in range(-3, 4):
        a = math.radians(-90 + k * 24)
        ic.paint(sd_seg((16.0, 28.0), (16.0 + 13.0 * math.cos(a), 27.0 + 13.0 * math.sin(a)), 0.8), rib)
    # Perle
    pearl = sd_circle(16.0, 13.0, 9.4)
    ic.paint(pearl, hexc("#6B7390"), grow=1.1)

    def col(x, y):
        t = min(1.0, math.hypot(x - 12.8, y - 9.6) / 14.5)
        c = mixc(hexc("#FFFFFF"), hexc("#C9D3EC"), t)
        if y > 15.0 and x > 15.0:
            c = mixc(c, hexc("#A9BDF0"), 0.35)
        return c
    ic.paint(pearl, col)
    ic.paint(ellipse(12.6, 9.4, 3.0, 2.0), (255, 255, 255, 0.95))
    ic.sparkle(19.5, 17.0, 1.6, 0.8)
    return ic


def icon_seemarke():
    ic = Icon()
    hexa = rnd(sd_poly([(16.0, 3.0), (24.5, 9.0), (24.5, 22.0), (16.0, 29.0), (7.5, 22.0), (7.5, 9.0)]), 1.0)
    ic.shape(hexa, TEAL, 2.0, 30.0, outline=hexc("#05444D"))
    ic.paint(inter(hexa, left_of(16.0)), (255, 255, 255, 0.22))
    ic.paint(inter(hexa, right_of(16.0)), (0, 40, 50, 0.2))
    ic.paint(sd_poly([(16.0, 3.5), (24.0, 9.2), (16.0, 15.0), (8.0, 9.2)]), (255, 255, 255, 0.3))
    line = hexc("#05444D", 0.5)
    ic.paint(sd_seg((16.0, 15.0), (16.0, 28.0), 0.8), line)
    ic.paint(sd_seg((8.0, 9.2), (16.0, 15.0), 0.8), line)
    ic.paint(sd_seg((24.0, 9.2), (16.0, 15.0), 0.8), line)
    ic.sparkle(11.5, 9.5, 2.8)
    return ic


def icon_dublone():
    ic = Icon()
    coin = _coin(ic, hexc("#FFD27A"), hexc("#D9650F"), hexc("#E88A1C"), hexc("#FFC864"),
                 hexc("#A84C00"), hexc("#5E2A00"))
    anchor = union(
        sd_ring(16.0, 9.3, 1.3, 2.9),
        sd_seg((16.0, 11.5), (16.0, 23.0), 2.4),
        sd_seg((11.8, 14.6), (20.2, 14.6), 2.2),
        sd_arc(16.0, 17.6, 5.2, 7.4, 200, 340),
    )
    _emboss(ic, anchor, hexc("#A04A00"), hexc("#6E3000"), hexc("#FFE3A0", 0.9), 8, 24)
    ic.gloss(coin, 2.0, 30.0, 0.22)
    ic.sparkle(9.0, 8.0, 3.2)
    return ic


def _person(ic, cx, s, colors):
    head_r, head_cy = 5.4 * s, 30.0 - 19.5 * s
    body_top = 30.0 - 11.5 * s
    w = 9.5 * s
    body = inter(sd_box(cx - w, body_top, cx + w, 38.0, 5.5 * s), above(29.4))
    ic.shape(body, colors, body_top, 30.0)
    ic.shape(sd_circle(cx, head_cy, head_r), colors, head_cy - head_r, head_cy + head_r)


def icon_user():
    ic = Icon()
    _person(ic, 16.0, 1.0, BLUE)
    return ic


def icon_users():
    ic = Icon()
    _person(ic, 10.5, 0.85, GREEN)
    _person(ic, 21.0, 1.0, BLUE)
    return ic


def icon_shield():
    ic = Icon()
    pts = [(16.0, 2.5), (27.0, 6.0), (27.0, 15.0), (23.5, 23.0), (16.0, 29.5), (8.5, 23.0), (5.0, 15.0), (5.0, 6.0)]
    sh = rnd(sd_poly(scale_pts(pts, 0.95, 16.0, 16.0)), 1.0)
    ic.shape(sh, RED, 2.0, 30.0)
    ic.paint(sd_poly(scale_pts(pts, 0.7, 16.0, 15.5)), (255, 255, 255, 0.16))
    star = star_pts(16.0, 15.6, 5.6, 2.4)
    ic.paint(shift(sd_poly(star), 0.4, 0.8), hexc("#6B0F0F", 0.5))
    ic.paint(sd_poly(star), WHITE)
    return ic


def icon_heart():
    ic = Icon()
    heart = union(sd_circle(10.8, 12.0, 7.6), sd_circle(21.2, 12.0, 7.6),
                  sd_poly([(3.6, 15.0), (28.4, 15.0), (16.0, 29.5)]))
    ic.shape(heart, HEART, 4.0, 30.0, outline=hexc("#5E0A1B"))
    ic.gloss(heart, 4.0, 30.0, 0.3)
    ic.sparkle(9.5, 10.0, 3.0)
    return ic


def icon_bell():
    ic = Icon()
    bell = union(sd_circle(16.0, 14.5, 8.7), sd_poly([(7.3, 14.5), (24.7, 14.5), (27.0, 23.0), (5.0, 23.0)]))
    ic.shape(sd_circle(16.0, 27.0, 2.9), (hexc("#F2B93A"), hexc("#C27800")), 24.0, 30.0, outline=hexc("#7A4300"), out=0.9)
    ic.shape(sd_circle(16.0, 5.0, 2.4), GOLD, 2.5, 8.0, outline=hexc("#7A4300"), out=0.9)
    ic.shape(bell, GOLD, 5.0, 24.0, outline=hexc("#7A4300"))
    ic.shape(sd_box(4.5, 22.0, 27.5, 25.5, 1.5), (hexc("#F2B93A"), hexc("#C27800")), 22.0, 25.5, outline=hexc("#7A4300"), out=0.9)
    ic.sparkle(11.5, 11.5, 2.8)
    return ic


def icon_mail():
    ic = Icon()
    ic.shape(sd_box(3.0, 7.0, 29.0, 25.5, 2.5), (hexc("#FFFFFF"), hexc("#D3DEEB")), 7.0, 25.5, outline=hexc("#44546A"))
    flap = sd_poly([(3.8, 7.8), (28.2, 7.8), (16.0, 18.0)])
    ic.paint(flap, vgrad(7, 18, hexc("#F4F8FC"), hexc("#B9C9DC")))
    ic.paint(sd_seg((3.8, 24.5), (13.0, 15.5), 1.2), hexc("#8FA2BA", 0.8))
    ic.paint(sd_seg((28.2, 24.5), (19.0, 15.5), 1.2), hexc("#8FA2BA", 0.8))
    ic.paint(sd_seg((4.5, 8.2), (16.0, 17.6), 1.3), hexc("#44546A"))
    ic.paint(sd_seg((27.5, 8.2), (16.0, 17.6), 1.3), hexc("#44546A"))
    ic.shape(sd_circle(16.0, 18.0, 2.7), RED, 15.0, 21.0, outline=hexc("#5E0A1B"), out=0.8, rim=False)
    return ic


def icon_chat():
    ic = Icon()
    bubble = union(sd_box(3.0, 4.5, 29.0, 22.0, 6.0), sd_poly([(7.0, 20.0), (7.5, 28.5), (16.5, 21.0)]))
    ic.shape(bubble, BLUE, 4.5, 28.5)
    ic.gloss(bubble, 4.5, 28.5, 0.28)
    for x in (10.0, 16.0, 22.0):
        ic.paint(sd_circle(x, 13.3, 1.9), WHITE)
    return ic


def icon_home():
    ic = Icon()
    ic.shape(sd_box(21.0, 4.0, 25.5, 12.0, 0.8), BROWN, 4.0, 12.0, outline=WOOD_OUT, out=0.9, rim=False)
    ic.shape(sd_box(6.0, 15.0, 26.0, 29.0, 1.0), CREAM, 15.0, 29.0, outline=hexc("#6B4A1E"))
    ic.shape(rnd(sd_poly([(16.0, 4.5), (28.0, 16.0), (4.0, 16.0)]), 1.6), RED, 3.0, 17.5)
    ic.shape(sd_box(13.0, 20.0, 19.0, 29.0, 1.2), BROWN, 20.0, 29.0, outline=WOOD_OUT, out=0.9, rim=False)
    ic.paint(sd_circle(17.6, 25.0, 0.7), hexc("#FFE675"))
    ic.shape(sd_box(8.0, 18.5, 11.5, 22.0, 0.6), CYAN, 18.5, 22.0, outline=hexc("#44546A"), out=0.7, rim=False)
    ic.shape(sd_box(20.5, 18.5, 24.0, 22.0, 0.6), CYAN, 18.5, 22.0, outline=hexc("#44546A"), out=0.7, rim=False)
    return ic


def icon_pin():
    ic = Icon()
    pin = union(sd_circle(16.0, 12.0, 9.6), sd_poly([(7.6, 16.0), (24.4, 16.0), (16.0, 30.0)]))
    ic.shape(pin, RED, 2.0, 30.5)
    ic.gloss(pin, 2.0, 30.5, 0.3)
    ic.paint(sd_circle(16.0, 12.0, 4.0), hexc("#5E0A1B", 0.6), grow=0.6)
    ic.paint(sd_circle(16.0, 12.0, 4.0), WHITE)
    return ic


def icon_gift():
    ic = Icon()
    gold = (hexc("#FFE675"), hexc("#EE9A12"))
    gold_out = hexc("#6B3F00")
    ic.shape(sd_box(4.5, 14.0, 27.5, 29.0, 2.0), RED, 14.0, 29.0)
    ic.shape(sd_box(14.0, 14.0, 18.0, 29.0, 0.4), gold, 14.0, 29.0, outline=gold_out, out=0.8, rim=False)
    ic.shape(sd_box(3.0, 9.5, 29.0, 16.5, 2.0), (hexc("#FF9AA8"), hexc("#E03A52")), 9.5, 16.5)
    ic.shape(sd_box(14.0, 9.5, 18.0, 16.5, 0.4), gold, 9.5, 16.5, outline=gold_out, out=0.8, rim=False)
    ic.shape(sd_ring(11.6, 6.2, 1.8, 4.8), gold, 1.4, 11.0, outline=gold_out, out=0.8, rim=False)
    ic.shape(sd_ring(20.4, 6.2, 1.8, 4.8), gold, 1.4, 11.0, outline=gold_out, out=0.8, rim=False)
    ic.shape(sd_circle(16.0, 9.3, 2.5), gold, 6.8, 11.8, outline=gold_out, out=0.8, rim=False)
    return ic


def icon_key():
    ic = Icon()
    ic.shape(sd_ring(9.5, 10.5, 3.2, 7.4), GOLD, 3.0, 18.0, outline=hexc("#7A4300"))
    shaft = union(sd_seg((13.5, 14.5), (27.0, 28.0), 3.6),
                  sd_seg((21.0, 22.5), (25.0, 18.5), 3.0),
                  sd_seg((25.0, 26.5), (28.8, 22.7), 3.0))
    ic.shape(shaft, GOLD, 10.0, 30.0, outline=hexc("#7A4300"))
    ic.sparkle(7.0, 7.0, 2.4, 0.8)
    return ic


def icon_dice():
    ic = Icon()
    die = sd_box(3.5, 3.5, 28.5, 28.5, 5.5)
    ic.shape(die, (hexc("#FFFFFF"), hexc("#CFD8E4")), 3.5, 28.5, outline=hexc("#44546A"))
    for (x, y) in ((9.5, 9.5), (22.5, 9.5), (16.0, 16.0), (9.5, 22.5), (22.5, 22.5)):
        ic.paint(shift(sd_circle(x, y, 2.5), 0.3, 0.6), hexc("#7A1010", 0.4))
        ic.paint(sd_circle(x, y, 2.5), vgrad(y - 2.5, y + 2.5, hexc("#FF6B6B"), hexc("#C62828")))
    return ic


def _sword_shape():
    blade = sd_poly([(16.0, 1.0), (19.4, 6.0), (19.4, 21.0), (12.6, 21.0), (12.6, 6.0)])
    return rot(blade, 45)


def icon_sword():
    ic = Icon()
    ic.shape(rot(sd_box(14.4, 23.5, 17.6, 29.5, 0.8), 45), BROWN, 0.0, 32.0, outline=WOOD_OUT, out=0.9, rim=False)
    ic.shape(rot(sd_circle(16.0, 30.0, 1.7), 45), GOLD, 0.0, 32.0, outline=hexc("#7A4300"), out=0.8, rim=False)
    ic.shape(rnd(_sword_shape(), 0.0), CYAN, 0.0, 32.0, outline=hexc("#0F4A66"))
    ic.paint(rot(sd_seg((16.0, 4.0), (16.0, 20.0), 1.0), 45), (255, 255, 255, 0.6))
    ic.shape(rot(sd_box(8.5, 21.0, 23.5, 24.0, 1.2), 45), GOLD, 0.0, 32.0, outline=hexc("#7A4300"), out=0.9)
    return ic


def icon_skull():
    ic = Icon()
    skull = union(sd_circle(16.0, 13.5, 11.2), sd_box(9.5, 17.0, 22.5, 28.0, 3.0))
    ic.shape(skull, (hexc("#FFFFFF"), hexc("#C2CCD8")), 2.0, 28.0, outline=hexc("#2B3440"))
    dark = hexc("#2B3440")
    ic.paint(sd_circle(11.3, 14.2, 3.2), dark)
    ic.paint(sd_circle(20.7, 14.2, 3.2), dark)
    ic.paint(sd_poly([(16.0, 17.2), (14.4, 20.6), (17.6, 20.6)]), dark)
    for x in (13.0, 16.0, 19.0):
        ic.paint(sd_seg((x, 22.6), (x, 27.4), 1.0), hexc("#6C7A8C"))
    return ic


def icon_feather():
    ic = Icon()
    vane = ellipse(16.0, 15.0, 6.0, 14.0)
    ic.shape(rot(vane, 45), (hexc("#FFFFFF"), hexc("#8FBFF0")), 0.0, 32.0, outline=hexc("#35609A"))
    ic.paint(rot(sd_seg((16.0, 2.0), (16.0, 31.0), 1.4), 45), hexc("#35609A", 0.85))
    ic.paint(rot(sd_seg((16.0, 22.0), (11.5, 18.0), 0.9), 45), hexc("#35609A", 0.5))
    ic.paint(rot(sd_seg((16.0, 14.0), (11.5, 10.0), 0.9), 45), hexc("#35609A", 0.5))
    return ic


def icon_xp():
    ic = Icon()
    glass = union(sd_circle(16.0, 20.0, 9.8), sd_box(12.4, 7.0, 19.6, 16.0, 1.0))
    ic.shape(glass, (hexc("#F2FBFF"), hexc("#A9CFE0")), 6.0, 30.0, outline=hexc("#2E5A70"))
    liquid = union(sd_circle(16.0, 20.4, 7.8), sd_box(13.8, 12.0, 18.2, 18.0))
    ic.paint(liquid, vgrad(12, 28, hexc("#D5FF7A"), hexc("#35B81A")))
    ic.shape(sd_box(10.8, 5.0, 21.2, 8.6, 1.2), (hexc("#E6F3FA"), hexc("#9DBFD0")), 5.0, 8.6, outline=hexc("#2E5A70"), out=0.8, rim=False)
    ic.shape(sd_box(13.4, 1.8, 18.6, 6.0, 0.8), BROWN, 1.8, 6.0, outline=WOOD_OUT, out=0.8, rim=False)
    ic.sparkle(12.2, 18.0, 2.4, 0.9)
    return ic


def icon_cart():
    ic = Icon()
    frame = union(sd_seg((3.0, 5.5), (7.0, 5.5), 2.4), sd_seg((7.0, 5.5), (10.5, 20.5), 2.4),
                  sd_seg((10.5, 20.5), (26.5, 20.5), 2.4))
    ic.shape(frame, STEEL, 4.0, 22.0, outline=hexc("#2F3A4A"), out=0.9)
    basket = rnd(sd_poly([(8.6, 9.8), (28.4, 9.8), (25.6, 17.6), (10.8, 17.6)]), 0.8)
    ic.shape(basket, GREEN, 9.0, 18.5)
    for x in (13.5, 18.5, 23.5):
        ic.paint(sd_seg((x, 11.2), (x - 0.4, 16.4), 0.9), hexc("#0B5A22", 0.45))
    for x in (12.5, 24.0):
        ic.shape(sd_circle(x, 25.8, 2.8), DARKGRAY, 23.0, 28.6, outline=hexc("#1F2630"), out=0.9)
    return ic


def icon_tag():
    ic = Icon()
    tag = rnd(sd_poly([(3.8, 16.0), (12.5, 7.0), (27.2, 7.0), (27.2, 25.0), (12.5, 25.0)]), 1.4)
    ic.shape(tag, ORANGE, 5.0, 27.0)
    ic.paint(sd_circle(9.4, 16.0, 2.3), hexc("#6B2A08", 0.7), grow=0.5)
    ic.paint(sd_circle(9.4, 16.0, 2.3), hexc("#FFF6E0"))
    for y, x1 in ((12.0, 23.5), (16.0, 21.0), (20.0, 23.5)):
        ic.paint(sd_seg((14.5, y), (x1, y), 1.8), hexc("#FFFFFF", 0.9))
    return ic


def icon_gavel():
    ic = Icon()
    ic.shape(sd_box(13.0, 26.5, 30.0, 30.5, 1.6), DARKGRAY, 26.5, 30.5, outline=hexc("#1F2630"), out=0.9)
    ic.shape(rot(sd_seg((16.0, 12.0), (16.0, 27.0), 3.8), -40), (hexc("#E8B27A"), hexc("#A8672F")), 0.0, 32.0, outline=WOOD_OUT)
    wood = (hexc("#E3A767"), hexc("#8A5326"))
    ic.shape(rot(sd_box(6.0, 3.5, 26.0, 12.5, 3.0), -40), wood, 0.0, 32.0, outline=WOOD_OUT)
    for x0 in (8.5, 21.0):
        ic.paint(rot(sd_box(x0, 3.5, x0 + 2.4, 12.5, 0.4), -40), hexc("#4A2A0E", 0.55))
    return ic


def icon_swap():
    ic = Icon()
    top = union(sd_seg((4.5, 10.0), (20.5, 10.0), 4.6), sd_poly([(19.5, 3.0), (29.0, 10.0), (19.5, 17.0)]))
    ic.shape(rnd(top, 0.0), GREEN, 2.0, 18.0)
    bottom = mirror(union(sd_seg((4.5, 22.0), (20.5, 22.0), 4.6), sd_poly([(19.5, 15.0), (29.0, 22.0), (19.5, 29.0)])))
    ic.shape(rnd(bottom, 0.0), BLUE, 14.0, 30.0)
    return ic


def icon_chart():
    ic = Icon()
    ic.shape(sd_box(4.5, 17.0, 10.5, 28.0, 1.2), BLUE, 17.0, 28.0)
    ic.shape(sd_box(13.0, 11.0, 19.0, 28.0, 1.2), GREEN, 11.0, 28.0)
    ic.shape(sd_box(21.5, 4.0, 27.5, 28.0, 1.2), GOLD, 4.0, 28.0, outline=hexc("#7A4300"))
    ic.paint(sd_seg((3.0, 29.2), (29.0, 29.2), 1.6), hexc("#2F3A4A"))
    return ic


def icon_trash():
    ic = Icon()
    can = rnd(sd_poly([(8.4, 11.5), (23.6, 11.5), (22.0, 27.6), (10.0, 27.6)]), 1.2)
    ic.shape(can, STEEL, 9.0, 29.0, outline=hexc("#2F3A4A"))
    for x in (12.6, 16.0, 19.4):
        ic.paint(sd_seg((x, 14.6), (x - (x - 16.0) * 0.12, 24.8), 1.5), hexc("#56657A", 0.8))
    ic.shape(sd_box(12.2, 3.0, 19.8, 7.4, 1.4), DARKGRAY, 3.0, 7.4, outline=hexc("#1F2630"), out=0.8, rim=False)
    ic.shape(sd_box(4.5, 6.6, 27.5, 11.0, 1.6), DARKGRAY, 6.6, 11.0, outline=hexc("#1F2630"), out=0.9)
    return ic


def icon_edit():
    ic = Icon()
    out = hexc("#5A3A12")
    ic.shape(rot(sd_box(12.4, 7.8, 19.6, 24.0, 0.5), 45), (hexc("#FFE675"), hexc("#EE9A12")), 0.0, 32.0, outline=out)
    ic.shape(rot(sd_poly([(12.4, 24.0), (19.6, 24.0), (16.0, 30.5)]), 45), (hexc("#F6D9AE"), hexc("#C99A5A")), 0.0, 32.0, outline=out, out=0.9)
    ic.paint(rot(sd_poly([(14.6, 28.0), (17.4, 28.0), (16.0, 30.5)]), 45), hexc("#2B3440"))
    ic.shape(rot(sd_box(12.4, 5.0, 19.6, 8.4, 0.4), 45), STEEL, 0.0, 32.0, outline=out, out=0.9, rim=False)
    ic.shape(rot(sd_box(12.4, 1.2, 19.6, 5.4, 1.8), 45), (hexc("#FF9AA8"), hexc("#E03A52")), 0.0, 32.0, outline=out, out=0.9)
    return ic


def _eye_lens():
    return inter(sd_circle(16.0, 25.3, 16.8), sd_circle(16.0, 6.7, 16.8))


def icon_eye():
    ic = Icon()
    lens = _eye_lens()
    ic.shape(lens, (hexc("#FFFFFF"), hexc("#D3DEEB")), 8.0, 24.0, outline=hexc("#2F3A4A"), rim=False)
    iris = inter(sd_circle(16.0, 16.0, 6.4), lens)
    ic.paint(iris, vgrad(10, 22, hexc("#6FCEFF"), hexc("#1E6FD6")))
    ic.paint(sd_circle(16.0, 16.0, 2.9), hexc("#10243F"))
    ic.paint(sd_circle(17.8, 14.2, 1.4), WHITE)
    return ic


def icon_eye_off():
    ic = icon_eye()
    ic.shape(sd_seg((5.5, 27.0), (26.5, 5.0), 3.6), RED, 3.0, 29.0, outline=hexc("#5E0A1B"))
    return ic


def icon_grass():
    ic = Icon()
    top = sd_poly([(16.0, 3.0), (29.0, 10.0), (16.0, 17.0), (3.0, 10.0)])
    left = sd_poly([(3.0, 10.0), (16.0, 17.0), (16.0, 30.0), (3.0, 23.0)])
    right = sd_poly([(16.0, 17.0), (29.0, 10.0), (29.0, 23.0), (16.0, 30.0)])
    whole = sd_poly([(16.0, 3.0), (29.0, 10.0), (29.0, 23.0), (16.0, 30.0), (3.0, 23.0), (3.0, 10.0)])
    ic.paint(whole, hexc("#2A1A08"), grow=1.1)
    ic.paint(left, vgrad(10, 30, hexc("#B97A43"), hexc("#8A5326")))
    ic.paint(right, vgrad(10, 30, hexc("#9A6232"), hexc("#6E4020")))
    ic.paint(top, vgrad(3, 17, hexc("#8FE35A"), hexc("#3FA82E")))
    # Grasrand an den Seiten
    ic.paint(sd_poly([(3.0, 10.0), (16.0, 17.0), (16.0, 20.5), (3.0, 13.5)]), hexc("#4CB634"))
    ic.paint(sd_poly([(16.0, 17.0), (29.0, 10.0), (29.0, 13.5), (16.0, 20.5)]), hexc("#37962A"))
    dirt = hexc("#4A2A0E", 0.45)
    for (x, y) in ((7.0, 19.0), (11.0, 24.0), (12.5, 20.5), (20.5, 22.5), (24.5, 17.5), (20.0, 27.0)):
        ic.paint(sd_box(x, y, x + 1.8, y + 1.8, 0.2), dirt)
    ic.sparkle(10.0, 9.0, 2.2, 0.7)
    return ic


def icon_block():
    ic = Icon()
    sign = union(sd_ring(16.0, 16.0, 9.4, 13.8), sd_seg((7.2, 7.2), (24.8, 24.8), 4.4))
    ic.shape(sign, RED, 2.0, 30.0, outline=hexc("#5E0A1B"))
    return ic


def _dot(colors, outline):
    ic = Icon()
    dot = sd_circle(16.0, 16.0, 9.5)
    ic.shape(dot, colors, 6.0, 26.0, outline=outline)
    ic.gloss(dot, 6.0, 26.0, 0.35)
    return ic


def icon_online():
    return _dot(GREEN, hexc("#0B4A1C"))


def icon_offline():
    return _dot(DARKGRAY, hexc("#1F2630"))


def icon_hourglass():
    ic = Icon()
    glass = union(sd_poly([(8.5, 6.0), (23.5, 6.0), (17.0, 16.0), (15.0, 16.0)]),
                  sd_poly([(15.0, 16.0), (17.0, 16.0), (23.5, 26.0), (8.5, 26.0)]))
    ic.shape(glass, (hexc("#F2FBFF"), hexc("#A9CFE0")), 5.0, 27.0, outline=hexc("#2E5A70"), rim=False)
    sand = hexc("#F0B93A")
    ic.paint(sd_poly([(11.4, 7.6), (20.6, 7.6), (16.9, 13.4), (15.1, 13.4)]), vgrad(7, 14, hexc("#FFD76A"), hexc("#E39A12")))
    ic.paint(sd_poly([(10.0, 25.0), (22.0, 25.0), (16.9, 19.0), (15.1, 19.0)]), vgrad(19, 25, hexc("#FFD76A"), hexc("#E39A12")))
    ic.paint(sd_seg((16.0, 14.0), (16.0, 19.0), 0.9), sand)
    for y0 in (2.5, 25.5):
        ic.shape(sd_box(5.0, y0, 27.0, y0 + 4.0, 1.5), GOLD, y0, y0 + 4.0, outline=hexc("#7A4300"), out=0.9)
    return ic


def icon_calendar():
    ic = Icon()
    page = sd_box(4.0, 5.0, 28.0, 28.5, 3.0)
    ic.shape(page, (hexc("#FFFFFF"), hexc("#D3DEEB")), 5.0, 28.5, outline=hexc("#44546A"), rim=False)
    ic.paint(inter(page, above(12.5)), vgrad(5, 12.5, hexc("#FF7B7B"), hexc("#D32F2F")))
    for x in (9.5, 19.5):
        ic.shape(sd_box(x, 2.0, x + 3.0, 8.0, 1.2), STEEL, 2.0, 8.0, outline=hexc("#2F3A4A"), out=0.8, rim=False)
    grid = hexc("#B3C2D6")
    for y in (15.5, 21.5):
        for x in (7.5, 14.0, 20.5):
            if (x, y) == (20.5, 21.5):
                ic.shape(sd_box(x, y, x + 4.2, y + 3.8, 0.8), BLUE, y, y + 3.8, outline=hexc("#0F3F7F"), out=0.7, rim=False)
            else:
                ic.paint(sd_box(x, y, x + 4.2, y + 3.8, 0.8), grid)
    return ic


def icon_cookie():
    ic = Icon()
    cookie = sub(sd_circle(16.0, 16.0, 13.2), sd_circle(27.0, 6.5, 6.4))
    ic.shape(cookie, (hexc("#EDB36B"), hexc("#B4702E")), 2.0, 30.0, outline=hexc("#5A3210"))
    chip = hexc("#4A2A0E")
    for (x, y, r) in ((9.5, 11.0, 2.2), (15.5, 12.5, 1.9), (9.0, 20.5, 2.0), (16.0, 20.0, 2.3), (22.5, 21.0, 2.0), (21.5, 14.5, 1.7)):
        ic.paint(sd_circle(x, y, r), chip)
    ic.sparkle(8.0, 7.5, 2.2, 0.7)
    return ic


# ── Batch 3: Bausteine fuer Dialoge/Menues ──────────────────────────────────

def _badge_box(ic):
    box = sd_box(3.5, 3.5, 28.5, 28.5, 5.5)
    ic.shape(box, (hexc("#2E2548"), hexc("#1B1530")), 3.5, 28.5, outline=hexc("#FF5A6A"), out=1.9, rim=False)
    return box


def icon_badge_star():
    ic = Icon()
    _badge_box(ic)
    ic.shape(sd_poly(star_pts(16.0, 16.8, 8.8, 3.9)), GOLD, 7.0, 25.0, outline=hexc("#7A4300"), out=0.8)
    return ic


def icon_badge_close():
    ic = Icon()
    _badge_box(ic)
    x = union(sd_seg((10.5, 10.5), (21.5, 21.5), 3.6), sd_seg((21.5, 10.5), (10.5, 21.5), 3.6))
    ic.shape(x, (hexc("#FF8A96"), hexc("#E03A52")), 9.0, 23.0, outline=hexc("#5E0A1B"), out=0.7, rim=False)
    return ic


def icon_chevron():
    ic = Icon()
    s = union(sd_seg((12.0, 7.0), (21.0, 16.0), 3.8), sd_seg((21.0, 16.0), (12.0, 25.0), 3.8))
    ic.shape(s, (hexc("#D5D9EA"), hexc("#8B91AA")), 5.0, 27.0, outline=hexc("#2A2745"), out=0.8, rim=False)
    return ic


# ── Batch 4: Lager (Amethyst-Theme) ─────────────────────────────────────────

def icon_arrow_up():
    ic = Icon()
    head = sd_poly([(16.0, 3.5), (28.0, 16.5), (4.0, 16.5)])
    tail = sd_box(11.5, 14.0, 20.5, 28.5, 1.0)
    ic.shape(rnd(union(head, tail), 1.0), GREEN, 3.0, 29.0)
    return ic


def _double_chevron(down):
    ic = Icon()
    lo, hi = 7.0, 25.0
    segs = []
    for y in (7.5, 16.5):
        a, b, c = ((6.5, y), (16.0, y + 9.0), (25.5, y)) if down else ((6.5, y + 9.0), (16.0, y), (25.5, y + 9.0))
        segs += [sd_seg(a, b, 4.4), sd_seg(b, c, 4.4)]
    ic.shape(union(*segs), (hexc("#8FE3FF"), hexc("#1E88E5")), lo - 4, hi + 6, outline=hexc("#0B3A75"), out=1.0)
    return ic


def icon_double_up():
    return _double_chevron(False)


def icon_double_down():
    return _double_chevron(True)


# ── Batch 5: Warp / Farmwelt (Panel-Themes) ─────────────────────────────────

def icon_ender_pearl():
    """Enderperle: tuerkise Kugel mit dunklem Kern und Glanzlicht (Warp-Theme, End-Farmwelt)."""
    ic = Icon()
    pearl = sd_circle(16.0, 16.5, 12.0)
    ic.paint(pearl, hexc("#06332D"), grow=1.2)

    def col(x, y):
        t = min(1.0, math.hypot(x - 12.0, y - 11.5) / 17.0)
        return mixc(hexc("#8FF2DA"), hexc("#14695C"), t)
    ic.paint(pearl, col)
    ic.paint(sd_circle(17.2, 17.8, 5.2), hexc("#0C4C42", 0.85))
    ic.paint(sd_circle(17.2, 17.8, 2.6), hexc("#08332C", 0.9))
    ic.paint(ellipse(11.5, 10.5, 3.4, 2.4), (255, 255, 255, 0.9))
    ic.sparkle(23.5, 23.0, 1.8, 0.75)
    return ic


# name -> (Zeichen, Funktion); die Zeichen werden der Reihenfolge nach ab U+E000 vergeben,
# neue Icons also nur HINTEN anhaengen, sonst aendern sich bestehende Zeichen.
_ICON_LIST = [
    # Batch 1 (U+E000 - U+E014)
    ("back", icon_back), ("next", icon_next), ("refresh", icon_refresh), ("check", icon_check),
    ("close", icon_close), ("tokens", icon_tokens), ("juwelen", icon_juwelen), ("search", icon_search),
    ("info", icon_info), ("warning", icon_warning), ("lock", icon_lock), ("unlock", icon_unlock),
    ("settings", icon_settings), ("toggle_on", icon_toggle_on), ("toggle_off", icon_toggle_off),
    ("plus", icon_plus), ("minus", icon_minus), ("bank", icon_bank), ("star", icon_star),
    ("clock", icon_clock), ("booster", icon_booster),
    # Batch 2
    ("pickaxe", icon_pickaxe), ("shard", icon_shard), ("minepoints", icon_minepoints),
    ("percent", icon_percent), ("flame", icon_flame), ("moneybag", icon_moneybag),
    ("chest", icon_chest), ("pass", icon_pass), ("quest", icon_quest), ("book", icon_book),
    ("trophy", icon_trophy), ("crown", icon_crown), ("medal_gold", icon_medal_gold),
    ("medal_silver", icon_medal_silver), ("medal_bronze", icon_medal_bronze),
    ("fish", icon_fish), ("rod", icon_rod), ("pearl", icon_pearl), ("seemarke", icon_seemarke),
    ("dublone", icon_dublone), ("user", icon_user), ("users", icon_users), ("shield", icon_shield),
    ("heart", icon_heart), ("bell", icon_bell), ("mail", icon_mail), ("chat", icon_chat),
    ("home", icon_home), ("pin", icon_pin), ("gift", icon_gift), ("key", icon_key),
    ("dice", icon_dice), ("sword", icon_sword), ("skull", icon_skull), ("feather", icon_feather),
    ("xp", icon_xp), ("cart", icon_cart), ("tag", icon_tag), ("gavel", icon_gavel),
    ("swap", icon_swap), ("chart", icon_chart), ("trash", icon_trash), ("edit", icon_edit),
    ("eye", icon_eye), ("eye_off", icon_eye_off), ("grass", icon_grass), ("block", icon_block),
    ("online", icon_online), ("offline", icon_offline), ("hourglass", icon_hourglass),
    ("calendar", icon_calendar), ("cookie", icon_cookie),
    # Batch 3
    ("badge_star", icon_badge_star), ("badge_close", icon_badge_close), ("chevron", icon_chevron),
    # Batch 4 (Lager)
    ("arrow_up", icon_arrow_up), ("double_up", icon_double_up), ("double_down", icon_double_down),
    # Batch 5 (Warp / Farmwelt)
    ("ender_pearl", icon_ender_pearl),
]

# Abstandszeichen (Font-Provider "space") und Balkensegment liegen im oberen Private-Use-Bereich,
# damit sie nie mit den durchnummerierten Icons kollidieren.
SPACE_NEG = {1: "\uF801", 2: "\uF808", 4: "\uF809", 8: "\uF80A", 16: "\uF80B", 32: "\uF80C"}
SPACE_POS = {1: "\uF802", 2: "\uF803", 4: "\uF804", 8: "\uF805", 16: "\uF806", 32: "\uF807"}
BAR_SEGMENT = "\uF810"
ICONS = {name: (chr(0xE000 + i), fn) for i, (name, fn) in enumerate(_ICON_LIST)}

# ── Panel-Bausteine fuer Menues ─────────────────────────────────────────────
# Das Menue-Hintergrundbild wird aus Kacheln zusammengesetzt, damit es jede Hoehe haben kann:
#   - Rahmen: Kopfzeile (oben, mit roter Linie), Mittelstueck, Fusszeile (unten), je 4 Kacheln nebeneinander.
#     Jede Kachel ist PANEL_UNIT Pixel hoch. Die Kachelreihe r sitzt r*PANEL_UNIT Pixel unter der Oberkante;
#     das erreicht Minecraft ueber den "ascent" des Zeichens. Darum gibt es pro Reihe eigene Zeichen
#     (mehrere Eintraege in der Font, die dieselbe PNG benutzen).
#   - Karte: Profilkarte, 4 Kacheln, fuer Menues mit Kopfbereich.
#   - Stern: grosses Stern-Icon fuer die Karte.
# Minecraft laedt Schriftbilder nur bis 256x256 Pixel, groessere erscheinen als weisses Kaestchen.
PANEL_W = 256
PANEL_COLS, PANEL_TILE_W = 4, 64
PANEL_UNIT = 12                # Hoehe einer Kachelreihe in GUI-Pixeln
PANEL_ROWS_MAX = 24            # maximale Reihenzahl -> Panelhoehe bis 288 Pixel
PANEL_ASCENT = 7               # Oberkante des Panels = Oberkante der ersten Zeile
PANEL_TOP_BASE, PANEL_MID_BASE, PANEL_BOT_BASE = 0xE100, 0xE200, 0xE300   # + Reihe*4 + Spalte
# Untere Kachel mit der Randlinie in einer hoeheren Pixelzeile der Kachel (nicht ganz unten), damit das Panel
# auf den Pixel genau enden kann. Variante v (PANEL_BOT_VAR_MIN..PANEL_UNIT-2) hat die Linie in Kachelzeile v;
# Variante PANEL_UNIT-1 ist die normale untere Kachel. Zeichen = Basis + ((v - MIN) * PANEL_ROWS_MAX + Reihe) * 4 + Spalte.
# Ab Zeile 2, damit die abgerundete Ecke (3 Pixel) noch in die Kachel passt.
PANEL_BOT_VAR_BASE = 0xE500
PANEL_BOT_VAR_MIN = 2
PANEL_SCALE = 2

# Button-Hintergrund fuer Textbuttons im Panel (sitzt im Text, nicht als echter Dialog-Button):
# links (59 Pixel), Mitte (60 Pixel, beliebig oft wiederholbar) und rechts (59 Pixel), 27 Pixel hoch (= drei\r\n# Textzeilen, damit der ganze Button klickbar ist). Sichtbar sind davon 24 Pixel (Zeile 1 bis 24), der Rest ist Abstand.
# Breite 118 = links + rechts, 238 = links + 2x Mitte + rechts.
BTN_H = 27
BTN_TOP, BTN_BOTTOM = 1, 25        # sichtbarer Teil des Buttons in der Kachel
BTN_END_W, BTN_MID_W = 59, 60
BTN_ASCENT = 7                 # Oberkante der Kachel = Oberkante der Zeile, in der sie steht
BTN_LEFT_CHAR, BTN_MID_CHAR, BTN_RIGHT_CHAR = "\uE900", "\uE901", "\uE902"
BTN_FILL = ("#1E1A33", "#181428")
BTN_BORDER = "#3B3558"
BTN_LIGHT = "#2A2547"

CARD_COLS, CARD_TILE_W = 4, 60
CARD_W, CARD_H = 240, 34       # x = 8 .. 248 im Panel
CARD_X = 8
CARD_BASE = 0xE400             # + Spalte
CARD_ASCENT = 1                # Oberkante der Karte = 6 Pixel unter der Oberkante der Zeile, in der sie steht

STAR_BIG_CHAR = "\uE410"
STAR_BIG_H = 24
TOKENS_BIG_SCALE = 3          # Aufloesung der grossen Token-Muenze: 3 Texturpixel je Einheit (96 x 96)
TOKENS_BIG_CHAR = "\uE411"      # grosse Token-Muenze, gleiche Groesse und Lage wie der Stern
STAR_BIG_ASCENT = -4           # zentriert den Stern in der Karte
STAR_X = 18                    # linke Kante des Sterns im Panel
NAME_X = 50                    # Textbeginn in der Karte
TEXT_RIGHT = 240               # rechter Textrand in der Karte

X_BIG_CHAR = "\uF831"          # das Schliessen-X (badge_close) in 14 Pixeln Hoehe
X_BIG_H, X_BIG_ASCENT = 14, 3  # sitzt 4 Pixel unter der Panel-Oberkante
X_BIG_X = 234                  # linke Kante des Schliessen-X

PANEL_FILL = "#16122B"
PANEL_BORDER = "#3B3558"
RED_LINE = ("#FF5A6A", "#FFB347")


def _shift_x(f, dx):
    return lambda x, y: f(x + dx, y)


def make_panel_tile(kind, col):
    """Eine Kachel des Rahmens. kind: "top", "mid" oder "bot"."""
    u = PANEL_UNIT
    ic = Icon(PANEL_TILE_W, u, scale=PANEL_SCALE, ss=3)
    if kind == "top":
        outer, inner = sd_box(0, 0, PANEL_W, 60, 3), sd_box(1, 1, PANEL_W - 1, 61, 2)
    elif kind == "mid":
        outer, inner = sd_box(0, -20, PANEL_W, u + 20, 0), sd_box(1, -21, PANEL_W - 1, u + 21, 0)
    else:
        outer, inner = sd_box(0, -60, PANEL_W, u, 3), sd_box(1, -61, PANEL_W - 1, u - 1, 2)
    ox = col * PANEL_TILE_W
    outer, inner = _shift_x(outer, ox), _shift_x(inner, ox)
    ic.paint(outer, hexc(PANEL_FILL))
    ic.paint(sub(outer, inner), hexc(PANEL_BORDER))
    if kind == "top":
        ic.paint(inter(outer, above(2.0)),
                 lambda x, y: mixc(hexc(RED_LINE[0]), hexc(RED_LINE[1]), (x + ox) / PANEL_W))
    return ic


def make_panel_bottom_variant(col, v):
    """Untere Kachel, deren Randlinie in Kachelzeile v liegt (darunter ist die Kachel leer)."""
    u = PANEL_UNIT
    b = v + 1
    ic = Icon(PANEL_TILE_W, u, scale=PANEL_SCALE, ss=3)
    outer, inner = sd_box(0, -60, PANEL_W, b, 3), sd_box(1, -61, PANEL_W - 1, b - 1, 2)
    ox = col * PANEL_TILE_W
    outer, inner = _shift_x(outer, ox), _shift_x(inner, ox)
    ic.paint(outer, hexc(PANEL_FILL))
    ic.paint(sub(outer, inner), hexc(PANEL_BORDER))
    return ic


def make_button_tile(kind):
    """Teil eines Button-Hintergrunds: "left", "mid" oder "right" (dunkel, 1 Pixel Rand, hellere Oberkante)."""
    w = BTN_MID_W if kind == "mid" else BTN_END_W
    ic = Icon(w, BTN_H, scale=PANEL_SCALE, ss=3)
    x0 = 0 if kind == "left" else -200       # ausserhalb der Kachel gibt es keinen Rand
    x1 = w if kind == "right" else 200
    outer = sd_box(x0, BTN_TOP, x1, BTN_BOTTOM, 3)
    inner = sd_box(x0 + 1, BTN_TOP + 1, x1 - 1, BTN_BOTTOM - 1, 2.2)
    ic.paint(outer, hexc(BTN_BORDER))
    ic.paint(inner, vgrad(BTN_TOP + 1, BTN_BOTTOM - 1, hexc(BTN_FILL[0]), hexc(BTN_FILL[1])))
    ic.paint(inter(inner, above(BTN_TOP + 2.0)), hexc(BTN_LIGHT))
    return ic


def make_card_tile(col):
    """Eine Kachel der Profilkarte (Rahmen mit Farbverlauf rot -> orange, roter Balken links)."""
    ic = Icon(CARD_TILE_W, CARD_H, scale=PANEL_SCALE, ss=3)
    ox = col * CARD_TILE_W
    card = _shift_x(sd_box(0, 0, CARD_W, CARD_H, 3), ox)
    ic.paint(card, vgrad(0, CARD_H, hexc("#261C3D"), hexc("#1B1530")))
    inner = _shift_x(sd_box(1.2, 1.2, CARD_W - 1.2, CARD_H - 1.2, 2), ox)
    ic.paint(sub(card, inner), lambda x, y: mixc(hexc(RED_LINE[0]), hexc(RED_LINE[1]), (x + ox) / CARD_W))
    ic.paint(inter(card, _shift_x(left_of(3.5), ox)), hexc(RED_LINE[0]))
    return ic


def panel_char(base, row, col):
    return chr(base + row * PANEL_COLS + col)

def glyph_advance(rows, height):
    """Vorschub, den Minecraft einem Bitmap-Zeichen gibt: int(0.5 + Breite * Skalierung) + 1."""
    h = len(rows)
    maxcol = max((x for row in rows for x, c in enumerate(row) if c[3] > 0), default=-1)
    return int(0.5 + (maxcol + 1) * height / h) + 1


def render_by_name(name):
    return name, ICONS[name][1]().render()


def make_pack_png(gem_rows):
    bg = blank(64, 64, (24, 12, 40, 255))
    for y in range(64):
        for x in range(64):
            if x < 2 or y < 2 or x > 61 or y > 61:
                bg[y][x] = (162, 53, 255, 255)
    blend(bg, scale_nearest(gem_rows, 2), 0, 0)
    return bg


def write_preview(path, rendered, per_row=12, scale=3):
    """Kontaktbogen aller Icons (nur zum Anschauen, landet in dist/ und nicht im Pack)."""
    cell = N + 12
    rows_n = -(-len(rendered) // per_row)
    sheet = blank(cell * per_row + 12, cell * rows_n + 12, (60, 60, 70, 255))
    for i, name in enumerate(ICONS):
        blend(sheet, rendered[name], 12 + (i % per_row) * cell, 12 + (i // per_row) * cell)
    write_png(path, scale_nearest(sheet, scale))


# Ordner des FMC-Plugins (Monorepo). Standard: der Nachbarordner "FMC-Plugin"; ueber die
# Umgebungsvariable FMC_PLUGIN_DIR anpassbar. Fehlt der Ordner, wird kein Enum geschrieben.
PLUGIN_DIR = os.path.abspath(os.environ.get("FMC_PLUGIN_DIR") or os.path.join(ROOT, "..", "FMC-Plugin"))
JAVA_ENUM = os.path.join(PLUGIN_DIR, "src", "main", "java", "com", "example", "myplugin", "ui", "UiIcon.java")


def write_java_enum(icon_adv, big_adv, info):
    """Schreibt Zeichen, Vorschub (Breite in Pixeln) und Panel-Masse als Java-Enum ins Plugin, damit
    beides nie auseinanderlaeuft. Der Vorschub wird fuers Ausrichten von Text gebraucht."""
    if not os.path.isdir(PLUGIN_DIR):
        print("Hinweis: FMC-Plugin-Ordner nicht gefunden, UiIcon.java wurde nicht geschrieben "
              "(Pfad per FMC_PLUGIN_DIR setzen).")
        return
    os.makedirs(os.path.dirname(JAVA_ENUM), exist_ok=True)

    def lit(c):
        return "\"\\u%04X\"" % ord(c)

    def const(name, value, doc=None):
        out = []
        if doc:
            out.append("    /** %s */" % doc)
        out.append("    public static final int %s = %d;" % (name, value))
        return out

    lines = [
        "package com.example.myplugin.ui;",
        "",
        "/**",
        " * GENERIERT von FMC-Resourcepack/tools/generate_icons.py - nicht von Hand aendern.",
        " * Die Zeichen liegen in der Font {@code fmc:icons} des Resourcepacks.",
        " */",
        "public enum UiIcon {",
    ]
    names = list(ICONS)
    for i, name in enumerate(names):
        end = ";" if i == len(names) - 1 else ","
        lines.append("    %s(%s, %d, %s, %d)%s" % (name.upper(), lit(ICONS[name][0]), icon_adv[name],
                                              lit(chr(BIG_ICON_BASE + i)), big_adv[name], end))
    lines += ["", "    // ── Balken ──",
              "    /** Balken-Segment (4 Pixel breit, per Textfarbe einfaerbbar) und sein Vorschub. */",
              "    public static final String BAR_SEGMENT = %s;" % lit(BAR_SEGMENT)]
    lines += const("BAR_ADVANCE", info["bar_adv"])

    lines += ["", "    // ── Panel (Hintergrund) ──",
              "    /** Basis-Zeichen der Rahmenkacheln; Zeichen = Basis + Reihe * PANEL_COLS + Spalte. */",
              "    public static final char PANEL_TOP_BASE = (char) 0x%04X;" % PANEL_TOP_BASE,
              "    public static final char PANEL_MID_BASE = (char) 0x%04X;" % PANEL_MID_BASE,
              "    public static final char PANEL_BOT_BASE = (char) 0x%04X;" % PANEL_BOT_BASE,
              "    /** Untere Kacheln mit Randlinie in Kachelzeile v: Basis + ((v - MIN) * ROWS_MAX + Reihe) * COLS + Spalte. */",
              "    public static final char PANEL_BOT_VAR_BASE = (char) 0x%04X;" % PANEL_BOT_VAR_BASE]
    lines += const("PANEL_BOT_VAR_MIN", PANEL_BOT_VAR_MIN, "Kleinste Kachelzeile mit Randlinie; darunter gibt es keine Variante.")
    lines += const("PANEL_COLS", PANEL_COLS)
    lines += const("PANEL_TILE_ADVANCE", info["panel_adv"], "Breite einer Rahmenkachel (inklusive 1 Pixel Abstand).")
    lines += const("PANEL_WIDTH", PANEL_W, "Breite des Panels in GUI-Pixeln.")
    lines += const("PANEL_UNIT", PANEL_UNIT, "Hoehe einer Kachelreihe; die Panelhoehe ist ein Vielfaches davon.")
    lines += const("PANEL_ROWS_MAX", PANEL_ROWS_MAX, "Hoechstzahl der Reihen.")

    lines += ["", "    // ── Profilkarte ──",
              "    public static final char CARD_BASE = (char) 0x%04X;" % CARD_BASE]
    lines += const("CARD_COLS", CARD_COLS)
    lines += const("CARD_TILE_ADVANCE", info["card_adv"])
    lines += const("CARD_X", CARD_X, "Linke Kante der Karte im Panel.")
    lines += const("CARD_W", CARD_W)
    lines += const("CARD_H", CARD_H)
    lines += const("STAR_X", STAR_X, "Linke Kante des grossen Sterns in der Karte.")
    lines += ["    public static final String STAR_BIG = %s;" % lit(STAR_BIG_CHAR)]
    lines += const("STAR_BIG_ADVANCE", info["star_adv"])
    lines += ["    /** Grosse Token-Muenze (statt des Sterns in der Karte). */",
              "    public static final String TOKENS_BIG = %s;" % lit(TOKENS_BIG_CHAR)]
    lines += const("TOKENS_BIG_ADVANCE", info["tokens_big_adv"])
    lines += const("NAME_X", NAME_X, "Textbeginn in der Karte.")
    lines += const("TEXT_RIGHT", TEXT_RIGHT, "Rechter Textrand in der Karte.")

    lines += ["", "    // ── Schliessen-X ──",
              "    /** Grosses Schliessen-X (14 Pixel hoch): Zeichen, Vorschub und linke Kante im Panel. */",
              "    public static final String X_BIG = %s;" % lit(X_BIG_CHAR)]
    lines += const("X_BIG_ADVANCE", info["x_adv"])
    lines += const("X_BIG_X", X_BIG_X)

    lines += ["", "    // ── Button-Hintergrund (Textbutton im Panel) ──",
              "    /** Links, Mitte und rechts. 118 Pixel Breite = links + rechts, 238 = links + 2x Mitte + rechts. */",
              "    public static final String BTN_LEFT = %s;" % lit(BTN_LEFT_CHAR),
              "    public static final String BTN_MID = %s;" % lit(BTN_MID_CHAR),
              "    public static final String BTN_RIGHT = %s;" % lit(BTN_RIGHT_CHAR)]
    lines += const("BTN_END_W", BTN_END_W, "Breite von links und rechts in Pixeln.")
    lines += const("BTN_MID_W", BTN_MID_W, "Breite der Mitte in Pixeln.")
    lines += const("BTN_END_ADVANCE", info["btn_end_adv"], "Vorschub von links und rechts (inklusive 1 Pixel Abstand).")
    lines += const("BTN_MID_ADVANCE", info["btn_mid_adv"], "Vorschub der Mitte (inklusive 1 Pixel Abstand).")
    lines += const("BTN_H", BTN_H, "Hoehe des Buttons in Pixeln.")

    lines += ["", "    // ── Kisten-GUIs: Hintergrundbild im Inventartitel (siehe tools/chest_textures.py) ──",
              "    /** Hintergrund der Endertruhe (54 Slots, 176 x 222 Pixel). */",
              "    public static final String CHEST_EC = %s;" % lit(info["chest"]["ec"]),
              "    /** Hintergrund der Bank (27 Slots, 176 x 168 Pixel). */",
              "    public static final String CHEST_BANK = %s;" % lit(info["chest"]["bank"])]
    lines += const("CHEST_ADVANCE", info["chest_adv"], "Vorschub des Hintergrundbilds (Breite + 1 Pixel Abstand).")
    lines += const("CHEST_TITLE_X", chest_textures.CHEST_TITLE_X, "Der Inventartitel beginnt so viele Pixel vom linken Rand.")
    lines += const("CHEST_WIDTH", chest_textures.W, "Breite des Kisten-GUIs in Pixeln.")

    lines += amethyst_theme.java_lines(info["am"])

    lines += ["", "    // ── Abstandszeichen: Vorschub in Pixeln, positiv (nach rechts) und negativ (zurueck) ──"]
    for w in sorted(SPACE_POS):
        lines.append("    public static final String SPACE_PLUS_%d = %s;" % (w, lit(SPACE_POS[w])))
    for w in sorted(SPACE_NEG):
        lines.append("    public static final String SPACE_MINUS_%d = %s;" % (w, lit(SPACE_NEG[w])))
    lines += [
        "",
        "    private final String glyph;",
        "    private final int advance;",
        "    private final String bigGlyph;",
        "    private final int bigAdvance;",
        "",
        "    UiIcon(String glyph, int advance, String bigGlyph, int bigAdvance) {",
        "        this.glyph = glyph;",
        "        this.advance = advance;",
        "        this.bigGlyph = bigGlyph;",
        "        this.bigAdvance = bigAdvance;",
        "    }",
        "",
        "    /** Grosse Variante (14 Pixel hoch) fuer Dialog-Buttons. */",
        "    public String bigGlyph() {",
        "        return bigGlyph;",
        "    }",
        "",
        "    /** Breite der grossen Variante in Pixeln (inklusive 1 Pixel Abstand). */",
        "    public int bigAdvance() {",
        "        return bigAdvance;",
        "    }",
        "",
        "    public String glyph() {",
        "        return glyph;",
        "    }",
        "",
        "    /** Breite des Icons im Text in Pixeln (inklusive 1 Pixel Abstand). */",
        "    public int advance() {",
        "        return advance;",
        "    }",
        "}",
        "",
    ]
    with open(JAVA_ENUM, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def single_advance(tiles, height, what):
    """Alle Kacheln einer Art muessen denselben Vorschub haben (sonst gaebe es Luecken im Bild)."""
    values = {glyph_advance(t, height) for t in tiles}
    assert len(values) == 1, f"{what}: Kacheln haben verschiedene Breiten {values}"
    return values.pop()


def main():
    with multiprocessing.Pool() as pool:
        rendered = dict(pool.map(render_by_name, list(ICONS)))

    providers = []
    for name, (char, _) in ICONS.items():
        write_png(os.path.join(ICON_DIR, name + ".png"), rendered[name])
        providers.append({
            "type": "bitmap",
            "file": f"fmc:font/icons/{name}.png",
            "ascent": GLYPH_ASCENT,
            "height": GLYPH_HEIGHT,
            "chars": [char],
        })
    for i, name in enumerate(ICONS):
        providers.append({
            "type": "bitmap",
            "file": f"fmc:font/icons/{name}.png",
            "ascent": BIG_ICON_ASCENT,
            "height": BIG_ICON_HEIGHT,
            "chars": [chr(BIG_ICON_BASE + i)],
        })
    space_advances = {c: -w for w, c in SPACE_NEG.items()}
    space_advances.update({c: w for w, c in SPACE_POS.items()})
    providers.append({"type": "space", "advances": space_advances})
    providers.append({"type": "bitmap", "file": "fmc:font/ui/bar_seg.png",
                      "ascent": 7, "height": 8, "chars": [BAR_SEGMENT]})

    # Panel-Rahmen: Kachelbilder (nur 12) und fuer jede Reihe eigene Font-Eintraege mit verschobenem ascent
    ui_dir = os.path.join(PACK, "assets", "fmc", "textures", "font", "ui")
    for old in os.listdir(ui_dir):
        if old.startswith(("panel", "card")):
            os.remove(os.path.join(ui_dir, old))
    panel_tiles = {}
    for kind in ("top", "mid", "bot"):
        for c in range(PANEL_COLS):
            rows = make_panel_tile(kind, c).render()
            panel_tiles[(kind, c)] = rows
            write_png(os.path.join(ui_dir, f"panel_{kind}_{c}.png"), rows)
    for c in range(PANEL_COLS):
        providers.append({"type": "bitmap", "file": f"fmc:font/ui/panel_top_{c}.png", "ascent": PANEL_ASCENT,
                          "height": PANEL_UNIT, "chars": [panel_char(PANEL_TOP_BASE, 0, c)]})
    for r in range(1, PANEL_ROWS_MAX):
        for kind, base in (("mid", PANEL_MID_BASE), ("bot", PANEL_BOT_BASE)):
            for c in range(PANEL_COLS):
                providers.append({"type": "bitmap", "file": f"fmc:font/ui/panel_{kind}_{c}.png",
                                  "ascent": PANEL_ASCENT - r * PANEL_UNIT, "height": PANEL_UNIT,
                                  "chars": [panel_char(base, r, c)]})
    # Untere Kacheln mit hoeher liegender Randlinie (pixelgenaue Panelhoehe)
    var_tiles = []
    for v in range(PANEL_BOT_VAR_MIN, PANEL_UNIT - 1):
        for c in range(PANEL_COLS):
            rows = make_panel_bottom_variant(c, v).render()
            var_tiles.append(rows)
            write_png(os.path.join(ui_dir, f"panel_botv_{v}_{c}.png"), rows)
        for r in range(1, PANEL_ROWS_MAX):
            for c in range(PANEL_COLS):
                providers.append({"type": "bitmap", "file": f"fmc:font/ui/panel_botv_{v}_{c}.png",
                                  "ascent": PANEL_ASCENT - r * PANEL_UNIT, "height": PANEL_UNIT,
                                  "chars": [chr(PANEL_BOT_VAR_BASE
                                                + ((v - PANEL_BOT_VAR_MIN) * PANEL_ROWS_MAX + r) * PANEL_COLS + c)]})
    panel_adv = single_advance(list(panel_tiles.values()) + var_tiles, PANEL_UNIT, "Panel")

    # Profilkarte, grosser Stern, Schliessen-X
    card_tiles = []
    for c in range(CARD_COLS):
        rows = make_card_tile(c).render()
        card_tiles.append(rows)
        write_png(os.path.join(ui_dir, f"card_{c}.png"), rows)
        providers.append({"type": "bitmap", "file": f"fmc:font/ui/card_{c}.png", "ascent": CARD_ASCENT,
                          "height": CARD_H, "chars": [chr(CARD_BASE + c)]})
    card_adv = single_advance(card_tiles, CARD_H, "Karte")
    # Grosse Token-Muenze: eigene Textur in 3-facher Aufloesung (96 x 96 statt 32 x 32). Sie wird mit 24 Pixeln Hoehe
    # angezeigt; aus der 32er-Textur wurde sie ungleichmaessig herunterskaliert und wirkte verpixelt.
    tokens_big_rows = icon_tokens(scale=TOKENS_BIG_SCALE).render()
    write_png(os.path.join(ICON_DIR, "tokens_big.png"), tokens_big_rows)
    providers.append({"type": "bitmap", "file": "fmc:font/icons/star.png",
                      "ascent": STAR_BIG_ASCENT, "height": STAR_BIG_H, "chars": [STAR_BIG_CHAR]})
    providers.append({"type": "bitmap", "file": "fmc:font/icons/tokens_big.png",
                      "ascent": STAR_BIG_ASCENT, "height": STAR_BIG_H, "chars": [TOKENS_BIG_CHAR]})
    providers.append({"type": "bitmap", "file": "fmc:font/icons/badge_close.png",
                      "ascent": X_BIG_ASCENT, "height": X_BIG_H, "chars": [X_BIG_CHAR]})

    # Button-Hintergrund (links / Mitte / rechts)
    btn_rows = {}
    for kind, char in (("left", BTN_LEFT_CHAR), ("mid", BTN_MID_CHAR), ("right", BTN_RIGHT_CHAR)):
        btn_rows[kind] = make_button_tile(kind).render()
        write_png(os.path.join(ui_dir, f"btn_{kind}.png"), btn_rows[kind])
        providers.append({"type": "bitmap", "file": f"fmc:font/ui/btn_{kind}.png", "ascent": BTN_ASCENT,
                          "height": BTN_H, "chars": [char]})
    btn_end_adv = single_advance([btn_rows["left"], btn_rows["right"]], BTN_H, "Button-Enden")
    btn_mid_adv = single_advance([btn_rows["mid"]], BTN_H, "Button-Mitte")

    ui_textures.write_all(PACK, write_png)
    am_info = amethyst_theme.write_all(sys.modules[__name__], PACK, write_png, providers, rendered)
    chest_providers, chest_chars, chest_adv = chest_textures.write_all(PACK, write_png)
    providers.extend(chest_providers)
    icon_adv = {name: glyph_advance(rendered[name], GLYPH_HEIGHT) for name in ICONS}
    big_adv = {name: glyph_advance(rendered[name], BIG_ICON_HEIGHT) for name in ICONS}
    write_java_enum(icon_adv, big_adv, {
        "panel_adv": panel_adv,
        "card_adv": card_adv,
        "star_adv": glyph_advance(rendered["star"], STAR_BIG_H),
        "tokens_big_adv": glyph_advance(tokens_big_rows, STAR_BIG_H),
        "x_adv": glyph_advance(rendered["badge_close"], X_BIG_H),
        "btn_end_adv": btn_end_adv,
        "btn_mid_adv": btn_mid_adv,
        "bar_adv": 5,
        "chest": chest_chars,
        "chest_adv": chest_adv,
        "am": am_info,
    })
    os.makedirs(os.path.dirname(FONT_JSON), exist_ok=True)
    with open(FONT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"providers": providers}, f, indent=2)
        f.write("\n")
    write_png(os.path.join(PACK, "pack.png"), make_pack_png(rendered["juwelen"]))
    write_preview(os.path.join(ROOT, "dist", "preview.png"), rendered)
    print(f"{len(ICONS)} Icons ({N}x{N}), {len(providers)} Font-Eintraege, icons.json und pack.png geschrieben.")
    for name, (char, _) in ICONS.items():
        print(f"  U+{ord(char):04X}  {name}")


if __name__ == "__main__":
    main()