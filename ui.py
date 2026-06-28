"""
Claude News Feed - Terminal UI
Always-behind window with cyberpunk terminal aesthetic.
"""

import tkinter as tk
from tkinter import font as tkfont
import json
import webbrowser
import threading
from pathlib import Path
import ctypes
from config import get_config

CONFIG = get_config()

# Windows-specific: keep window always behind others
try:
    from ctypes import windll
    HWND_BOTTOM = 1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
except:
    windll = None


class Tooltip:
    """Tiny hover tooltip — shown after a short delay on Enter, gone on Leave."""

    DELAY_MS = 350

    def __init__(self, widget, text_getter):
        """text_getter: callable returning the current tooltip string (or '')"""
        self.widget = widget
        self.text_getter = text_getter
        self.tipwindow = None
        self.scheduled = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event):
        self._cancel()
        self.scheduled = self.widget.after(self.DELAY_MS, self._show)

    def _on_leave(self, _event):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self.scheduled:
            self.widget.after_cancel(self.scheduled)
            self.scheduled = None

    def _show(self):
        text = self.text_getter() or ""
        if not text or self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="#1a1a1a")
        label = tk.Label(
            tw, text=text, justify=tk.LEFT,
            bg="#1a1a1a", fg="#f8f8f2",
            font=("Consolas", 9),
            wraplength=380,
            padx=8, pady=5,
            borderwidth=1, relief="solid",
        )
        label.pack()
        self.tipwindow = tw

    def _hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class StarFilter:
    """The clickable star filter at top"""

    def __init__(self, parent, on_change):
        self.frame = tk.Frame(parent, bg='#0a0a0a')
        self.on_change = on_change
        self.states = [False, False, False, False, False]  # which stars are active

        self.buttons = []
        for i in range(5):
            btn = tk.Label(
                self.frame,
                text="○",
                font=("Consolas", 14),
                fg="#404040",
                bg="#0a0a0a",
                cursor="hand2",
                padx=5
            )
            btn.bind("<Button-1>", lambda e, idx=i: self.toggle(idx))
            btn.pack(side=tk.LEFT, padx=2)
            self.buttons.append(btn)

        # All button
        self.all_btn = tk.Label(
            self.frame,
            text="[ALL]",
            font=("Consolas", 10),
            fg="#606060",
            bg="#0a0a0a",
            cursor="hand2",
            padx=10
        )
        self.all_btn.bind("<Button-1>", lambda e: self.select_all())
        self.all_btn.pack(side=tk.LEFT, padx=10)

    def toggle(self, idx):
        self.states[idx] = not self.states[idx]
        self.update_display()
        self.on_change(self.get_active_stars())

    def select_all(self):
        self.states = [False, False, False, False, False]
        self.update_display()
        self.on_change([])

    def get_active_stars(self):
        """Return list of star levels to show"""
        active = [i + 1 for i, s in enumerate(self.states) if s]
        return active if active else []  # empty = show all

    def update_display(self):
        colors = ["#ff6b6b", "#ffa06b", "#ffd96b", "#9be36b", "#6bfff0"]
        for i, btn in enumerate(self.buttons):
            if self.states[i]:
                btn.config(text="●", fg=colors[i])
            else:
                btn.config(text="○", fg="#404040")


class SourceFilter:
    """Clickable source filter and refresh source selector."""

    SOURCE_COLORS = {
        'ANTH': '#ff79c6',
        'RDIT': '#ff5555',
        'RDSR': '#ff8a50',
        'NEWS': '#8be9fd',
        'HN': '#ff9500',
        'GOOG': '#4285f4',
    }

    def __init__(self, parent, sources, on_change):
        self.frame = tk.Frame(parent, bg='#0a0a0a')
        self.on_change = on_change
        self.states = {source: True for source in sources}
        self.buttons = {}

        for source in sources:
            btn = tk.Label(
                self.frame,
                text=f"[{source}]",
                font=("Consolas", 10),
                fg=self.SOURCE_COLORS.get(source, "#f8f8f2"),
                bg="#0a0a0a",
                cursor="hand2",
                padx=5,
            )
            btn.bind("<Button-1>", lambda e, code=source: self.toggle(code))
            btn.pack(side=tk.LEFT, padx=2)
            self.buttons[source] = btn

    def toggle(self, source):
        self.states[source] = not self.states[source]
        if not any(self.states.values()):
            self.states[source] = True
        self.update_display()
        self.on_change(self.get_active_sources())

    def get_active_sources(self):
        return {source for source, active in self.states.items() if active}

    def update_display(self):
        for source, btn in self.buttons.items():
            if self.states[source]:
                btn.config(
                    text=f"[{source}]",
                    fg=self.SOURCE_COLORS.get(source, "#f8f8f2"),
                )
            else:
                btn.config(text=f" {source} ", fg="#404040")


