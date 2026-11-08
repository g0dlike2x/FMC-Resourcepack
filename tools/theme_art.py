#!/usr/bin/env python3
"""
Gezeichnete Ersatzbilder fuer die Panel-Themes (Warp, Farmwelt), solange in art/ kein KI-Bild liegt.

Die Bilder bestehen aus Minecraft-artigen Bloecken (isometrisch, 16 x 16 Texel je Seite, Texturen aus
Zufallsmustern mit festem Startwert), Kugeln (Enderperle, Enderauge), einem Baum, Blumen und Partikeln. Jedes Teil
bekommt einen dunklen Umriss, hinter der Gruppe liegt ein weicher Schein in der Themenfarbe.

Alle Funktionen liefern Zeilen aus (r, g, b, a) mit 0..255, in der Groesse, die amethyst_theme.py erwartet
(Seitenkristalle 44 x 64, Eckkristalle 80 x 112, Ornament 240 x 80 Texturpixel). Nur Standardbibliothek.
"""
import math
import random


# ── Zeichenflaeche ──────────────────────────────────────────────────────────

def blank(w, h):
    return [[(0, 0, 0, 0)] * w for _ in range(h)]


def hexrgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def put(cv, x, y, c, a=255):
    """Setzt einen Pixel mit Alpha-Mischung (c = (r, g, b), a = 0..255)."""
    if a <= 0 or not (0 <= y < len(cv) and 0 <= x < len(cv[0])):
        return
    r, g, b, da = cv[y][x]
    sa, ba = a / 255.0, da / 255.0
    oa = sa + ba * (1 - sa)
    cv[y][x] = (round((c[0] * sa + r * ba * (1 - sa)) / oa), round((c[1] * sa + g * ba * (1 - sa)) / oa),
                round((c[2] * sa + b * ba * (1 - sa)) / oa), round(255 * oa))


def over(dst, src, ox=0, oy=0):
    for y, row in enumerate(src):
        for x, (r, g, b, a) in enumerate(row):
            if a:
                put(dst, x + ox, y + oy, (r, g, b), a)


def shade(c, f):
    """f < 1 dunkler, f > 1 heller."""
    if f <= 1:
        return tuple(round(v * f) for v in c)
    t = f - 1
    return tuple(round(v + (255 - v) * t) for v in c)


def mix(c0, c1, t):
    return tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def outline(layer, color, width=1):
    """Dunkler Umriss um alles Sichtbare der Ebene (aussen, width Pixel)."""
    h, w = len(layer), len(layer[0])
    solid = [[layer[y][x][3] > 90 for x in range(w)] for y in range(h)]
    for _ in range(width):
        grow = [row[:] for row in solid]
        for y in range(h):
            for x in range(w):
                if solid[y][x]:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and solid[ny][nx]:
                        grow[y][x] = True
                        break
        for y in range(h):
            for x in range(w):
                if grow[y][x] and not solid[y][x]:
                    r, g, b, a = layer[y][x]
                    if a < 255:
                        base = blank(1, 1)
                        put(base, 0, 0, color, 255)
                        put(base, 0, 0, (r, g, b), a)
                        layer[y][x] = base[0][0]
        solid = grow


def blur_alpha(alpha, radius):
    h, w = len(alpha), len(alpha[0])
    cur = alpha
    for _ in range(2):
        tmp = [[0.0] * w for _ in range(h)]
        win = 2 * radius + 1
        for y in range(h):
            row, acc = cur[y], 0.0
            for x in range(-radius, radius + 1):
                if 0 <= x < w:
                    acc += row[x]
            for x in range(w):
                tmp[y][x] = acc / win
                if x + radius + 1 < w:
                    acc += row[x + radius + 1]
                if x - radius >= 0:
                    acc -= row[x - radius]
        out = [[0.0] * w for _ in range(h)]
        for x in range(w):
            acc = 0.0
            for y in range(-radius, radius + 1):
                if 0 <= y < h:
                    acc += tmp[y][x]
            for y in range(h):
                out[y][x] = acc / win
                if y + radius + 1 < h:
                    acc += tmp[y + radius + 1][x]
                if y - radius >= 0:
                    acc -= tmp[y - radius][x]
        cur = out
    return cur


