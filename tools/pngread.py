#!/usr/bin/env python3
"""PNG-Leser nur mit der Standardbibliothek (8 Bit und Paletten, ohne Interlace). Liefert Zeilen aus (r, g, b, a)."""
import struct
import zlib


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
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + (a + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
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
