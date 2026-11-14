#!/usr/bin/env python3
"""ai-happy-01: The happiest ride ever (v3).

A round little hamster rides a white unicorn under a big rainbow,
laughing with its whole face, on a bright green hill. Pure Python
3.13 standard library only; writes one deterministic PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (default /output).
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


def fill_circle_vgrad(buf, cx, cy, r, c_top, c_bottom, y0, y1):
    # Fill a circle with a smooth vertical gradient (light top, darker
    # bottom) so a shape reads as rounded, not flat. y0/y1 are the
    # global gradient range, so several circles share one shading.
    for y in range(cy - r, cy + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        t = (y - y0) / (y1 - y0)
        t = max(0.0, min(1.0, t))
        c = lerp_color(c_top, c_bottom, t)
        for x in range(cx - dx, cx + dx + 1):
            put(buf, x, y, c)


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
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
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
SKY_TOP = (130, 190, 240)
SKY_MID = (170, 215, 245)
SKY_LOW = (220, 240, 250)
HILL_BACK = (112, 192, 112)
HILL_FRONT = (88, 178, 100)
CLOUD = (255, 252, 245)
WHITE = (255, 255, 255)
CREAM = (255, 244, 224)
OUTLINE = (205, 195, 185)
DARK = (43, 43, 43)
GOLD = (255, 200, 60)
PINK = (255, 150, 150)
CHEEK = (255, 150, 150)
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


def rainbow(buf):
    cx, cy = 512, 1250
    bands = ((700, (255, 100, 100)), (730, (255, 170, 60)),
             (760, (255, 220, 80)), (790, (120, 210, 120)),
             (820, (110, 170, 255)), (850, (170, 120, 230)))
    for r, color in bands:
        arc(buf, cx, cy, r, math.pi, 2 * math.pi, color, 30)


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
    arc(buf, x - s, y, s, math.pi * 1.15, math.pi * 1.85, DARK, 4)
    arc(buf, x + s, y, s, math.pi * 1.15, math.pi * 1.85, DARK, 4)


def butterfly(buf, x, y, s, color):
    fill_circle(buf, x - s, y - s // 2, s, color)
    fill_circle(buf, x + s, y - s // 2, s, color)
    fill_circle(buf, x - s, y + s // 2, max(2, s - 2), color)
    fill_circle(buf, x + s, y + s // 2, max(2, s - 2), color)
    line(buf, x, y - s, x, y + s, DARK, 3)


def unicorn(buf):
    # Tail: rainbow strands flowing down-right from the rear.
    line(buf, 645, 760, 705, 850, (255, 120, 120), 18)
    line(buf, 650, 780, 715, 870, (255, 205, 90), 18)
    line(buf, 652, 800, 720, 885, (140, 220, 140), 18)
    # Legs, galloping: thick outlined lines angled out from the body.
    for (x0, y0, x1, y1) in ((450, 810, 405, 905),
                             (490, 815, 465, 910),
                             (580, 815, 615, 905),
                             (620, 810, 660, 900)):
        line(buf, x0, y0, x1, y1, OUTLINE, 26)
        line(buf, x0, y0, x1, y1, WHITE, 20)
        fill_circle(buf, x1, y1, 14, GOLD)
    # Body (smaller, so the hamster is the star).
    round_rect(buf, 420, 750, 650, 840, 45, OUTLINE)
    round_rect(buf, 424, 754, 646, 836, 42, WHITE)
    # Neck (outline then white).
    fill_poly(buf, [(406, 814), (464, 794), (399, 666), (351, 694)], OUTLINE)
    fill_poly(buf, [(410, 810), (460, 790), (395, 670), (355, 690)], WHITE)
    # Mane: overlapping rainbow blobs along the back of the neck.
    for mx, my, mr, mc in ((457, 766, 20, (255, 120, 120)),
                           (441, 736, 20, (255, 205, 90)),
                           (425, 706, 20, (255, 225, 110)),
                           (412, 682, 18, (140, 220, 140))):
        fill_circle(buf, mx, my, mr, mc)
    # Head.
    fill_circle(buf, 372, 660, 44, OUTLINE)
    fill_circle(buf, 372, 660, 40, WHITE)
    # Muzzle.
    round_rect(buf, 312, 668, 378, 708, 16, OUTLINE)
    round_rect(buf, 316, 672, 374, 704, 14, WHITE)
    # Nostril and a small smile.
    fill_circle(buf, 330, 690, 5, DARK)
    arc(buf, 348, 688, 16, math.pi * 0.15, math.pi * 0.85, DARK, 4)
    # Gentle eye with a sparkle.
    fill_circle(buf, 366, 652, 8, DARK)
    fill_circle(buf, 363, 649, 3, WHITE)
    # Ear.
    fill_poly(buf, [(352, 622), (364, 590), (382, 618)], OUTLINE)
    fill_poly(buf, [(356, 618), (364, 598), (376, 616)], PINK)
    # Golden horn.
    fill_poly(buf, [(340, 624), (312, 560), (366, 618)], GOLD)
    line(buf, 330, 596, 344, 590, (220, 160, 40), 3)
    line(buf, 322, 578, 336, 572, (220, 160, 40), 3)


def hamster(buf, cx, cy):
    # Body: an avocado/pear shape — a wide bottom circle plus a
    # narrower top circle, not one round ball.
    fill_circle(buf, cx, cy + 35, 130, OUTLINE)
    fill_circle(buf, cx, cy - 75, 100, OUTLINE)
    fill_circle(buf, cx, cy + 35, 126, CREAM)
    fill_circle(buf, cx, cy - 75, 96, CREAM)
    # Ears, poking out of the narrower top.
    for ex in (cx - 52, cx + 52):
        fill_circle(buf, ex, cy - 158, 24, OUTLINE)
        fill_circle(buf, ex, cy - 158, 20, CREAM)
        fill_circle(buf, ex, cy - 155, 11, PINK)
    # Happy closed eyes.
    arc(buf, cx - 48, cy - 25, 24, math.pi, 2 * math.pi, DARK, 8)
    arc(buf, cx + 48, cy - 25, 24, math.pi, 2 * math.pi, DARK, 8)
    # Pink nose.
    fill_poly(buf, [(cx - 13, cy), (cx + 13, cy), (cx, cy + 15)], PINK)
    # HUGE open laugh with two big front teeth.
    fill_circle(buf, cx, cy + 55, 48, DARK)
    fill_rect(buf, cx - 18, cy + 15, cx, cy + 59, WHITE)
    fill_rect(buf, cx, cy + 15, cx + 18, cy + 59, WHITE)
    line(buf, cx, cy + 15, cx, cy + 59, DARK, 4)
    # Blushing cheeks.
    fill_circle(buf, cx - 82, cy + 35, 18, CHEEK)
    fill_circle(buf, cx + 82, cy + 35, 18, CHEEK)
    # Left arm waving up.
    line(buf, cx - 95, cy + 50, cx - 148, cy - 25, DARK, 12)
    fill_circle(buf, cx - 148, cy - 25, 15, CREAM)
    # Right arm resting on the unicorn's back.
    line(buf, cx + 95, cy + 50, cx + 125, cy + 125, DARK, 12)
    fill_circle(buf, cx + 125, cy + 125, 15, CREAM)
    # Little feet on the unicorn's back.
    round_rect(buf, cx - 58, cy + 125, cx - 18, cy + 145, 10, DARK)
    round_rect(buf, cx + 18, cy + 125, cx + 58, cy + 145, 10, DARK)


def draw():
    buf = new_canvas()
    sky(buf)
    rainbow(buf)
    cloud(buf, 170, 180, 15)
    cloud(buf, 850, 150, 13)
    cloud(buf, 720, 260, 11)
    hill(buf, 820, -55, 0.0, HILL_BACK)
    hill(buf, 920, -45, 1.2, HILL_FRONT)
    # Wildflowers on the front hill.
    for x, y, r, petal in (
            (120, 950, 12, (255, 120, 160)),
            (240, 980, 10, (255, 220, 80)),
            (360, 960, 12, (150, 140, 255)),
            (660, 970, 11, (255, 120, 160)),
            (790, 950, 12, (255, 220, 80)),
            (910, 980, 10, (150, 140, 255)),
            (60, 990, 10, (255, 220, 80)),
            (960, 940, 11, (255, 120, 160))):
        flower(buf, x, y, r, petal, FLOWER_CENTER)
    unicorn(buf)
    hamster(buf, 540, 620)
    bird(buf, 220, 330, 16)
    bird(buf, 300, 290, 12)
    bird(buf, 880, 300, 14)
    butterfly(buf, 330, 900, 9, (255, 150, 200))
    butterfly(buf, 700, 910, 9, (150, 180, 255))
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
