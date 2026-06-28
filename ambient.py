"""
Pygame ambient desktop view for Claude News.

Shows a scrolling RSS rail on the left and animated pixel/newspaper headlines
on the right. It reads the existing SQLite DB; it does not fetch or rate.
"""

import json
import math
import random
import textwrap
import time

from config import get_config
from database import get_connection, get_items
from digest import latest_report

CONFIG = get_config()

BG = (7, 8, 10)
INK = (232, 232, 220)
DIM = (88, 94, 104)
GREEN = (80, 250, 123)
CYAN = (139, 233, 253)
PINK = (255, 121, 198)
YELLOW = (255, 217, 102)
ORANGE = (255, 138, 80)
RED = (255, 85, 85)

SOURCE_COLORS = {
    "ANTH": PINK,
    "RDIT": RED,
    "RDSR": ORANGE,
    "HN": YELLOW,
    "GOOG": (66, 133, 244),
    "NEWS": CYAN,
}


def load_items(limit=60):
    conn = get_connection(CONFIG.db_path)
    items = get_items(conn, limit=limit, include_unrated=True)
    conn.close()
    return items


def parse_tldr(item):
    try:
        analysis = json.loads(item.get("analysis") or "{}")
    except json.JSONDecodeError:
        return ""
    return analysis.get("tldr") or analysis.get("first_impressions") or ""


