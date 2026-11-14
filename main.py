#!/usr/bin/env python3
"""ai-happy-01: The little robot's first sunrise.

A small round robot stands on a green hill at dawn, waving at the sun
while holding a sunflower, greeting its very first sunrise. The sun
smiles back. Pure Python 3.13 standard library only; writes one
deterministic PNG to $MAKEFUN_OUTPUT_DIR/entry.png (default /output).
"""
import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- raster
# A flat RGB buffer; every draw is a pure function of constants, so two
# runs write byte-identical PNGs.


def new_canvas():
    return bytearray(W * H * 3)


def put(buf, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = color


def fill_rect(buf, x0, y0, x1, y1, color):
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W, x1)
    y1 = min(H, y1)
    for y in range(y0, y1):
        base = y * W * 3
        for x in range(x0, x1):
            i = base + x * 3
            buf[i], buf[i + 1], buf[i + 2] = color


def fill_circle(buf, cx, cy, r, color):
    r2 = r * r
    for y in range(cy - r, cy + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r2 - dy * dy)))
        for x in range(cx - dx, cx + dx + 1):
            put(buf, x, y, color)


def line(buf, x0, y0, x1, y1, color, width=1):
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy), 1)
    for s in range(steps + 1):
        t = s / steps
        x = int(round(x0 + dx * t))
        y = int(round(y0 + dy * t))
        fill_circle(buf, x, y, max(1, width // 2), color)


def arc(buf, cx, cy, r, a0, a1, color, width=1):
    # Angles in radians, measured from the positive x axis, going clockwise
    # on screen (y grows downwards).
    steps = max(8, int(abs(a1 - a0) * r / 3))
    for s in range(steps + 1):
        a = a0 + (a1 - a0) * s / steps
        x = int(round(cx + r * math.cos(a)))
        y = int(round(cy + r * math.sin(a)))
        fill_circle(buf, x, y, max(1, width // 2), color)


def round_rect(buf, x0, y0, x1, y1, r, color):
    fill_rect(buf, x0 + r, y0, x1 - r, y1, color)
    fill_rect(buf, x0, y0 + r, x1, y1 - r, color)
    fill_circle(buf, x0 + r, y0 + r, r, color)
    fill_circle(buf, x1 - r, y0 + r, r, color)
    fill_circle(buf, x0 + r, y1 - r, r, color)
    fill_circle(buf, x1 - r, y1 - r, r, color)


def fill_poly(buf, points, color):
    # Scanline fill for a simple polygon given as [(x, y), ...].
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(H, max(ys) + 1)):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            fill_rect(buf, int(xs[i]), y, int(xs[i + 1]) + 1, y + 1, color)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t)),
            int(lerp(c1[1], c2[1], t)),
            int(lerp(c1[2], c2[2], t)))


