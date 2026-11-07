#!/usr/bin/env python3
"""
Texturen fuer das Dialog-/Menue-Design (Buttons, Hintergruende, Trennlinien, Balken).

Wird von generate_icons.py mit aufgerufen, kann aber auch einzeln benutzt werden.
Nur Standardbibliothek.

Was hier ueberschrieben wird (alles Vanilla-Pfade, wirkt also im ganzen Client,
solange das Pack aktiv ist):
    gui/sprites/widget/button.png, button_highlighted.png, button_disabled.png
        200x20, 9-Slice mit Rand 3 (die .mcmeta wird mitgeschrieben)
    gui/menu_background.png, gui/inworld_menu_background.png     16x16 Kachel
    gui/header_separator.png, footer_separator.png (+ inworld_)  32x2 Kachel
und neu (eigene Font, keine Vanilla-Pfade):
    textures/font/ui/bar_seg.png     Segment fuer Fortschrittsbalken
"""
import json
import os

ACCENT = (162, 53, 255)  # #A235FF, Lila aus dem Pay-Praefix


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def button_sprite(fill_top, fill_bot, border, inner_light, w=200, h=20):
    """Dunkler Button mit 1px Rand, abgeschnittenen Ecken und hellerer Kante oben."""
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            corner = (x in (0, w - 1)) and (y in (0, h - 1))
            if corner:
                row.append((0, 0, 0, 0))
                continue
            edge = x in (0, w - 1) or y in (0, h - 1)
            near_corner = ((x in (1, w - 2)) and (y in (0, h - 1))) or ((x in (0, w - 1)) and (y in (1, h - 2)))
            if edge:
                c = border
                if near_corner:
                    c = _mix(border, fill_top, 0.45)  # weichere Ecke
                row.append((*c, 255))
            elif y == 1:
                row.append((*inner_light, 255))
            else:
                row.append((*_mix(fill_top, fill_bot, (y - 1) / (h - 2)), 255))
        rows.append(row)
    return rows


def tile(rgb, alpha, noise=2, size=16):
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            n = ((x * 7 + y * 13 + x * y) % 5) - 2        # deterministisches, leichtes Rauschen
            n = max(-noise, min(noise, n))
            row.append((rgb[0] + n, rgb[1] + n, rgb[2] + n + (1 if n > 0 else 0), alpha))
        rows.append(row)
    return rows


def separator(color, w=32):
    return [[(*color, 255) for _ in range(w)], [(*color, 90) for _ in range(w)]]


def bar_segment():
    """4x8: Balken aus 4 Zeilen (weiss, wird per Textfarbe getoent) mit schwarzem Rand oben/unten."""
    rows = []
    for y in range(8):
        if y in (0, 7):
            rows.append([(0, 0, 0, 0)] * 4)
        elif y in (1, 6):
            rows.append([(0, 0, 0, 150)] * 4)
        else:
            rows.append([(255, 255, 255, 255)] * 4)
    return rows


def write_all(pack_dir, write_png):
    gui = os.path.join(pack_dir, "assets", "minecraft", "textures", "gui")
    widget = os.path.join(gui, "sprites", "widget")

    write_png(os.path.join(widget, "button.png"),
              button_sprite((30, 26, 51), (24, 20, 40), (59, 53, 88), (42, 37, 71)))
    write_png(os.path.join(widget, "button_highlighted.png"),
              button_sprite((46, 36, 76), (36, 28, 62), ACCENT, (66, 52, 108)))
    write_png(os.path.join(widget, "button_disabled.png"),
              button_sprite((20, 17, 31), (17, 14, 27), (38, 34, 58), (26, 22, 42)))
    meta = {"gui": {"scaling": {"type": "nine_slice", "width": 200, "height": 20, "border": 3}}}
    for name in ("button", "button_highlighted", "button_disabled"):
        with open(os.path.join(widget, name + ".png.mcmeta"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")

    write_png(os.path.join(gui, "menu_background.png"), tile((20, 16, 32), 255))
    write_png(os.path.join(gui, "inworld_menu_background.png"), tile((18, 14, 30), 205))
    for prefix in ("", "inworld_"):
        write_png(os.path.join(gui, prefix + "header_separator.png"), separator(ACCENT))
        write_png(os.path.join(gui, prefix + "footer_separator.png"), separator(ACCENT))

    write_png(os.path.join(pack_dir, "assets", "fmc", "textures", "font", "ui", "bar_seg.png"), bar_segment())