class NewsItemWidget:
    """Single news item row"""

    def __init__(self, parent, item, on_click, on_open):
        self.item = item
        self.on_open = on_open
        self.frame = tk.Frame(parent, bg='#0a0a0a')

        # Source
        source_colors = {
            'ANTH': '#ff79c6',  # pink - official
            'RDIT': '#ff5555',  # red - reddit
            'RDSR': '#ff8a50',  # orange-red - reddit search
            'NEWS': '#8be9fd',  # cyan - news api
            'BLOG': '#50fa7b',  # green - blogs
            'HN':   '#ff9500',  # orange - hacker news
            'GOOG': '#4285f4',  # blue - google news
        }
        source_color = source_colors.get(item['source'], '#f8f8f2')

        self.source = tk.Label(
            self.frame,
            text=f"{item['source']:4}",
            font=("Consolas", 10),
            fg=source_color,
            bg="#0a0a0a",
            width=5
        )
        self.source.pack(side=tk.LEFT)

        # Separator
        tk.Label(self.frame, text="│", fg="#404040", bg="#0a0a0a",
                 font=("Consolas", 10)).pack(side=tk.LEFT)

        # Title (clickable, wraps to show full text)
        self.title = tk.Label(
            self.frame,
            text=item['title'],
            font=("Consolas", 10),
            fg=self._title_color(),
            bg="#0a0a0a",
            cursor="hand2",
            anchor="w",
            justify="left",
            wraplength=550
        )
        self.title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.title.bind("<Button-1>", lambda e: self.open_url())
        self.title.bind("<Enter>", lambda e: self.title.config(fg="#8be9fd"))
        self.title.bind("<Leave>", lambda e: self.title.config(fg=self._title_color()))

        # Separator
        tk.Label(self.frame, text="│", fg="#404040", bg="#0a0a0a",
                 font=("Consolas", 10)).pack(side=tk.LEFT)

        # Stars (clickable for analysis)
        stars = item.get('stars', 0)
        star_colors = ["#ff6b6b", "#ffa06b", "#ffd96b", "#9be36b", "#6bfff0"]
        star_text = ""
        for i in range(5):
            if i < stars:
                star_text += "★"
            else:
                star_text += "☆"

        self.stars = tk.Label(
            self.frame,
            text=star_text,
            font=("Consolas", 10),
            fg=star_colors[stars - 1] if stars > 0 else "#404040",
            bg="#0a0a0a",
            cursor="hand2"
        )
        self.stars.pack(side=tk.LEFT, padx=5)
        self.stars.bind("<Button-1>", lambda e: on_click(item))

        # Hover tooltip: show the LLM's quick reaction (tldr -> first_impressions)
        Tooltip(self.stars, lambda: self._tooltip_text())

    def _title_color(self):
        return "#808080" if self.item.get('read') else "#f8f8f2"

    def open_url(self):
        webbrowser.open(self.item['url'])
        self.item['read'] = 1
        self.title.config(fg=self._title_color())
        self.on_open(self.item)

    def _tooltip_text(self) -> str:
        try:
            analysis = json.loads(self.item.get('analysis') or '{}')
        except (json.JSONDecodeError, TypeError):
            return ""
        if analysis.get('error'):
            return "(rating failed — will retry next refresh)"
        return (analysis.get('tldr')
                or analysis.get('first_impressions')
                or "")