# ------------------------------------------------------------------- font
# A tiny 5x7 bitmap font, only the glyphs the message needs.
FONT = {
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    ",": ("00000", "00000", "00000", "00000", "00000", "01100", "01000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def draw_text(buf, text, cx, y, scale, color, halo=None):
    """Draw centred text; halo draws a soft light outline first."""
    widths = [5 * scale + scale for _ in text]
    total = sum(widths) - scale
    x = cx - total // 2
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "1":
                    if halo is not None:
                        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                                       (-2, -2), (2, -2), (-2, 2), (2, 2)):
                            fill_rect(buf, x + col * scale + ox,
                                      y + row * scale + oy,
                                      x + (col + 1) * scale + ox,
                                      y + (row + 1) * scale + oy, halo)
                    fill_rect(buf, x + col * scale, y + row * scale,
                              x + (col + 1) * scale, y + (row + 1) * scale,
                              color)
        x += 6 * scale


# ------------------------------------------------------------------ scene
SKY_TOP = (96, 150, 220)
SKY_MID = (250, 185, 115)
SKY_LOW = (255, 220, 145)
SUN = (255, 214, 64)
SUN_RAY = (255, 190, 45)
SUN_FACE = (122, 74, 20)
HILL_BACK = (112, 192, 112)
HILL_FRONT = (88, 178, 100)
CLOUD = (255, 252, 245)
ROBOT = (255, 246, 229)
ROBOT_EDGE = (205, 195, 170)
ROBOT_DARK = (43, 43, 43)
CHEEK = (255, 150, 150)
STEM = (60, 140, 60)
PETAL = (255, 200, 40)
FLOWER_CENTER = (120, 80, 30)
TEXT_COLOR = (122, 74, 33)
TEXT_HALO = (255, 250, 235)


def sky(buf):
    for y in range(H):
        t = y / H
        if t < 0.5:
            c = lerp_color(SKY_TOP, SKY_MID, t / 0.5)
        else:
            c = lerp_color(SKY_MID, SKY_LOW, (t - 0.5) / 0.5)
        fill_rect(buf, 0, y, W, y + 1, c)


def cloud(buf, cx, cy, s):
    for dx, dy, r in ((-2, 0, 2), (0, -1, 3), (2, 0, 2), (-1, 1, 2), (1, 1, 2)):
        fill_circle(buf, cx + dx * s, cy + dy * s, r * s, CLOUD)


def sun(buf, cx, cy, r):
    for k in range(12):
        a = math.pi * 2 * k / 12
        x0 = int(cx + (r + 8) * math.cos(a))
        y0 = int(cy + (r + 8) * math.sin(a))
        x1 = int(cx + (r + 52) * math.cos(a))
        y1 = int(cy + (r + 52) * math.sin(a))
        line(buf, x0, y0, x1, y1, SUN_RAY, 14)
    fill_circle(buf, cx, cy, r, SUN)
    # Happy closed eyes: two little arches.
    arc(buf, cx - 52, cy - 18, 26, math.pi, 2 * math.pi, SUN_FACE, 9)
    arc(buf, cx + 52, cy - 18, 26, math.pi, 2 * math.pi, SUN_FACE, 9)
    # A big open smile.
    arc(buf, cx, cy + 12, 62, math.pi * 0.15, math.pi * 0.85, SUN_FACE, 10)
    # Rosy cheeks.
    fill_circle(buf, cx - 88, cy + 22, 16, (255, 150, 120))
    fill_circle(buf, cx + 88, cy + 22, 16, (255, 150, 120))


def hill(buf, y_base, amp, phase, color):
    pts = [(0, H)]
    for x in range(0, W + 1, 16):
        y = int(y_base + amp * math.sin(math.pi * x / W + phase))
        pts.append((x, y))
    pts.append((W, H))
    fill_poly(buf, pts, color)


def flower(buf, x, y, r, petal, center):
    for k in range(5):
        a = math.pi * 2 * k / 5 - math.pi / 2
        fill_circle(buf, int(x + r * math.cos(a)), int(y + r * math.sin(a)),
                    max(2, r // 2), petal)
    fill_circle(buf, x, y, max(2, r // 2), center)


def bird(buf, x, y, s):
    arc(buf, x - s, y, s, math.pi * 1.15, math.pi * 1.85, ROBOT_DARK, 4)
    arc(buf, x + s, y, s, math.pi * 1.15, math.pi * 1.85, ROBOT_DARK, 4)


def butterfly(buf, x, y, s, color):
    fill_circle(buf, x - s, y - s // 2, s, color)
    fill_circle(buf, x + s, y - s // 2, s, color)
    fill_circle(buf, x - s, y + s // 2, max(2, s - 2), color)
    fill_circle(buf, x + s, y + s // 2, max(2, s - 2), color)
    line(buf, x, y - s, x, y + s, ROBOT_DARK, 3)


def rainbow(buf):
    cx, cy = 512, 1100
    bands = ((500, (255, 120, 120)), (522, (255, 180, 90)),
             (544, (255, 225, 110)), (566, (140, 220, 140)),
             (588, (130, 180, 255)))
    for r, color in bands:
        arc(buf, cx, cy, r, math.pi, 2 * math.pi, color, 18)


def robot(buf, cx, feet_y):
    # Antenna with a red ball.
    line(buf, cx, feet_y - 258, cx, feet_y - 218, ROBOT_DARK, 6)
    fill_circle(buf, cx, feet_y - 266, 12, (235, 80, 80))
    # Body: one friendly rounded shape, with a soft outline.
    round_rect(buf, cx - 104, feet_y - 222, cx + 104, feet_y + 4, 50,
               ROBOT_EDGE)
    round_rect(buf, cx - 100, feet_y - 218, cx + 100, feet_y, 48, ROBOT)
    # Big bright eyes with sparkles.
    for ex in (cx - 42, cx + 42):
        fill_circle(buf, ex, feet_y - 152, 20, ROBOT_DARK)
        fill_circle(buf, ex - 7, feet_y - 159, 7, (255, 255, 255))
    # Wide happy smile.
    arc(buf, cx, feet_y - 118, 44, math.pi * 0.15, math.pi * 0.85,
        ROBOT_DARK, 8)
    # Blushing cheeks.
    fill_circle(buf, cx - 68, feet_y - 112, 13, CHEEK)
    fill_circle(buf, cx + 68, feet_y - 112, 13, CHEEK)
    # Belly light.
    fill_circle(buf, cx, feet_y - 62, 16, (255, 214, 64))
    # Left arm waving up.
    line(buf, cx - 96, feet_y - 130, cx - 158, feet_y - 205,
         ROBOT_DARK, 12)
    fill_circle(buf, cx - 158, feet_y - 205, 12, ROBOT)
    # Right arm holding the sunflower stem.
    line(buf, cx + 96, feet_y - 130, cx + 150, feet_y - 178,
         ROBOT_DARK, 12)
    # Sunflower on its stem.
    line(buf, cx + 150, feet_y - 178, cx + 178, feet_y - 268, STEM, 8)
    for k in range(8):
        a = math.pi * 2 * k / 8
        fill_circle(buf, int(cx + 178 + 26 * math.cos(a)),
                    int(feet_y - 282 + 26 * math.sin(a)), 13, PETAL)
    fill_circle(buf, cx + 178, feet_y - 282, 18, FLOWER_CENTER)
    # Little feet.
    round_rect(buf, cx - 62, feet_y - 16, cx - 8, feet_y + 4, 8, ROBOT_DARK)
    round_rect(buf, cx + 8, feet_y - 16, cx + 62, feet_y + 4, 8, ROBOT_DARK)


def draw():
    buf = new_canvas()
    sky(buf)
    rainbow(buf)
    cloud(buf, 210, 150, 16)
    cloud(buf, 820, 110, 13)
    cloud(buf, 480, 210, 11)
    sun(buf, 720, 380, 138)
    hill(buf, 700, -62, 0.0, HILL_BACK)
    hill(buf, 830, -48, 1.2, HILL_FRONT)
    # Wildflowers on the front hill.
    for x, y, r, petal in (
            (120, 880, 12, (255, 120, 160)),
            (240, 930, 10, (255, 220, 80)),
            (360, 900, 12, (150, 140, 255)),
            (660, 920, 11, (255, 120, 160)),
            (790, 880, 12, (255, 220, 80)),
            (910, 940, 10, (150, 140, 255)),
            (60, 960, 10, (255, 220, 80)),
            (960, 860, 11, (255, 120, 160))):
        flower(buf, x, y, r, petal, FLOWER_CENTER)
    robot(buf, 500, 940)
    bird(buf, 220, 300, 16)
    bird(buf, 300, 260, 12)
    bird(buf, 880, 260, 14)
    butterfly(buf, 330, 850, 9, (255, 150, 200))
    butterfly(buf, 700, 860, 9, (150, 180, 255))
    draw_text(buf, "GOOD MORNING,", 512, 52, 6, TEXT_COLOR, TEXT_HALO)
    draw_text(buf, "SUNSHINE!", 512, 116, 6, TEXT_COLOR, TEXT_HALO)
    return buf


# -------------------------------------------------------------------- png
def png_bytes(buf):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw.extend(buf[y * W * 3:(y + 1) * W * 3])
    comp = zlib.compress(bytes(raw), 6)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes(draw()))
    print("wrote", path)


if __name__ == "__main__":
    main()
