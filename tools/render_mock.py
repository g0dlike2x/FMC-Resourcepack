#!/usr/bin/env python3
"""
Zeichnet eine Vorschau des Demo-Menues (/fmcmenu), ohne dass Minecraft laeuft.

    python tools/render_mock.py <pfad-zur-minecraft-client.jar>

Schreibt dist/mock_fmcmenu.png. Es werden benutzt:
  - die Texturen aus pack/ (Buttons, Icons, Balken, Hintergrund, Trennlinien),
  - die Vanilla-Schrift und das Warn-Symbol aus der angegebenen client.jar
    (nur lokal zum Zeichnen gelesen, nichts davon wird ins Repo kopiert).

Das ist eine Naeherung: Position und Abstaende folgen dem Vanilla-Aufbau, wie Minecraft die
Dialoge tatsaechlich setzt, kann aber leicht abweichen. Es ersetzt keinen Test im Spiel.
"""
import json
import os
import struct
import sys
import zipfile
import zlib

import generate_icons as gi

ROOT = gi.ROOT
S = 3  # Vergroesserung: 1 GUI-Pixel = S Bildpixel


# ── PNG lesen ───────────────────────────────────────────────────────────────

def png_read(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, plte, trns = 8, b"", None, None
    while pos < len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE":
            plte = body
        elif tag == b"tRNS":
            trns = body
        elif tag == b"IDAT":
            idat += body
    assert interlace == 0 and (depth == 8 or ctype in (0, 3)), "nicht unterstuetztes PNG-Format"
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    bpp = max(1, ch * depth // 8)
    stride = (w * ch * depth + 7) // 8
    prev = bytearray(stride)
    rows, p = [], 0
    for _ in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        prev = line
        row = []
        for x in range(w):
            if depth < 8:
                bit = x * depth
                v = (line[bit // 8] >> (8 - depth - bit % 8)) & ((1 << depth) - 1)
                if ctype == 0:
                    g = v * 255 // ((1 << depth) - 1)
                    row.append((g, g, g, 255))
                else:
                    a = trns[v] if trns and v < len(trns) else 255
                    row.append((plte[v * 3], plte[v * 3 + 1], plte[v * 3 + 2], a))
            elif ctype == 6:
                row.append(tuple(line[x * 4:x * 4 + 4]))
            elif ctype == 2:
                row.append((line[x * 3], line[x * 3 + 1], line[x * 3 + 2], 255))
            elif ctype == 0:
                row.append((line[x], line[x], line[x], 255))
            elif ctype == 4:
                row.append((line[x * 2], line[x * 2], line[x * 2], line[x * 2 + 1]))
            else:
                i = line[x]
                a = trns[i] if trns and i < len(trns) else 255
                row.append((plte[i * 3], plte[i * 3 + 1], plte[i * 3 + 2], a))
        rows.append(row)
    return rows


# ── Zeichenflaeche (in Bildpixeln, Koordinaten der API in GUI-Pixeln) ───────

class Canvas:
    def __init__(self, gw, gh):
        self.w, self.h = gw * S, gh * S
        self.px = [[(0, 0, 0, 255)] * self.w for _ in range(self.h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            a = c[3] / 255.0
            if a >= 1.0:
                self.px[y][x] = (c[0], c[1], c[2], 255)
            elif a > 0:
                d = self.px[y][x]
                self.px[y][x] = (round(c[0] * a + d[0] * (1 - a)), round(c[1] * a + d[1] * (1 - a)),
                                 round(c[2] * a + d[2] * (1 - a)), 255)

    def rect(self, gx, gy, gw, gh, color):
        for y in range(round(gy * S), round((gy + gh) * S)):
            for x in range(round(gx * S), round((gx + gw) * S)):
                self.put(x, y, color)

    def gpix(self, gx, gy, color):
        self.rect(gx, gy, 1, 1, color)

    def blit_rows(self, rows, x0, y0):
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c[3]:
                    self.put(x0 + x, y0 + y, c)


def resize_box(rows, tw, th):
    """Flaechengemittelte Verkleinerung (mit Alpha-Gewichtung)."""
    sh, sw = len(rows), len(rows[0])
    out = []
    for ty in range(th):
        y0, y1 = ty * sh / th, (ty + 1) * sh / th
        orow = []
        for tx in range(tw):
            x0, x1 = tx * sw / tw, (tx + 1) * sw / tw
            sa = sr = sg = sb = tot = 0.0
            for sy in range(int(y0), min(sh, int(y1) + 1)):
                wy = min(y1, sy + 1) - max(y0, sy)
                if wy <= 0:
                    continue
                for sx in range(int(x0), min(sw, int(x1) + 1)):
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


# ── Schrift ─────────────────────────────────────────────────────────────────

class Font:
    def __init__(self, jar_path):
        z = zipfile.ZipFile(jar_path)
        self.glyphs = {}
        meta = json.loads(z.read("assets/minecraft/font/include/default.json"))
        for prov in meta["providers"]:
            if prov["type"] != "bitmap":
                continue
            name = prov["file"].split(":", 1)[1]
            img = png_read(z.read("assets/minecraft/textures/" + name))
            chars = prov["chars"]
            cols, rws = len(chars[0]), len(chars)
            cw, ch = len(img[0]) // cols, len(img) // rws
            height = prov.get("height", 8)
            for r, line in enumerate(chars):
                for c, ch_ in enumerate(line):
                    if ch_ == "\u0000" or ch_ in self.glyphs:
                        continue
                    px, maxcol = [], -1
                    for yy in range(ch):
                        for xx in range(cw):
                            p = img[r * ch + yy][c * cw + xx]
                            if p[3] > 0:
                                px.append((xx, yy, p))
                                maxcol = max(maxcol, xx)
                    self.glyphs[ch_] = {"px": px, "adv": int(0.5 + (maxcol + 1) * height / ch) + 1,
                                        "ascent": prov["ascent"]}
        self.glyphs[" "] = {"px": [], "adv": 4, "ascent": 7}


def custom_glyph(rows, ascent, height):
    """Bitmap-Glyph aus dem Pack (beliebige Groesse), liefert Breite/Vorschub wie Minecraft."""
    h, w = len(rows), len(rows[0])
    scale = height / h
    maxcol = max((x for row in rows for x, c in enumerate(row) if c[3] > 0), default=-1)
    return {"rows": rows, "w": w * scale, "h": height, "adv": int(0.5 + (maxcol + 1) * scale) + 1, "ascent": ascent}


# ── Text/Icon-Folgen ────────────────────────────────────────────────────────

WHITE, YELLOW, LILAC, GRAY = (255, 255, 255), (255, 255, 85), (255, 85, 255), (170, 170, 170)


class Ui:
    def __init__(self, font, pack_dir):
        self.font = font
        self.pack = pack_dir
        self.icon_cache, self.bar_glyph = {}, None
        seg = png_read(open(os.path.join(pack_dir, "assets", "fmc", "textures", "font", "ui", "bar_seg.png"), "rb").read())
        self.bar_glyph = custom_glyph(seg, 7, 8)

    def icon(self, name):
        if name not in self.icon_cache:
            rows = png_read(open(os.path.join(self.pack, "assets", "fmc", "textures", "font", "icons", name + ".png"), "rb").read())
            g = custom_glyph(rows, gi.GLYPH_ASCENT, gi.GLYPH_HEIGHT)
            g["scaled"] = resize_box(rows, round(g["w"] * S), round(g["h"] * S))
            self.icon_cache[name] = g
        return self.icon_cache[name]

    def width(self, runs):
        total = 0
        for r in runs:
            if r[0] == "t":
                for ch in r[1]:
                    total += self.font.glyphs[ch]["adv"] + (1 if r[3] else 0)
            elif r[0] == "i":
                total += self.icon(r[1])["adv"]
            elif r[0] == "s":
                total += r[1]
            elif r[0] == "b":
                total += r[2] * (self.bar_glyph["adv"] - 1)
        return total

    def draw(self, cv, runs, gx, gy, shadow=True):
        x = gx
        for r in runs:
            if r[0] == "t":
                for ch in r[1]:
                    g = self.font.glyphs[ch]
                    for dx in ((0, 1) if r[3] else (0,)):
                        if shadow:
                            self._glyph_px(cv, g, x + dx + 1, gy + 1, tuple(c // 4 for c in r[2]))
                        self._glyph_px(cv, g, x + dx, gy, r[2])
                    x += g["adv"] + (1 if r[3] else 0)
            elif r[0] == "i":
                g = self.icon(r[1])
                cv.blit_rows(g["scaled"], round(x * S), round((gy + 7 - g["ascent"]) * S))
                x += g["adv"]
            elif r[0] == "s":
                x += r[1]
            elif r[0] == "b":
                percent, segs, c0, c1 = r[1], r[2], r[3], r[4]
                filled = round(percent / 100.0 * segs)
                for i in range(segs):
                    t = i / (segs - 1) if segs > 1 else 0
                    col = tuple(round(c0[k] + (c1[k] - c0[k]) * t) for k in range(3)) if i < filled else (58, 53, 80)
                    for yy, row in enumerate(self.bar_glyph["rows"]):
                        for xx, p in enumerate(row):
                            if p[3]:
                                tint = (p[0] * col[0] // 255, p[1] * col[1] // 255, p[2] * col[2] // 255, p[3])
                                cv.rect(x + xx, gy + 7 - self.bar_glyph["ascent"] + yy, 1, 1, tint)
                    x += self.bar_glyph["adv"] - 1
        return x

    def _glyph_px(self, cv, g, gx, gy, color):
        for (xx, yy, p) in g["px"]:
            cv.rect(gx + xx, gy + 7 - g["ascent"] + yy, 1, 1, (color[0], color[1], color[2], 255))

    def center(self, cv, runs, cx, gy, shadow=True):
        self.draw(cv, runs, cx - self.width(runs) / 2.0, gy, shadow)


# ── Bausteine ───────────────────────────────────────────────────────────────

def nine_slice(rows, gw, gh, border=3):
    """Skaliert ein 9-Slice-Sprite auf gw x gh GUI-Pixel (jeweils mal S)."""
    sh, sw = len(rows), len(rows[0])
    tw, th = gw * S, gh * S
    b = border * S

    def src(t, size, length):
        if t < b:
            return t // S
        if t >= size - b:
            return length - 1 - (size - 1 - t) // S
        return border + (t - b) * (length - 2 * border) // (size - 2 * b)

    xs = [src(x, tw, sw) for x in range(tw)]
    return [[rows[src(y, th, sh)][sx] for sx in xs] for y in range(th)]


def scene(cv):
    """Platzhalter fuer die unscharfe Spielwelt hinter dem Menue."""
    for y in range(cv.h):
        t = y / cv.h
        for x in range(cv.w):
            n = ((x // 24 + y // 24) % 3) * 6
            if t < 0.55:
                c = (58 + int(70 * t) + n, 96 + int(80 * t) + n, 150 + int(60 * t))
            else:
                c = (66 + n, 110 + n * 2, 58 + n)
            cv.px[y][x] = (c[0], c[1], c[2], 255)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    jar = sys.argv[1]
    pack = gi.PACK
    font = Font(jar)
    ui = Ui(font, pack)
    z = zipfile.ZipFile(jar)

    gw, gh = 340, 214
    cv = Canvas(gw, gh)
    scene(cv)
    # Hintergrund-Kachel des Packs (inworld_menu_background) ueber den ganzen Bildschirm
    gui = os.path.join(pack, "assets", "minecraft", "textures", "gui")
    bg = png_read(open(os.path.join(gui, "inworld_menu_background.png"), "rb").read())
    for y in range(cv.h):
        for x in range(cv.w):
            cv.put(x, y, bg[(y // (2 * S)) % 16][(x // (2 * S)) % 16])

    btn = {k: png_read(open(os.path.join(gui, "sprites", "widget", k + ".png"), "rb").read())
           for k in ("button", "button_highlighted")}
    sep = png_read(open(os.path.join(gui, "inworld_header_separator.png"), "rb").read())

    cx = gw / 2.0
    # Kopfzeile
    title = [("i", "crown"), ("s", 4), ("t", "FMC", (162, 53, 255), True), ("t", " Men\u00fc", WHITE, False)]
    tw = ui.width(title)
    ui.center(cv, title, cx - 11, 12)
    warn = png_read(z.read("assets/minecraft/textures/gui/sprites/dialog/warning_button.png"))
    cv.blit_rows([[p for p in row for _ in range(S)] for row in warn for _ in range(S)],
                 round((cx - 11 + tw / 2.0 + 4) * S), round(7 * S) - 0)
    for i, gy in enumerate((33, 34)):
        for gx in range(gw):
            c = sep[i][gx % 32]
            for yy in range(S):
                for xx in range(S):
                    cv.put(gx * S + xx, gy * S + yy, c)

    # Profilkarte
    ui.center(cv, [("i", "badge_star"), ("s", 4), ("t", "Julian", WHITE, True)], cx, 42)
    ui.center(cv, [("i", "tokens"), ("s", 2), ("t", "12.500", YELLOW, False), ("s", 10),
                   ("i", "juwelen"), ("s", 2), ("t", "340", LILAC, False)], cx, 55)
    ui.center(cv, [("b", 64, 20, (255, 90, 106), (255, 179, 71)), ("s", 4), ("t", "64%", WHITE, True)], cx, 68)

    # Buttons
    entries = [("bank", "Bank"), ("tokens", "Pay"), ("settings", "Einstellungen"),
               ("chart", "Statistik"), ("trophy", "Rangliste"), ("info", "Hilfe")]
    left = cx - 120
    for i, (icon, label) in enumerate(entries):
        col, row = i % 2, i // 2
        bx, by = left + col * 122, 84 + row * 24
        hover = (i == 0)
        cv.blit_rows(nine_slice(btn["button_highlighted" if hover else "button"], 118, 20),
                     round(bx * S), round(by * S))
        ui.center(cv, [("i", icon), ("s", 4), ("t", label, WHITE, False)], bx + 59, by + 6)

    # Fusszeile
    for i, gy in enumerate((166, 167)):
        for gx in range(gw):
            c = sep[i][gx % 32]
            for yy in range(S):
                for xx in range(S):
                    cv.put(gx * S + xx, gy * S + yy, c)
    cv.blit_rows(nine_slice(btn["button"], 240, 20), round(left * S), round(174 * S))
    ui.center(cv, [("i", "badge_close"), ("s", 4), ("t", "Schlie\u00dfen", WHITE, False)], cx, 180)

    out = os.path.join(ROOT, "dist", "mock_fmcmenu.png")
    gi.write_png(out, cv.px)
    print(out, cv.w, "x", cv.h)


if __name__ == "__main__":
    main()