class AnalysisView:
    """Detailed analysis view"""

    def __init__(self, parent, on_back):
        self.frame = tk.Frame(parent, bg='#0a0a0a')
        self.on_back = on_back

        # Back button
        self.back = tk.Label(
            self.frame,
            text="← BACK",
            font=("Consolas", 12, "bold"),
            fg="#ff79c6",
            bg="#0a0a0a",
            cursor="hand2"
        )
        self.back.pack(anchor="w", pady=10, padx=10)
        self.back.bind("<Button-1>", lambda e: on_back())
        self.back.bind("<Enter>", lambda e: self.back.config(fg="#ff5555"))
        self.back.bind("<Leave>", lambda e: self.back.config(fg="#ff79c6"))

        # Content area
        self.content = tk.Text(
            self.frame,
            font=("Consolas", 11),
            fg="#f8f8f2",
            bg="#0a0a0a",
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=15,
            pady=10,
            cursor="arrow"
        )
        self.content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.content.config(state=tk.DISABLED)

    def show(self, item):
        """Display analysis for an item"""
        self.content.config(state=tk.NORMAL)
        self.content.delete(1.0, tk.END)

        # Title
        self.content.insert(tk.END, f"{item['title']}\n", "title")
        self.content.insert(tk.END, f"{'─'*50}\n\n", "sep")

        # Parse analysis
        try:
            analysis = json.loads(item.get('analysis', '{}'))
        except:
            analysis = {}

        sections = [
            ("FIRST IMPRESSIONS", analysis.get('first_impressions', 'No analysis available')),
            ("IMPLICATIONS", analysis.get('implications', '')),
            ("ACTION ITEMS", analysis.get('action_items', 'None')),
            ("TL;DR", analysis.get('tldr', '')),
        ]

        for header, content in sections:
            if content:
                self.content.insert(tk.END, f"{header}:\n", "header")
                self.content.insert(tk.END, f"{content}\n\n", "body")

        # Link
        self.content.insert(tk.END, f"\n{'─'*50}\n", "sep")
        self.content.insert(tk.END, f"URL: {item['url']}\n", "link")

        # Configure tags
        self.content.tag_config("title", font=("Consolas", 14, "bold"), foreground="#50fa7b")
        self.content.tag_config("sep", foreground="#404040")
        self.content.tag_config("header", font=("Consolas", 11, "bold"), foreground="#ff79c6")
        self.content.tag_config("body", foreground="#f8f8f2")
        self.content.tag_config("link", foreground="#8be9fd")

        self.content.config(state=tk.DISABLED)


