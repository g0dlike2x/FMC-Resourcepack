#!/usr/bin/env python3
"""
Hintergruende fuer Kisten-GUIs (Inventare) im FMC-Stil.

Wird von generate_icons.py mit aufgerufen. Nur Standardbibliothek.

So funktioniert es: Der Inventartitel enthaelt ein Zeichen der Font fmc:icons, dessen Bild genau so gross ist
wie das Inventar (176 x 222 bzw. 176 x 168 Pixel, 1 Bildpixel = 1 GUI-Pixel). Es wird ueber die Kiste gelegt und
verdeckt die Vanilla-Textur. Die Items liegen davor und bleiben normale, klickbare Items.

Geometrie (aus Vanilla, ContainerScreen):
    Titel beginnt bei x = 8, y = 6 (Grundlinie bei y = 13)  ->  ascent = 13 setzt die Oberkante des Bildes auf y = 0
    Slot-Item bei (8 + 18*c, 18 + 18*r), der Slot-Rahmen sitzt eins links/oberhalb davon (7, 17)
    Spielerinventar beginnt bei y = Hoehe - 82, die Hotbar bei y = Hoehe - 24 (jeweils Item-Position)
    Minecraft laedt Schriftbilder nur bis 256 x 256 Pixel; 176 x 222 passt.

Zeichen (U+EA00 bis U+EAFF sind fuer Kisten-GUIs reserviert):
    U+EA00  Endertruhe (54 Slots)      U+EA01  Bank (27 Slots)

Neue Menues: eine Funktion wie make_ec() schreiben, in CHESTS eintragen, generate_icons.py ausfuehren.
"""
import json
import os

W = 176
CHEST_ASCENT = 13          # Oberkante des Bildes = Oberkante des Inventars (siehe oben)
CHEST_TITLE_X = 8          # der Titel beginnt 8 Pixel vom linken Rand

ACCENT = (162, 53, 255)    # #A235FF, Lila aus dem Pay-Praefix
PANEL_TOP = (28, 23, 56)
PANEL_BOT = (18, 15, 38)
BORDER = (59, 53, 88)      # #3B3558, wie die Buttons
HEADER_TOP = (36, 30, 70)
HEADER_BOT = (28, 23, 56)
CELL_FILL = (13, 10, 28)
CELL_DARK = (6, 4, 14)
CELL_LIGHT = (52, 47, 90)
DIVIDER = (120, 45, 190)


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[(0, 0, 0, 255)] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = (c[0], c[1], c[2], 255)

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, c)

    def vgrad(self, x, y, w, h, top, bot):
        for yy in range(h):
            c = _mix(top, bot, yy / max(1, h - 1))
            for xx in range(w):
                self.put(x + xx, y + yy, c)

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def inset(self, x, y, w, h, fill=CELL_FILL, dark=CELL_DARK, light=CELL_LIGHT):
        """Eingelassene Flaeche: oben/links dunkel, unten/rechts hell (wie ein Vanilla-Slot)."""
        self.rect(x, y, w, h, fill)
        self.hline(x, y, w - 1, dark)
        self.rect(x, y, 1, h - 1, dark)
        self.hline(x + 1, y + h - 1, w - 1, light)
        self.rect(x + w - 1, y + 1, 1, h - 1, light)

    def frame(self, x, y, w, h, border, fill_top, fill_bot, cut=True):
        """Flaeche mit 1 Pixel Rand und abgeschnittenen Ecken."""
        self.vgrad(x, y, w, h, fill_top, fill_bot)
        self.rect(x, y, w, 1, border)
        self.rect(x, y + h - 1, w, 1, border)
        self.rect(x, y, 1, h, border)
        self.rect(x + w - 1, y, 1, h, border)
        if cut:
            under = _mix(fill_top, fill_bot, 0.5)
            for cx, cy in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
                self.put(cx, cy, under)

    def rows(self):
        return [list(r) for r in self.px]


def _base(h, divider_y):
    """Panel mit Rand, Kopfleiste (Titelzeile) und Trennlinie ueber dem Spielerinventar."""
    cv = Canvas(W, h)
    cv.vgrad(0, 0, W, h, PANEL_TOP, PANEL_BOT)
    # Kopfleiste: y 1..14, darunter die lila Linie
    cv.vgrad(1, 1, W - 2, 14, HEADER_TOP, HEADER_BOT)
    cv.hline(1, 15, W - 2, ACCENT)
    cv.hline(1, 16, W - 2, (46, 22, 84))
    # Aussenrand (die Ecken bleiben deckend, damit die Vanilla-Textur darunter nicht durchscheint)
    cv.rect(0, 0, W, 1, BORDER)
    cv.rect(0, h - 1, W, 1, BORDER)
    cv.rect(0, 0, 1, h, BORDER)
    cv.rect(W - 1, 0, 1, h, BORDER)
    for x, y in ((0, 0), (W - 1, 0), (0, h - 1), (W - 1, h - 1)):
        cv.put(x, y, CELL_DARK)
    # Trennlinie ueber dem Spielerinventar (der Vanilla-Text "Inventar" steht darunter)
    cv.hline(7, divider_y, W - 14, DIVIDER)
    # Spielerinventar: 3 Reihen + Hotbar
    inv_y = h - 82 - 1
    for r in range(3):
        for c in range(9):
            cv.inset(7 + 18 * c, inv_y + 18 * r, 18, 18)
    hot_y = h - 24 - 1
    for c in range(9):
        cv.inset(7 + 18 * c, hot_y, 18, 18)
    return cv