def with_glow(cv, color, radius, strength):
    """Legt einen weichen Schein (aus dem Alpha des Bildes) hinter das Bild."""
    h, w = len(cv), len(cv[0])
    blurred = blur_alpha([[cv[y][x][3] / 255.0 for x in range(w)] for y in range(h)], radius)
    out = [[(color[0], color[1], color[2], min(255, round(255 * min(1.0, blurred[y][x] * strength))))
            for x in range(w)] for y in range(h)]
    over(out, cv)
    return out


def flip(rows):
    return [row[::-1] for row in rows]


# ── Texturen (16 x 16, Werte (r, g, b) oder None = durchsichtig) ────────────

def _pick(rnd, pal):
    return hexrgb(rnd.choice(pal))


def tex_noise(seed, pal):
    rnd = random.Random(seed)
    return [[_pick(rnd, pal) for _ in range(16)] for _ in range(16)]


DIRT = ["#8A5A35", "#79502F", "#966540", "#6A4428", "#84553A"]
GRASS = ["#5FA83A", "#6DBA45", "#559C33", "#7CC850", "#66B23E"]


def tex_grass_top():
    return tex_noise(11, GRASS)


def tex_grass_side():
    rnd = random.Random(12)
    t = tex_noise(13, DIRT)
    for x in range(16):
        depth = 3 + (1 if rnd.random() < 0.55 else 0) + (1 if rnd.random() < 0.2 else 0)
        for y in range(depth):
            t[y][x] = _pick(rnd, GRASS)
    return t


def tex_end_stone():
    rnd = random.Random(21)
    t = tex_noise(22, ["#DCDF9E", "#E3E6A8", "#D1D490", "#D8DB97"])
    for _ in range(14):
        x, y = rnd.randrange(16), rnd.randrange(16)
        t[y][x] = hexrgb("#B7BA79")
    return t


def tex_obsidian():
    return tex_noise(31, ["#14101E", "#1C1530", "#251B3C", "#100C18", "#2E2149"])


def tex_portal_top():
    """Endportalrahmen von oben: Rand aus Endstein-Gruen, Mitte mit dem Loch fuer das Enderauge."""
    rnd = random.Random(41)
    t = []
    for y in range(16):
        row = []
        for x in range(16):
            edge = min(x, y, 15 - x, 15 - y)
            if edge < 2:
                row.append(_pick(rnd, ["#5E8C71", "#6E9C80", "#557F66"]))
            elif edge < 4:
                row.append(_pick(rnd, ["#2F5A4B", "#376654", "#2A5044"]))
            else:
                row.append(_pick(rnd, ["#1D3A33", "#224339", "#183129"]))
        t.append(row)
    return t


def tex_portal_side():
    rnd = random.Random(42)
    t = tex_end_stone()
    for y in range(4):
        for x in range(16):
            t[y][x] = _pick(rnd, ["#3E6E5C", "#467862", "#355E4F"])
    for x in range(16):
        if rnd.random() < 0.5:
            t[4][x] = _pick(rnd, ["#3E6E5C", "#467862"])
    return t


def tex_water():
    rnd = random.Random(51)
    t = tex_noise(52, ["#3F76E4", "#3A6DD8", "#4580EC", "#3566CF"])
    for y in (3, 9, 13):
        x0 = rnd.randrange(10)
        for x in range(x0, x0 + 5):
            t[y][x % 16] = hexrgb("#76A6FF")
    return t


def tex_log_side():
    rnd = random.Random(61)
    pal = ["#6B5132", "#5A4329", "#7A5C3A", "#4E3A23"]
    cols = [rnd.choice(pal) for _ in range(16)]
    return [[hexrgb(cols[x]) if rnd.random() > 0.15 else _pick(rnd, pal) for x in range(16)] for _ in range(16)]


