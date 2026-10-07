"""Big block-letter date banner, e.g. "23 / 10".

The glyphs are drawn by hand (no extra library needed). Every glyph is 7 rows tall.
"""

GLYPHS = {
    "0": [
        "  ░████  ",
        " ░██ ░██ ",
        "░██ ░████",
        "░██░██░██",
        "░████ ░██",
        " ░██ ░██ ",
        "  ░████  ",
    ],
    "1": [
        "  ░██  ",
        "░████  ",
        "  ░██  ",
        "  ░██  ",
        "  ░██  ",
        "  ░██  ",
        "░██████",
    ],
    "2": [
        " ░██████ ",
        "░██   ░██",
        "      ░██",
        "  ░█████ ",
        " ░██     ",
        "░██      ",
        "░████████",
    ],
    "3": [
        " ░██████ ",
        "░██   ░██",
        "      ░██",
        "  ░█████ ",
        "      ░██",
        "░██   ░██",
        " ░██████ ",
    ],
    "4": [
        "    ░████ ",
        "   ░██░██ ",
        "  ░██ ░██ ",
        " ░██  ░██ ",
        "░█████████",
        "      ░██ ",
        "      ░██ ",
    ],
    "5": [
        "░████████",
        "░██      ",
        "░███████ ",
        "      ░██",
        "      ░██",
        "░██   ░██",
        " ░██████ ",
    ],
    "6": [
        " ░██████ ",
        "░██   ░██",
        "░██      ",
        "░███████ ",
        "░██   ░██",
        "░██   ░██",
        " ░██████ ",
    ],
    "7": [
        "░████████",
        "      ░██",
        "     ░██ ",
        "    ░██  ",
        "   ░██   ",
        "   ░██   ",
        "   ░██   ",
    ],
    "8": [
        " ░██████ ",
        "░██   ░██",
        "░██   ░██",
        " ░██████ ",
        "░██   ░██",
        "░██   ░██",
        " ░██████ ",
    ],
    "9": [
        " ░██████ ",
        "░██   ░██",
        "░██   ░██",
        " ░███████",
        "      ░██",
        "░██   ░██",
        " ░██████ ",
    ],
    "/": [
        "      ░██",
        "     ░██ ",
        "    ░██  ",
        "   ░██   ",
        "  ░██    ",
        " ░██     ",
        "░██      ",
    ],
    " ": [" "] * 7,
}

HEIGHT = 7
LETTER_GAP = " "  # space between two digits


def render(text: str) -> str:
    """Render a string made of digits, '/' and spaces."""
    rows = [""] * HEIGHT
    for i, ch in enumerate(text):
        glyph = GLYPHS[ch]
        width = max(len(line) for line in glyph)
        for r in range(HEIGHT):
            gap = LETTER_GAP if i > 0 else ""
            rows[r] += gap + glyph[r].ljust(width)
    return "\n".join(row.rstrip() for row in rows)


def render_date(day: int, month: int) -> str:
    """render_date(23, 10) -> the "23 / 10" banner."""
    return render(f"{day:02d} / {month:02d}")


if __name__ == "__main__":
    print(render_date(23, 10))
    print()
    print(render_date(4, 5))
    print()
    print(render("6789"))