class ActionAnalysisView:
    """Detailed analysis view with curation actions."""

    def __init__(self, parent, on_back, on_open, on_rerate, on_hide):
        self.frame = tk.Frame(parent, bg='#0a0a0a')
        self.on_back = on_back
        self.on_open = on_open
        self.on_rerate = on_rerate
        self.on_hide = on_hide
        self.item = None

        action_row = tk.Frame(self.frame, bg="#0a0a0a")
        action_row.pack(fill=tk.X, pady=10, padx=10)

        self.back = tk.Label(
            action_row,
            text="< BACK",
            font=("Consolas", 12, "bold"),
            fg="#ff79c6",
            bg="#0a0a0a",
            cursor="hand2"
        )
        self.back.pack(side=tk.LEFT)
        self.back.bind("<Button-1>", lambda e: on_back())
        self.back.bind("<Enter>", lambda e: self.back.config(fg="#ff5555"))
        self.back.bind("<Leave>", lambda e: self.back.config(fg="#ff79c6"))

        self.hide_btn = self._action_label(action_row, "[HIDE]", "#ff5555")
        self.rerate_btn = self._action_label(action_row, "[RERATE]", "#ffd96b")
        self.open_btn = self._action_label(action_row, "[OPEN]", "#50fa7b")
        self.open_btn.bind("<Button-1>", lambda e: self.item and self.on_open(self.item))
        self.rerate_btn.bind("<Button-1>", lambda e: self.item and self.on_rerate(self.item))
        self.hide_btn.bind("<Button-1>", lambda e: self.item and self.on_hide(self.item))

        self.content = tk.Text(
            self.frame,
            font=("Consolas", 11),
            fg="#f8f8f2",
            bg="#0a0a0a",
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=15,
            pady=10,
            cursor="arrow"
        )
        self.content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.content.config(state=tk.DISABLED)

    def _action_label(self, parent, text, color):
        label = tk.Label(
            parent,
            text=text,
            font=("Consolas", 10),
            fg=color,
            bg="#0a0a0a",
            cursor="hand2",
            padx=8,
        )
        label.pack(side=tk.RIGHT)
        return label

    def show(self, item):
        """Display analysis for an item."""
        self.item = item
        self.content.config(state=tk.NORMAL)
        self.content.delete(1.0, tk.END)

        self.content.insert(tk.END, f"{item['title']}\n", "title")
        stars = "*" * item.get('stars', 0) + "." * (5 - item.get('stars', 0))
        read_state = "read" if item.get('read') else "unread"
        meta = f"{item.get('source', 'UNK')} | {stars} | {read_state} | {item.get('published', '')}"
        self.content.insert(tk.END, f"{meta}\n", "meta")
        self.content.insert(tk.END, f"{'-'*50}\n\n", "sep")

        try:
            analysis = json.loads(item.get('analysis', '{}'))
        except:
            analysis = {}

        sections = [
            ("FIRST IMPRESSIONS", analysis.get('first_impressions', 'No analysis available')),
            ("IMPLICATIONS", analysis.get('implications', '')),
            ("ACTION ITEMS", analysis.get('action_items', 'None')),
            ("TL;DR", analysis.get('tldr', '')),
        ]

        for header, content in sections:
            if content:
                self.content.insert(tk.END, f"{header}:\n", "header")
                self.content.insert(tk.END, f"{content}\n\n", "body")

        summary = (item.get('summary') or '').strip()
        body = (item.get('body') or '').strip()
        if summary:
            self.content.insert(tk.END, "SUMMARY:\n", "header")
            self.content.insert(tk.END, f"{summary}\n\n", "body")
        if body:
            snippet = body[:1200].rsplit(" ", 1)[0]
            if len(body) > len(snippet):
                snippet += "..."
            self.content.insert(tk.END, "BODY SNIPPET:\n", "header")
            self.content.insert(tk.END, f"{snippet}\n\n", "body")

        self.content.insert(tk.END, f"\n{'-'*50}\n", "sep")
        self.content.insert(tk.END, f"URL: {item['url']}\n", "link")

        self.content.tag_config("title", font=("Consolas", 14, "bold"), foreground="#50fa7b")
        self.content.tag_config("meta", foreground="#606060")
        self.content.tag_config("sep", foreground="#404040")
        self.content.tag_config("header", font=("Consolas", 11, "bold"), foreground="#ff79c6")
        self.content.tag_config("body", foreground="#f8f8f2")
        self.content.tag_config("link", foreground="#8be9fd")

        self.content.config(state=tk.DISABLED)