def tex_leaves():
    rnd = random.Random(71)
    t = tex_noise(72, ["#3E8A2A", "#4C9E33", "#367A25", "#5AAE3C"])
    for _ in range(26):
        t[rnd.randrange(16)][rnd.randrange(16)] = hexrgb("#24561A")
    return t


# ── Formen ──────────────────────────────────────────────────────────────────

def iso_block(cv, cx, top, a, tex_top, tex_left, tex_right, side_k=1.12, light=(1.0, 0.84, 0.66)):
    """Isometrischer Block: obere Spitze bei (cx, top), halbe Breite a. Texturen werden pixelgenau (naechster
    Texel) abgebildet, die Seiten sind abgedunkelt."""
    H = a * side_k
    x0, x1 = int(math.floor(cx - a)), int(math.ceil(cx + a))
    y0, y1 = int(math.floor(top)), int(math.ceil(top + a + H))
    for py in range(y0, y1):
        for px in range(x0, x1):
            x, y = px + 0.5 - cx, py + 0.5 - top
            # Oberseite (Raute)
            s = (x / a + 2 * y / a) / 2
            t = (2 * y / a - x / a) / 2
            if 0 <= s < 1 and 0 <= t < 1:
                c = tex_top[min(15, int(t * 16))][min(15, int(s * 16))]
                put(cv, px, py, shade(c, light[0]))
                continue
            if x < 0:
                u = (x + a) / a
                v = (y - a / 2 - u * a / 2) / H
                if 0 <= u < 1 and 0 <= v < 1:
                    c = tex_left[min(15, int(v * 16))][min(15, int(u * 16))]
                    put(cv, px, py, shade(c, light[1]))
            else:
                u = x / a
                v = (y - a + u * a / 2) / H
                if 0 <= u < 1 and 0 <= v < 1:
                    c = tex_right[min(15, int(v * 16))][min(15, int(u * 16))]
                    put(cv, px, py, shade(c, light[2]))
    return y1


def block_height(a, side_k=1.12):
    return a + a * side_k


def sphere(cv, cx, cy, r, dark, mid, light, ss=3):
    """Glaenzende Kugel mit Licht oben links (Kantenglaettung durch Ueberabtastung)."""
    for py in range(int(cy - r - 1), int(cy + r + 2)):
        for px in range(int(cx - r - 1), int(cx + r + 2)):
            hits, acc = 0, [0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    x = px + (sx + 0.5) / ss - cx
                    y = py + (sy + 0.5) / ss - cy
                    d = math.hypot(x, y) / r
                    if d > 1:
                        continue
                    hits += 1
                    lt = math.hypot(x + r * 0.35, y + r * 0.4) / (r * 1.4)
                    c = mix(light, mid, min(1.0, lt * 1.3)) if lt < 0.75 else mix(mid, dark, min(1.0, (lt - 0.75) * 2.2))
                    for i in range(3):
                        acc[i] += c[i]
            if hits:
                put(cv, px, py, tuple(round(v / hits) for v in acc), round(255 * hits / (ss * ss)))


def disc(cv, cx, cy, rx, ry, color, alpha=255, ss=3):
    for py in range(int(cy - ry - 1), int(cy + ry + 2)):
        for px in range(int(cx - rx - 1), int(cx + rx + 2)):
            hits = 0
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss - cx) / rx
                    y = (py + (sy + 0.5) / ss - cy) / ry
                    if x * x + y * y <= 1:
                        hits += 1
            if hits:
                put(cv, px, py, color, round(alpha * hits / (ss * ss)))


def rect(cv, x0, y0, x1, y1, color, alpha=255):
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            put(cv, x, y, color, alpha)


def sparkle(cv, cx, cy, r, color, alpha=230):
    """Vierzackiger Funke."""
    for i in range(-r, r + 1):
        a = round(alpha * (1 - abs(i) / (r + 1)))
        put(cv, cx + i, cy, color, a)
        put(cv, cx, cy + i, color, a)


