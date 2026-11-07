#!/usr/bin/env python3
"""
Schreibt FontMetrics.java ins Plugin: die Breite jedes Zeichens der Minecraft-Standardschrift in Pixeln.

    python tools/gen_font_widths.py <pfad-zur-minecraft-client.jar>

Wird gebraucht, um Text in Menues exakt auszurichten (rechtsbuendig, Spalten). Die Breiten sind reine
Zahlen aus der Schrift-Textur; die Schrift selbst wird nicht kopiert. Nach einem Minecraft-Update, das die
Schrift aendert, einmal neu ausfuehren. Die Datei muss nur selten neu erzeugt werden.
"""
import os
import sys

import generate_icons as gi
import render_mock

FIRST, LAST = 32, 0x17F          # Leerzeichen bis Latin Extended-A
FALLBACK = 6


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    font = render_mock.Font(sys.argv[1])
    widths = []
    for cp in range(FIRST, LAST + 1):
        g = font.glyphs.get(chr(cp))
        widths.append(g["adv"] if g else FALLBACK)

    rows = []
    for i in range(0, len(widths), 16):
        rows.append("        " + ", ".join(str(w) for w in widths[i:i + 16]))
    body = ",\n".join(rows)

    java = f"""package com.example.myplugin.ui;

/**
 * GENERIERT von FMC-Resourcepack/tools/gen_font_widths.py - nicht von Hand aendern.
 * Breite jedes Zeichens der Minecraft-Standardschrift in Pixeln (inklusive 1 Pixel Abstand).
 */
public final class FontMetrics {{

    private static final int FIRST = {FIRST};
    private static final int FALLBACK = {FALLBACK};
    private static final int[] WIDTHS = {{
{body}
    }};

    private FontMetrics() {{
    }}

    /** Breite eines Zeichens; unbekannte Zeichen zaehlen als {FALLBACK} Pixel. */
    public static int width(char c) {{
        int index = c - FIRST;
        return index >= 0 && index < WIDTHS.length ? WIDTHS[index] : FALLBACK;
    }}

    /** Breite eines Textes; fett bedeutet 1 Pixel mehr pro Zeichen. */
    public static int width(String text, boolean bold) {{
        int total = 0;
        for (int i = 0; i < text.length(); i++) {{
            total += width(text.charAt(i)) + (bold ? 1 : 0);
        }}
        return total;
    }}
}}
"""
    out = os.path.join(gi.PLUGIN_DIR, "src", "main", "java", "com", "example", "myplugin", "ui", "FontMetrics.java")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(java)
    print(out)
    print("Beispiele:", {c: font.glyphs[c]["adv"] for c in "Ail .0Mü"})


if __name__ == "__main__":
    main()