class ClaudeNewsUI:
    """Main UI window"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Claude News")
        self.root.geometry("700x500")
        self.root.configure(bg='#0a0a0a')

        # Remove window decorations for clean look (optional)
        # self.root.overrideredirect(True)

        # Make window stay behind others (Windows)
        self.root.attributes('-alpha', 0.95)  # slight transparency

        # Main container
        self.container = tk.Frame(self.root, bg='#0a0a0a')
        self.container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Header
        header = tk.Frame(self.container, bg='#0a0a0a')
        header.pack(fill=tk.X, pady=5)

        title = tk.Label(
            header,
            text="CLAUDE NEWS FEED",
            font=("Consolas", 12, "bold"),
            fg="#bd93f9",
            bg="#0a0a0a"
        )
        title.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(
            header,
            text="",
            font=("Consolas", 9),
            fg="#606060",
            bg="#0a0a0a"
        )
        self.status_label.pack(side=tk.LEFT, padx=4)

        # Refresh button
        self.refresh_btn = tk.Label(
            header,
            text="[↻ REFRESH]",
            font=("Consolas", 10),
            fg="#50fa7b",
            bg="#0a0a0a",
            cursor="hand2"
        )
        self.refresh_btn.pack(side=tk.RIGHT, padx=10)
        self.refresh_btn.bind("<Button-1>", lambda e: self.refresh())

        # Notes/interests button
        self.notes_btn = tk.Label(
            header,
            text="[ NOTES ]",
            font=("Consolas", 10),
            fg="#bd93f9",
            bg="#0a0a0a",
            cursor="hand2"
        )
        self.notes_btn.pack(side=tk.RIGHT, padx=5)
        self.notes_btn.bind("<Button-1>", lambda e: self.open_notes())

        self.vibe_btn = tk.Label(
            header,
            text="[ VIBE ]",
            font=("Consolas", 10),
            fg="#8be9fd",
            bg="#0a0a0a",
            cursor="hand2"
        )
        self.vibe_btn.pack(side=tk.RIGHT, padx=5)
        self.vibe_btn.bind("<Button-1>", lambda e: self.open_vibe())

        # Star filter
        self.filter = StarFilter(self.container, self.on_filter_change)
        self.filter.frame.pack(fill=tk.X, pady=5, padx=10)

        self.source_filter = SourceFilter(
            self.container,
            sorted(CONFIG.enabled_sources),
            self.on_source_filter_change,
        )
        self.source_filter.frame.pack(fill=tk.X, pady=(0, 5), padx=10)

        mode_row = tk.Frame(self.container, bg="#0a0a0a")
        mode_row.pack(fill=tk.X, pady=(0, 5), padx=10)

        tk.Label(
            mode_row,
            text="SEARCH",
            font=("Consolas", 9),
            fg="#606060",
            bg="#0a0a0a",
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            mode_row,
            textvariable=self.search_var,
            font=("Consolas", 10),
            fg="#f8f8f2",
            bg="#1a1a1a",
            insertbackground="#f8f8f2",
            relief=tk.FLAT,
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.search_entry.bind("<KeyRelease>", self.on_search_change)

        self.priority_only = False
        self.unread_only = False
        self.priority_btn = tk.Label(
            mode_row,
            text="[PRIORITY]",
            font=("Consolas", 10),
            fg="#606060",
            bg="#0a0a0a",
            cursor="hand2",
            padx=6,
        )
        self.unread_btn = tk.Label(
            mode_row,
            text="[UNREAD]",
            font=("Consolas", 10),
            fg="#606060",
            bg="#0a0a0a",
            cursor="hand2",
            padx=6,
        )
        self.mark_read_btn = tk.Label(
            mode_row,
            text="[MARK READ]",
            font=("Consolas", 10),
            fg="#8be9fd",
            bg="#0a0a0a",
            cursor="hand2",
            padx=6,
        )
        self.priority_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.unread_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.mark_read_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.priority_btn.bind("<Button-1>", lambda e: self.toggle_priority())
        self.unread_btn.bind("<Button-1>", lambda e: self.toggle_unread())
        self.mark_read_btn.bind("<Button-1>", lambda e: self.mark_current_filter_read())

        # Separator
        tk.Frame(self.container, bg='#404040', height=1).pack(fill=tk.X, pady=5)

        # Feed view
        self.feed_frame = tk.Frame(self.container, bg='#0a0a0a')
        self.feed_frame.pack(fill=tk.BOTH, expand=True)

        # Analysis view (hidden initially)
        self.analysis_view = ActionAnalysisView(
            self.container,
            self.show_feed,
            self.open_item,
            self.rerate_item,
            self.hide_item,
        )

        # Items list
        self.item_widgets = []
        self.empty_label = None

        # Refresh state
        self.refreshing = False
        self.search_after_id = None

        # Load feed
        self.current_filter = []
        self.current_sources = self.source_filter.get_active_sources()
        self.update_mode_buttons()
        self.load_feed()

    def load_feed(self):
        """Load items from database"""
        from database import get_connection, get_items, get_stats

        conn = get_connection(CONFIG.db_path)
        min_stars = 4 if self.priority_only else 0
        items = get_items(
            conn,
            min_stars=min_stars,
            limit=100,
            include_unrated=not self.priority_only,
            sources=sorted(self.current_sources),
            query=self.search_var.get().strip(),
            unread_only=self.unread_only,
        )
        stats = get_stats(conn)
        conn.close()

        self.update_status(stats)
        self.display_items(items)

    def update_status(self, stats):
        """Update the compact feed health/status readout."""
        total = stats.get("total", 0)
        priority = stats.get("high_priority", 0)
        unrated = stats.get("unrated", 0)
        text = f"{total} items | {priority} priority"
        if unrated:
            text += f" | {unrated} unrated"
        if stats.get("unread"):
            text += f" | {stats['unread']} unread"
        self.status_label.config(text=text)

    def display_items(self, items):
        """Display items in feed"""
        # Clear existing
        for widget in self.item_widgets:
            widget.frame.destroy()
        self.item_widgets = []
        if self.empty_label:
            self.empty_label.destroy()
            self.empty_label = None

        # Filter by stars if filter active
        if self.current_filter:
            items = [i for i in items if i.get('stars', 0) in self.current_filter]
        if self.current_sources:
            items = [i for i in items if i.get('source') in self.current_sources]

        # Create widgets
        for item in items[:30]:
            widget = NewsItemWidget(self.feed_frame, item, self.show_analysis, self.mark_item_read)
            widget.frame.pack(fill=tk.X, pady=1)
            self.item_widgets.append(widget)

        if not items:
            self.empty_label = tk.Label(
                self.feed_frame,
                text="No items match filter. Try refreshing or changing filters.",
                font=("Consolas", 10),
                fg="#606060",
                bg="#0a0a0a"
            )
            self.empty_label.pack(pady=20)

    def on_filter_change(self, active_stars):
        """Handle filter change"""
        self.current_filter = active_stars
        self.load_feed()

    def on_source_filter_change(self, active_sources):
        """Handle source filter change"""
        self.current_sources = active_sources
        self.load_feed()

    def on_search_change(self, _event=None):
        """Debounce local search slightly so typing stays smooth."""
        if self.search_after_id:
            self.root.after_cancel(self.search_after_id)
        self.search_after_id = self.root.after(180, self.load_feed)

    def toggle_priority(self):
        self.priority_only = not self.priority_only
        self.update_mode_buttons()
        self.load_feed()

    def toggle_unread(self):
        self.unread_only = not self.unread_only
        self.update_mode_buttons()
        self.load_feed()

    def update_mode_buttons(self):
        self.priority_btn.config(fg="#ffd96b" if self.priority_only else "#606060")
        self.unread_btn.config(fg="#50fa7b" if self.unread_only else "#606060")

    def mark_item_read(self, item):
        from database import get_connection, get_stats, mark_read

        conn = get_connection(CONFIG.db_path)
        mark_read(conn, item['content_hash'])
        stats = get_stats(conn)
        conn.close()
        self.update_status(stats)
        if self.unread_only:
            self.load_feed()

    def mark_current_filter_read(self):
        from feed import ClaudeNewsFeed

        min_stars = 4 if self.priority_only else 0
        feed = ClaudeNewsFeed()
        changed = feed.mark_filtered_read(
            min_stars=min_stars,
            sources=sorted(self.current_sources),
            query=self.search_var.get().strip(),
            priority_only=self.priority_only,
        )
        self.status_label.config(text=f"marked {changed} read")
        self.load_feed()

    def open_item(self, item):
        webbrowser.open(item['url'])
        item['read'] = 1
        self.mark_item_read(item)
        self.analysis_view.show(item)

    def rerate_item(self, item):
        self.analysis_view.rerate_btn.config(text="[RATING...]", fg="#ffd96b")

        def worker():
            try:
                from feed import ClaudeNewsFeed
                from database import get_item_by_hash

                feed = ClaudeNewsFeed()
                result = feed.rerate([item], delay=0)
                updated = get_item_by_hash(feed.conn, item['content_hash'])
                self.root.after(0, lambda: self._rerate_done(result, updated or item))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._rerate_failed(err))

        threading.Thread(target=worker, daemon=True).start()

    def _rerate_done(self, result, item):
        self.analysis_view.rerate_btn.config(text="[RERATE]", fg="#ffd96b")
        self.analysis_view.show(item)
        self.load_feed()

    def _rerate_failed(self, err):
        print(f"Rerate failed: {err}")
        self.analysis_view.rerate_btn.config(text="[RERATE ERR]", fg="#ff5555")
        self.root.after(5000, lambda: self.analysis_view.rerate_btn.config(
            text="[RERATE]", fg="#ffd96b"
        ))

    def hide_item(self, item):
        from database import get_connection, get_stats, hide_item

        conn = get_connection(CONFIG.db_path)
        hide_item(conn, item['content_hash'])
        stats = get_stats(conn)
        conn.close()
        self.update_status(stats)
        self.show_feed()
        self.load_feed()

    def show_analysis(self, item):
        """Show analysis view for an item"""
        item['read'] = 1
        self.mark_item_read(item)
        self.feed_frame.pack_forget()
        self.analysis_view.frame.pack(fill=tk.BOTH, expand=True)
        self.analysis_view.show(item)

    def show_feed(self):
        """Return to feed view"""
        self.analysis_view.frame.pack_forget()
        self.feed_frame.pack(fill=tk.BOTH, expand=True)

    def refresh(self):
        """Refresh feed from sources in a background thread (UI stays responsive)."""
        if self.refreshing:
            return
        self.refreshing = True
        self.refresh_btn.config(text="[...LOADING...]", fg="#ffd93d")

        def worker():
            try:
                from feed import ClaudeNewsFeed
                # Connection lives entirely in this thread — safe.
                feed = ClaudeNewsFeed(enabled_sources=self.current_sources)
                result = feed.refresh(rate_new=True)
                self.root.after(0, lambda: self._refresh_done(result))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._refresh_failed(err))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_done(self, result):
        added = result.get('added', 0)
        rated = result.get('rated', 0)
        failed = result.get('rating_failed', 0)
        label = f"[↻ +{added} ★{rated}"
        if failed:
            label += f" !{failed}"
        label += "]"
        self.refresh_btn.config(text=label, fg="#50fa7b")
        self.load_feed()
        self.refreshing = False
        self.root.after(5000, lambda: self.refresh_btn.config(text="[↻ REFRESH]", fg="#50fa7b"))

    def _refresh_failed(self, err):
        print(f"Refresh failed: {err}")
        self.refresh_btn.config(text="[↻ ERROR]", fg="#ff5555")
        self.refreshing = False
        self.root.after(5000, lambda: self.refresh_btn.config(text="[↻ REFRESH]", fg="#50fa7b"))

    def open_notes(self):
        """Edit the free-text interest notes that get injected into the rater prompt."""
        from feed import load_interests, save_interests

        win = tk.Toplevel(self.root)
        win.title("Interest Notes")
        win.geometry("520x340")
        win.configure(bg="#0a0a0a")
        win.transient(self.root)

        tk.Label(
            win,
            text="What are you especially interested in?",
            font=("Consolas", 11, "bold"),
            fg="#bd93f9", bg="#0a0a0a",
        ).pack(anchor="w", padx=12, pady=(12, 2))

        tk.Label(
            win,
            text="(injected into the rater prompt; keep it short)",
            font=("Consolas", 9),
            fg="#606060", bg="#0a0a0a",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        text = tk.Text(
            win,
            font=("Consolas", 10),
            fg="#f8f8f2", bg="#1a1a1a",
            insertbackground="#f8f8f2",
            relief=tk.FLAT, wrap=tk.WORD,
            padx=8, pady=6,
            height=10,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        text.insert("1.0", load_interests())
        text.focus_set()

        btn_row = tk.Frame(win, bg="#0a0a0a")
        btn_row.pack(fill=tk.X, padx=12, pady=8)

        status = tk.Label(btn_row, text="", font=("Consolas", 9),
                          fg="#50fa7b", bg="#0a0a0a")
        status.pack(side=tk.LEFT)

        def do_save():
            save_interests(text.get("1.0", tk.END))
            status.config(text="saved — applies on next refresh")

        def do_close():
            win.destroy()

        close_btn = tk.Label(btn_row, text="[ CLOSE ]", font=("Consolas", 10),
                             fg="#ff5555", bg="#0a0a0a", cursor="hand2")
        save_btn = tk.Label(btn_row, text="[ SAVE ]", font=("Consolas", 10),
                            fg="#50fa7b", bg="#0a0a0a", cursor="hand2")
        save_btn.pack(side=tk.RIGHT, padx=4)
        close_btn.pack(side=tk.RIGHT, padx=4)
        save_btn.bind("<Button-1>", lambda e: do_save())
        close_btn.bind("<Button-1>", lambda e: do_close())

    def open_vibe(self):
        """Open a compact daily/weekly vibe report window."""
        from digest import format_report, latest_report

        win = tk.Toplevel(self.root)
        win.title("Vibe Report")
        win.geometry("720x560")
        win.configure(bg="#0a0a0a")
        win.transient(self.root)

        top = tk.Frame(win, bg="#0a0a0a")
        top.pack(fill=tk.X, padx=12, pady=10)

        tk.Label(
            top,
            text="VIBE REPORT",
            font=("Consolas", 12, "bold"),
            fg="#8be9fd",
            bg="#0a0a0a",
        ).pack(side=tk.LEFT)

        text = tk.Text(
            win,
            font=("Consolas", 10),
            fg="#f8f8f2",
            bg="#111111",
            insertbackground="#f8f8f2",
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=8,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        def set_report(body):
            text.config(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            text.insert("1.0", body)
            text.config(state=tk.DISABLED)

        latest = latest_report()
        if latest:
            set_report(format_report(latest))
        else:
            set_report("No saved vibe reports yet. Generate a daily or weekly report.")

        actions = tk.Frame(win, bg="#0a0a0a")
        actions.pack(fill=tk.X, padx=12, pady=(0, 10))

        status = tk.Label(actions, text="", font=("Consolas", 9),
                          fg="#606060", bg="#0a0a0a")
        status.pack(side=tk.LEFT)

        def generate(days=1, recent=False):
            status.config(text="generating...")
            set_report("Generating vibe report...")

            def worker():
                try:
                    from digest import VibeDigest, format_report
                    result = VibeDigest().generate(
                        days=days,
                        limit=80,
                        save=True,
                        recent=recent,
                    )
                    body = format_report(result)
                    self.root.after(0, lambda: set_report(body))
                    self.root.after(0, lambda: status.config(
                        text=f"saved #{result.get('id')} from {result.get('item_count', 0)} items"
                    ))
                except Exception as e:
                    err = str(e)
                    self.root.after(0, lambda: set_report(f"Vibe generation failed:\n{err}"))
                    self.root.after(0, lambda: status.config(text="error"))

            threading.Thread(target=worker, daemon=True).start()

        def show_history():
            from digest import format_history, report_history
            set_report(format_history(report_history(limit=12)))
            status.config(text="history")

        def show_delta():
            from digest import format_delta, report_delta
            set_report(format_delta(report_delta()))
            status.config(text="delta")

        daily_btn = tk.Label(actions, text="[DAILY]", font=("Consolas", 10),
                             fg="#50fa7b", bg="#0a0a0a", cursor="hand2")
        weekly_btn = tk.Label(actions, text="[WEEKLY]", font=("Consolas", 10),
                              fg="#ffd96b", bg="#0a0a0a", cursor="hand2")
        recent_btn = tk.Label(actions, text="[RECENT]", font=("Consolas", 10),
                              fg="#8be9fd", bg="#0a0a0a", cursor="hand2")
        history_btn = tk.Label(actions, text="[HISTORY]", font=("Consolas", 10),
                               fg="#bd93f9", bg="#0a0a0a", cursor="hand2")
        delta_btn = tk.Label(actions, text="[DELTA]", font=("Consolas", 10),
                             fg="#ff79c6", bg="#0a0a0a", cursor="hand2")
        close_btn = tk.Label(actions, text="[CLOSE]", font=("Consolas", 10),
                             fg="#ff5555", bg="#0a0a0a", cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=4)
        delta_btn.pack(side=tk.RIGHT, padx=4)
        history_btn.pack(side=tk.RIGHT, padx=4)
        weekly_btn.pack(side=tk.RIGHT, padx=4)
        daily_btn.pack(side=tk.RIGHT, padx=4)
        recent_btn.pack(side=tk.RIGHT, padx=4)
        daily_btn.bind("<Button-1>", lambda e: generate(days=1))
        weekly_btn.bind("<Button-1>", lambda e: generate(days=7))
        recent_btn.bind("<Button-1>", lambda e: generate(recent=True))
        history_btn.bind("<Button-1>", lambda e: show_history())
        delta_btn.bind("<Button-1>", lambda e: show_delta())
        close_btn.bind("<Button-1>", lambda e: win.destroy())

    def set_always_behind(self):
        """Set window to always stay behind others (Windows only)"""
        if windll:
            hwnd = windll.user32.GetForegroundWindow()
            # This is tricky - needs more work for true always-behind behavior

    def start_auto_refresh(self, interval_ms: int = 3600000):
        """Start auto-refresh timer (default: 1 hour)"""
        def do_refresh():
            print("[Auto-refresh] Checking for new items...")
            self.refresh()
            self.root.after(interval_ms, do_refresh)

        # First refresh after interval
        self.root.after(interval_ms, do_refresh)
        print(f"[Auto-refresh] Enabled - every {interval_ms // 60000} minutes")

    def run(self):
        """Start the UI"""
        self.start_auto_refresh(CONFIG.auto_refresh_minutes * 60000)
        self.root.mainloop()


def main():
    app = ClaudeNewsUI()
    app.run()


if __name__ == "__main__":
    main()