def particles(cv, spots, colors, size):
    for i, (x, y) in enumerate(spots):
        c = hexrgb(colors[i % len(colors)])
        s = size if i % 3 else size + 1
        rect(cv, x, y, x + s, y + s, c, 235)


# ── Teile ───────────────────────────────────────────────────────────────────

def ender_pearl(cv, cx, cy, r):
    sphere(cv, cx, cy, r, hexrgb("#0B3B35"), hexrgb("#1F7A6A"), hexrgb("#7FE8CF"))
    # dunkler Kern wie bei der Enderperle im Spiel
    disc(cv, cx + r * 0.12, cy + r * 0.15, r * 0.42, r * 0.42, hexrgb("#0E4A40"), 200)
    disc(cv, cx - r * 0.38, cy - r * 0.42, r * 0.22, r * 0.17, (235, 255, 250), 230)


def ender_eye(cv, cx, cy, r):
    sphere(cv, cx, cy, r, hexrgb("#1D4D2C"), hexrgb("#4FA35F"), hexrgb("#C6F5B8"))
    disc(cv, cx, cy, r * 0.62, r * 0.62, hexrgb("#3D8F57"), 150)
    disc(cv, cx, cy, r * 0.16, r * 0.55, hexrgb("#0C1F12"), 255)
    disc(cv, cx - r * 0.4, cy - r * 0.45, r * 0.2, r * 0.15, (245, 255, 240), 230)


