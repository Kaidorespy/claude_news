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


class NewsItemWidget:
    """Single news item row"""

    def __init__(self, parent, item, on_click):
        self.item = item
        self.frame = tk.Frame(parent, bg='#0a0a0a')

        # Source
        source_colors = {
            'ANTH': '#ff79c6',  # pink - official
            'RDIT': '#ff5555',  # red - reddit
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
            fg="#f8f8f2",
            bg="#0a0a0a",
            cursor="hand2",
            anchor="w",
            justify="left",
            wraplength=550
        )
        self.title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.title.bind("<Button-1>", lambda e: webbrowser.open(item['url']))
        self.title.bind("<Enter>", lambda e: self.title.config(fg="#8be9fd"))
        self.title.bind("<Leave>", lambda e: self.title.config(fg="#f8f8f2"))

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

        # Star filter
        self.filter = StarFilter(self.container, self.on_filter_change)
        self.filter.frame.pack(fill=tk.X, pady=5, padx=10)

        # Separator
        tk.Frame(self.container, bg='#404040', height=1).pack(fill=tk.X, pady=5)

        # Feed view
        self.feed_frame = tk.Frame(self.container, bg='#0a0a0a')
        self.feed_frame.pack(fill=tk.BOTH, expand=True)

        # Analysis view (hidden initially)
        self.analysis_view = AnalysisView(self.container, self.show_feed)

        # Items list
        self.item_widgets = []
        self.empty_label = None

        # Refresh state
        self.refreshing = False

        # Load feed
        self.current_filter = []
        self.load_feed()

    def load_feed(self):
        """Load items from database"""
        from database import get_connection, get_items, get_stats

        conn = get_connection()
        items = get_items(conn, min_stars=0, limit=30)
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

        # Create widgets
        for item in items:
            widget = NewsItemWidget(self.feed_frame, item, self.show_analysis)
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

    def show_analysis(self, item):
        """Show analysis view for an item"""
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
                feed = ClaudeNewsFeed()
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
        self.start_auto_refresh()  # auto-refresh every hour
        self.root.mainloop()


def main():
    app = ClaudeNewsUI()
    app.run()


if __name__ == "__main__":
    main()