def make_ec():
    """Endertruhe: 5 Reihen Kistenslots (0-44) und eine Leiste (45-53) mit Zurueck / Info / Weiter."""
    h = 222
    cv = _base(h, divider_y=126)
    for r in range(5):
        for c in range(9):
            cv.inset(7 + 18 * c, 17 + 18 * r, 18, 18)
    # Leiste: eigene Flaeche statt Slots (die Fueller-Items sind unsichtbar)
    cv.frame(7, 107, 162, 18, (45, 39, 78), (26, 21, 52), (20, 16, 42), cut=False)
    for c in (0, 1, 2, 6, 7, 8):
        cv.rect(7 + 18 * c + 8, 107 + 8, 2, 2, (58, 51, 98))
    for c in (3, 5):    # Zurueck / Weiter
        cv.frame(7 + 18 * c, 107, 18, 18, (96, 82, 160), (44, 35, 84), (34, 27, 66))
    cv.frame(7 + 18 * 4, 107, 18, 18, ACCENT, (62, 32, 110), (44, 24, 82))   # Info
    return cv.rows()


def make_bank():
    """Bank: Fenster ueber 3 Reihen, links Einzahlen (gruen), Mitte Konto-Info, rechts Abheben (rot)."""
    h = 168
    cv = _base(h, divider_y=72)
    cv.inset(7, 17, 162, 54, fill=(14, 11, 30))
    # Dezente Schraffur in den freien Flaechen
    for y in range(18, 70):
        for x in range(8, 168):
            if (x + y) % 6 == 0:
                cv.put(x, y, (18, 14, 38))
    # Einzahlen: Plattenbreite 52, Mitte bei x = 52 (Item in Spalte 2)
    cv.frame(26, 35, 52, 18, (47, 158, 90), (24, 58, 42), (15, 36, 28))
    cv.hline(28, 36, 48, (40, 92, 64))
    # Abheben: Mitte bei x = 124 (Item in Spalte 6)
    cv.frame(98, 35, 52, 18, (176, 58, 74), (62, 24, 33), (38, 15, 22))
    cv.hline(100, 36, 48, (96, 40, 52))
    # Konto-Info (Spalte 4)
    cv.frame(7 + 18 * 4, 35, 18, 18, ACCENT, (62, 32, 110), (44, 24, 82))
    # Verbindungslinien Platte - Info
    cv.hline(78, 44, 1, (80, 64, 130))
    cv.hline(97, 44, 1, (80, 64, 130))
    return cv.rows()


# name -> (Zeichen, Datei, Funktion, Hoehe)
CHESTS = [
    ("ec", "\uEA00", make_ec, 222),
    ("bank", "\uEA01", make_bank, 168),
]


def glyph_advance(width, scale=1.0):
    """Vorschub eines Bitmap-Zeichens: int(0.5 + Breite * Skalierung) + 1 (hier Skalierung 1)."""
    return int(0.5 + width * scale) + 1


def write_all(pack_dir, write_png):
    """Schreibt Texturen, Font-Eintraege (Rueckgabe) und das unsichtbare Item fuer die Fueller-Slots."""
    ui_dir = os.path.join(pack_dir, "assets", "fmc", "textures", "font", "ui")
    providers, info = [], {}
    for name, char, fn, height in CHESTS:
        rows = fn()
        assert len(rows) == height and len(rows[0]) == W, name
        write_png(os.path.join(ui_dir, f"chest_{name}.png"), rows)
        providers.append({"type": "bitmap", "file": f"fmc:font/ui/chest_{name}.png",
                          "ascent": CHEST_ASCENT, "height": height, "chars": [char]})
        info[name] = char

    # Unsichtbares Item: Fueller-Slots in der Leiste sollen nichts zeigen (item_model = fmc:blank).
    items = os.path.join(pack_dir, "assets", "fmc", "items")
    models = os.path.join(pack_dir, "assets", "fmc", "models", "item")
    os.makedirs(items, exist_ok=True)
    os.makedirs(models, exist_ok=True)
    with open(os.path.join(items, "blank.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"model": {"type": "minecraft:model", "model": "fmc:item/blank"}}, f, indent=2)
        f.write("\n")
    with open(os.path.join(models, "blank.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"elements": []}, f, indent=2)
        f.write("\n")
    return providers, info, glyph_advance(W)