def tree(cv, cx, base, trunk_h, crown_r):
    """Baum von vorn: Stamm mit Rinde, Krone aus Blaettertextur (gepixelt, Texel 3 Pixel)."""
    bark, leaves = tex_log_side(), tex_leaves()
    tw = max(4, round(crown_r * 0.38))
    for y in range(int(base - trunk_h), int(base)):
        for x in range(int(cx - tw / 2), int(cx + tw / 2)):
            c = bark[(y // 3) % 16][(x // 3) % 16]
            put(cv, x, y, shade(c, 0.95 if x < cx else 0.75))
    ccy = base - trunk_h - crown_r * 0.55
    rnd = random.Random(81)
    blobs = [(0, 0, 1.0), (-0.62, 0.28, 0.66), (0.62, 0.28, 0.66), (0, -0.45, 0.7)]
    for bx, by, br in blobs:
        R = crown_r * br
        ox, oy = cx + bx * crown_r, ccy + by * crown_r
        for y in range(int(oy - R), int(oy + R) + 1):
            for x in range(int(ox - R), int(ox + R) + 1):
                if math.hypot(x + 0.5 - ox, y + 0.5 - oy) <= R:
                    c = leaves[(y // 3) % 16][(x // 3) % 16]
                    lt = 1.08 - 0.35 * ((y - (ccy - crown_r)) / (2 * crown_r)) - (0.08 if x > cx else 0)
                    put(cv, x, y, shade(c, max(0.6, lt)))
    for _ in range(6):
        ax = cx + rnd.uniform(-0.7, 0.7) * crown_r
        ay = ccy + rnd.uniform(-0.3, 0.6) * crown_r
        disc(cv, ax, ay, 1.6, 1.6, hexrgb("#E8443A"))       # Aepfel


def flower(cv, x, base, color, h=9, s=2):
    """Blume als Pixelbild: Stiel h Pixel hoch, s Pixel je Bildpunkt (x = linke Kante des Stiels)."""
    stem, leaf = hexrgb("#3E8A2A"), hexrgb("#5AAE3C")
    rect(cv, x, base - h, x + s, base, stem)
    rect(cv, x + s, base - h // 2, x + 2 * s, base - h // 2 + s, leaf)
    rect(cv, x - s, base - h // 3, x, base - h // 3 + s, leaf)
    c, dark = hexrgb(color), shade(hexrgb(color), 0.7)
    top = base - h
    rect(cv, x - s, top - 2 * s, x + 2 * s, top, dark)
    rect(cv, x - 2 * s, top - 3 * s, x + 3 * s, top - s, c)
    rect(cv, x - s, top - 4 * s, x + 2 * s, top - 3 * s, c)
    rect(cv, x, top - 3 * s, x + s, top - 2 * s, hexrgb("#FFE36B"))


def tuft(cv, x, base, h=7):
    rnd = random.Random(int(x * 13 + base))
    for i in range(5):
        hh = h - abs(i - 2) * 2 + rnd.randint(-1, 1)
        c = hexrgb(rnd.choice(GRASS))
        for k in range(max(2, hh)):
            put(cv, x + i * 2 + (k // 4) * (1 if i > 2 else -1 if i < 2 else 0), base - k, c)
            put(cv, x + i * 2 + 1, base - k, shade(c, 0.85))


# ── Themen: Warp (Ender) ────────────────────────────────────────────────────

ENDER_OUT = hexrgb("#06201C")
ENDER_GLOW = hexrgb("#2FE0C0")
PURPLE_DOTS = ["#C77DFF", "#9D4EDD", "#E0AAFF"]


def _end_stone_block(cv, cx, top, a):
    t = tex_end_stone()
    iso_block(cv, cx, top, a, t, t, t)


def ender_corner(w, h):
    """Eckteil (unten): Endsteinblock mit schwebender Enderperle und Partikeln."""
    cv = blank(w, h)
    layer = blank(w, h)
    a = w * 0.38
    top = h - 2 - block_height(a)
    _end_stone_block(layer, w * 0.46, top, a)
    outline(layer, ENDER_OUT, 2)
    pearl = blank(w, h)
    r = w * 0.20
    ender_pearl(pearl, w * 0.56, top - r * 1.25, r)
    outline(pearl, ENDER_OUT, 2)
    over(layer, pearl)
    particles(layer, [(int(w * 0.18), int(top - r * 0.6)), (int(w * 0.82), int(top - r * 2.2)),
                      (int(w * 0.30), int(top - r * 2.6)), (int(w * 0.86), int(top + a * 0.4))], PURPLE_DOTS, 3)
    over(cv, with_glow(layer, ENDER_GLOW, 6, 0.9))
    return cv


def ender_corner_small(w, h):
    """Eckteil (oben, klein): schwebende Enderperle mit Funken."""
    cv = blank(w, h)
    layer = blank(w, h)
    r = w * 0.36
    ender_pearl(layer, w * 0.5, h - r - 6, r)
    outline(layer, ENDER_OUT, 2)
    particles(layer, [(int(w * 0.12), int(h - 2 * r - 10)), (int(w * 0.78), int(h - 2 * r - 18))], PURPLE_DOTS, 3)
    sparkle(layer, int(w * 0.8), int(h - r * 0.6), 4, (220, 255, 245))
    over(cv, with_glow(layer, ENDER_GLOW, 5, 0.9))
    return cv


def ender_banner(w, h):
    """Ornament: Endportalrahmen mit Enderauge in der Mitte, daneben Endstein und Obsidian mit Enderperlen."""
    cv = blank(w, h)
    layer = blank(w, h)
    cx = w / 2
    es, ob = tex_end_stone(), tex_obsidian()
    # Seiten (aussen Obsidian, innen Endstein), von aussen nach innen gezeichnet
    for side in (-1, 1):
        a = 15
        iso_block(layer, cx + side * 78, h - 1 - block_height(a), a, ob, ob, ob)
        a = 17
        iso_block(layer, cx + side * 50, h - 1 - block_height(a), a, es, es, es)
        a = 11
        iso_block(layer, cx + side * 60, h - 1 - block_height(17) - block_height(a) + a * 0.55, a, es, es, es)
    outline(layer, ENDER_OUT, 2)
    mid = blank(w, h)
    a = 22
    top = h - 1 - block_height(a)
    iso_block(mid, cx, top, a, tex_portal_top(), tex_portal_side(), tex_portal_side())
    outline(mid, ENDER_OUT, 2)
    over(layer, mid)
    orbs = blank(w, h)
    ender_eye(orbs, cx, top - 4, 13)
    ender_pearl(orbs, cx - 62, h - block_height(17) - 27, 7)
    ender_pearl(orbs, cx + 62, h - block_height(17) - 27, 7)
    outline(orbs, ENDER_OUT, 2)
    over(layer, orbs)
    particles(layer, [(int(cx - 30), 10), (int(cx + 27), 6), (int(cx - 95), 30), (int(cx + 92), 26),
                      (int(cx - 22), 30), (int(cx + 33), 34), (int(cx - 45), 4), (int(cx + 50), 14)], PURPLE_DOTS, 3)
    sparkle(layer, int(cx + 15), 6, 5, (220, 255, 245))
    sparkle(layer, int(cx - 70), 18, 4, (220, 255, 245))
    over(cv, with_glow(layer, ENDER_GLOW, 8, 0.8))
    return cv


# ── Themen: Farmwelt (Natur) ────────────────────────────────────────────────

NATURE_OUT = hexrgb("#13240C")
NATURE_GLOW = hexrgb("#8BE05A")


def _grass_block(cv, cx, top, a):
    iso_block(cv, cx, top, a, tex_grass_top(), tex_grass_side(), tex_grass_side())


def nature_corner(w, h):
    """Eckteil (unten): Grasblock mit Blume und Grasbueschel."""
    cv = blank(w, h)
    layer = blank(w, h)
    a = w * 0.38
    top = h - 2 - block_height(a)
    _grass_block(layer, w * 0.47, top, a)
    deco = blank(w, h)
    flower(deco, int(w * 0.36), int(top + a * 0.62), "#E8443A", 16, 3)
    tuft(deco, int(w * 0.50), int(top + a * 0.80), 9)
    over(layer, deco)
    outline(layer, NATURE_OUT, 2)
    over(cv, with_glow(layer, NATURE_GLOW, 6, 0.55))
    return cv


def nature_corner_small(w, h):
    """Eckteil (oben, klein): kleiner Baum auf einem Grasbueschel."""
    cv = blank(w, h)
    layer = blank(w, h)
    tree(layer, w * 0.5, h - 3, h * 0.30, w * 0.36)
    tuft(layer, int(w * 0.5) - 5, h - 2, 6)
    outline(layer, NATURE_OUT, 2)
    over(cv, with_glow(layer, NATURE_GLOW, 5, 0.5))
    return cv


def nature_banner(w, h):
    """Ornament: Baum auf einem Grasblock in der Mitte, daneben Grasbloecke, Wasser und Blumen."""
    cv = blank(w, h)
    layer = blank(w, h)
    cx = w / 2
    water = tex_water()
    for side in (-1, 1):
        a = 15
        iso_block(layer, cx + side * 80, h - 1 - block_height(a), a, water, water, water)
        a = 17
        _grass_block(layer, cx + side * 50, h - 1 - block_height(a), a)
    deco = blank(w, h)
    for side in (-1, 1):
        flower(deco, int(cx + side * 50 - 4), int(h - 1 - block_height(17) + 13), "#E8443A" if side < 0 else "#FFD23F",
               12, 2)
        tuft(deco, int(cx + side * 50 + 2), int(h - 1 - block_height(17) + 16), 7)
    over(layer, deco)
    outline(layer, NATURE_OUT, 2)
    mid = blank(w, h)
    a = 22
    top = h - 1 - block_height(a)
    _grass_block(mid, cx, top, a)
    tree(mid, cx, top + a * 0.55, 13, 19)
    outline(mid, NATURE_OUT, 2)
    over(layer, mid)
    sparkle(layer, int(cx + 34), 10, 4, (255, 255, 220))
    sparkle(layer, int(cx - 88), 30, 3, (255, 255, 220))
    over(cv, with_glow(layer, NATURE_GLOW, 8, 0.5))
    return cv


FALLBACKS = {
    "warp": {"corner": ender_corner, "corner_small": ender_corner_small, "banner": ender_banner},
    "farmwelt": {"corner": nature_corner, "corner_small": nature_corner_small, "banner": nature_banner},
}