def draw_text(surface, font, text, pos, color=INK, max_width=None, line_gap=4):
    x, y = pos
    if max_width:
        char_width = max(1, font.size("M")[0])
        width_chars = max(8, max_width // char_width)
        lines = []
        for raw in str(text).splitlines() or [""]:
            lines.extend(textwrap.wrap(raw, width=width_chars) or [""])
    else:
        lines = [str(text)]

    for line in lines:
        surface.blit(font.render(line, True, color), (x, y))
        y += font.get_height() + line_gap
    return y


def draw_scanlines(surface, width, height, tick):
    alpha = 26 + int(10 * math.sin(tick * 0.004))
    overlay = surface.convert_alpha()
    overlay.fill((0, 0, 0, 0))
    for y in range(0, height, 4):
        pygame = __import__("pygame")
        pygame.draw.line(overlay, (0, 0, 0, alpha), (0, y), (width, y))
    surface.blit(overlay, (0, 0))


def draw_rss_rail(surface, fonts, items, scroll, width, height):
    pygame = __import__("pygame")
    rail_w = min(430, max(330, width // 3))
    pygame.draw.rect(surface, (10, 11, 14), (0, 0, rail_w, height))
    pygame.draw.line(surface, (46, 49, 57), (rail_w, 0), (rail_w, height), 2)

    draw_text(surface, fonts["title"], "RSS WIRE", (18, 16), CYAN)
    draw_text(surface, fonts["tiny"], time.strftime("%Y-%m-%d %H:%M:%S"), (20, 48), DIM)

    y = 86 - (scroll % 120)
    loop_items = items + items[:8]
    for item in loop_items:
        source = item.get("source", "UNK")
        color = SOURCE_COLORS.get(source, INK)
        stars = "*" * int(item.get("stars") or 0)
        pygame.draw.rect(surface, (14, 16, 20), (12, y - 8, rail_w - 26, 104), border_radius=3)
        pygame.draw.rect(surface, color, (12, y - 8, 4, 104))
        draw_text(surface, fonts["tiny"], f"{source} {stars}", (24, y), color)
        draw_text(surface, fonts["small"], item.get("title", "No title"), (24, y + 20), INK, rail_w - 52)
        tldr = parse_tldr(item)
        if tldr:
            draw_text(surface, fonts["tiny"], tldr, (24, y + 70), DIM, rail_w - 52)
        y += 120
        if y > height + 120:
            break
    return rail_w


def newspaper_card(surface, fonts, item, rect, tick, accent):
    pygame = __import__("pygame")
    x, y, w, h = rect
    jitter = 1 if int(tick / 420) % 2 else 0
    paper = (222, 219, 197)
    ink = (24, 24, 22)
    shadow = (0, 0, 0)

    pygame.draw.rect(surface, shadow, (x + 8, y + 8, w, h), border_radius=2)
    pygame.draw.rect(surface, paper, (x + jitter, y, w, h), border_radius=2)
    pygame.draw.rect(surface, accent, (x + jitter, y, w, 8))

    source = item.get("source", "NEWS")
    draw_text(surface, fonts["paper_tiny"], f"CLAUDE NEWS EXTRA // {source}", (x + 18, y + 18), ink)
    pygame.draw.line(surface, ink, (x + 18, y + 42), (x + w - 18, y + 42), 2)
    draw_text(surface, fonts["paper_head"], item.get("title", "UNTITLED"), (x + 18, y + 56), ink, w - 36, 2)

    summary = item.get("summary") or parse_tldr(item) or "Developing signal. Details still noisy."
    draw_text(surface, fonts["paper_body"], summary, (x + 18, y + h - 96), (42, 42, 38), w - 36, 2)

    for px in range(x + 18, x + w - 18, 18):
        if random.random() < 0.45:
            pygame.draw.rect(surface, (70, 70, 62), (px, y + h - 22, 8, 3))


def draw_vibe_panel(surface, fonts, x, y, w):
    report = latest_report()
    if not report:
        headline = "NO SAVED VIBE REPORT"
        one_line = "Run python run.py vibe recent to seed the report layer."
    else:
        data = report.get("report", {})
        headline = data.get("headline", "VIBE REPORT")
        one_line = data.get("one_line") or data.get("mood", "")

    draw_text(surface, fonts["title"], "CURRENT VIBE", (x, y), PINK)
    y = draw_text(surface, fonts["headline"], headline.upper(), (x, y + 36), INK, w)
    draw_text(surface, fonts["small"], one_line, (x, y + 8), DIM, w)


def draw_pixel_bars(surface, tick, x, y, w, h):
    pygame = __import__("pygame")
    random.seed(int(tick / 300))
    cols = max(10, w // 18)
    for i in range(cols):
        bar_h = random.randint(16, h)
        color = [CYAN, PINK, GREEN, YELLOW, ORANGE][i % 5]
        dimmed = tuple(max(20, c // 2) for c in color)
        bx = x + i * 18
        pygame.draw.rect(surface, dimmed, (bx, y + h - bar_h, 10, bar_h))
        pygame.draw.rect(surface, color, (bx, y + h - bar_h, 10, 4))


def run_ambient(fullscreen=True, width=1280, height=720, fps=30, duration=None):
    import pygame

    pygame.init()
    flags = pygame.NOFRAME
    if fullscreen:
        info = pygame.display.Info()
        width, height = info.current_w, info.current_h
        flags |= pygame.FULLSCREEN

    screen = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Claude News Ambient")
    clock = pygame.time.Clock()

    fonts = {
        "title": pygame.font.SysFont("consolas", 20, bold=True),
        "headline": pygame.font.SysFont("consolas", 34, bold=True),
        "small": pygame.font.SysFont("consolas", 15),
        "tiny": pygame.font.SysFont("consolas", 12),
        "paper_head": pygame.font.SysFont("couriernew", 30, bold=True),
        "paper_body": pygame.font.SysFont("couriernew", 14),
        "paper_tiny": pygame.font.SysFont("couriernew", 12, bold=True),
    }

    items = load_items()
    last_reload = time.time()
    selected = 0
    scroll = 0
    running = True
    started = time.time()

    while running:
        if duration and time.time() - started >= duration:
            running = False

        tick = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_r:
                    items = load_items()
                    selected = 0
                elif event.key == pygame.K_RIGHT:
                    selected = (selected + 1) % max(1, len(items))
                elif event.key == pygame.K_LEFT:
                    selected = (selected - 1) % max(1, len(items))

        if time.time() - last_reload > 120:
            items = load_items()
            last_reload = time.time()

        width, height = screen.get_size()
        screen.fill(BG)
        if not items:
            items = [{"source": "NONE", "title": "No feed items yet", "summary": "Run a refresh first.", "stars": 0}]

        scroll += 0.32
        rail_w = draw_rss_rail(screen, fonts, items, scroll, width, height)

        right_x = rail_w + 34
        right_w = width - rail_w - 68
        draw_vibe_panel(screen, fonts, right_x, 28, right_w)
        draw_pixel_bars(screen, tick, right_x, height - 138, right_w, 92)

        selected = int((tick / 7000) % len(items))
        item = items[selected]
        accent = SOURCE_COLORS.get(item.get("source", ""), CYAN)
        card_w = min(760, right_w)
        card_h = min(330, max(260, height // 2))
        card_x = right_x + max(0, (right_w - card_w) // 2)
        card_y = 180 + int(math.sin(tick * 0.0012) * 8)
        newspaper_card(screen, fonts, item, (card_x, card_y, card_w, card_h), tick, accent)

        draw_text(screen, fonts["tiny"], "ESC/Q quit  R reload  arrows cycle", (right_x, height - 28), DIM)
        draw_scanlines(screen, width, height, tick)
        pygame.display.flip()
        clock.tick(fps)

    pygame.quit()
