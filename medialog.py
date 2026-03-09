#!/usr/bin/env python3
"""
MediaLog – keyboard-driven media consumption tracker.

Dependencies:  pip install rich
Run:           python media_log.py
Import CSV:    python media_log.py --import-csv /path/to/media.csv

Navigation
──────────
List view   j/k ↑↓  move      Enter/Space  open detail    g/G  top/bottom
            /        search    t/T          cycle type filter (fwd/back)
            r        reset     a  add       l  log selected
            d        delete    i  import CSV
            q        quit

Detail view  l  log   e  edit   d  delete   j/k ↑↓  scroll sessions
             q / Esc  back
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import os
import shutil
import sqlite3
import sys
if os.name != "nt":
    import select
    import termios
    import tty
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

# ─── Constants ────────────────────────────────────────────────────────────────

DB_PATH = Path(r"C:\Users\rodri\Desktop\python_scripts\medialog\.media_log\media.db")
console = Console(force_terminal=True, highlight=False)

MEDIA_TYPES = [
    "Anime", "Book", "Game", "Manga", "Movie",
    "Music", "Podcast", "Song", "TV Series",
]

TYPE_HINTS: dict[str, str] = {
    "Anime":     "e.g. 2 episodes",
    "Book":      "e.g. 10 pages / ch. 5–8",
    "Manga":     "e.g. 3 chapters",
    "Movie":     "Watched",
    "Music":     "Played",
    "TV Series": "e.g. 1 episode / S02E04",
    "Song":      "Played",
    "Game":      "e.g. 2 hours",
    "Podcast":   "e.g. 1 episode",
}

TYPE_STYLES: dict[str, str] = {
    "Anime":     "cyan",
    "Book":      "green",
    "Game":      "magenta",
    "Manga":     "yellow",
    "Movie":     "blue",
    "Music":     "red",
    "Podcast":   "bright_blue",
    "Song":      "bright_red",
    "TV Series": "bright_cyan",
}

_last_type: str = "Movie"  # remembered across add-media calls


_VT_HOME = "\033[H"    # move cursor to top-left (no erase)
_VT_EOSC = "\033[J"    # erase from cursor to end of screen
_VT_HIDC = "\033[?25l" # hide cursor
_VT_SHWC = "\033[?25h" # show cursor


def _enable_vt() -> None:
    """Enable VT100/ANSI processing on Windows 10+. No-op elsewhere."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 0x0007
            )
        except Exception:
            pass


@contextlib.contextmanager
def _frame():
    """Render into a StringIO buffer, then blit atomically.

    Replaces the console.clear() → draw cycle with:
        cursor-home → overwrite new frame → erase tail
    The screen is never blank, eliminating flicker entirely.
    """
    cols = shutil.get_terminal_size().columns
    buf  = io.StringIO()
    old_file  = console._file
    old_width = console._width
    console._file  = buf
    console._width = cols
    try:
        yield
    finally:
        console._file  = old_file
        console._width = old_width
    # Insert \033[K (erase to end of line) before every \n so stale content
    # on longer previous-frame lines is cleared, not just content past the
    # last character of the new frame.
    output = buf.getvalue().replace("\n", "\033[K\n")
    sys.stdout.write(_VT_HOME + output + _VT_EOSC)
    sys.stdout.flush()




@contextlib.contextmanager
def get_db():
    """Yield a connection that is committed (or rolled back) and closed on exit."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                type         TEXT    NOT NULL,
                title        TEXT    NOT NULL,
                rating       REAL,
                genres       TEXT,
                release_date TEXT,
                thumbnail    TEXT,
                creators     TEXT,
                length       TEXT,
                progress     TEXT,
                count        INTEGER NOT NULL DEFAULT 1,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id   INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
                logged_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                quantity   TEXT,
                note       TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_type   ON media(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_title  ON media(title COLLATE NOCASE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_mid ON sessions(media_id)")


def import_csv(path: str) -> tuple[int, int]:
    """Import from CSV. Returns (imported, skipped)."""
    imported = skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        with get_db() as conn:
            for row in reader:
                raw_type  = (row.get("Types") or "").strip()
                raw_title = (row.get("Title") or "").strip()
                if not raw_title:
                    skipped += 1
                    continue
                dup = conn.execute(
                    "SELECT 1 FROM media"
                    "  WHERE title = ? COLLATE NOCASE"
                    "    AND type  = ? COLLATE NOCASE",
                    (raw_title, raw_type),
                ).fetchone()
                if dup:
                    skipped += 1
                    continue
                try:
                    rating_s = (row.get("My_rating") or "").strip()
                    rating   = float(rating_s) if rating_s else None
                    count_s  = (row.get("Count") or "1").strip()
                    count    = int(float(count_s)) if count_s else 1
                except (ValueError, TypeError):
                    rating = None
                    count  = 1
                conn.execute(
                    """INSERT INTO media
                         (type, title, rating, genres, release_date,
                          thumbnail, creators, length, progress, count)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        raw_type, raw_title, rating,
                        (row.get("Genres")       or "").strip() or None,
                        (row.get("Release_date") or "").strip() or None,
                        (row.get("Thumbnail")    or "").strip() or None,
                        (row.get("Creators")     or "").strip() or None,
                        (row.get("Length")       or "").strip() or None,
                        (row.get("Progress")     or "").strip() or None,
                        count,
                    ),
                )
                imported += 1
    return imported, skipped


# ─── Terminal input ────────────────────────────────────────────────────────────

def getch() -> str:
    """Read one keypress.
    Arrow keys → 'UP' / 'DOWN' / 'LEFT' / 'RIGHT'.
    Escape alone → 'ESC'.  Ctrl+C → '\\x03'.
    """
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\xe0", b"\x00"):
            ch2 = msvcrt.getch()
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(
                ch2.decode("ascii", errors="ignore"), "?"
            )
        return ch.decode("utf-8", errors="ignore")

    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r2:
                        ch3 = sys.stdin.read(1)
                        return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(ch3, "ESC")
            return "ESC"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def term_height() -> int:
    return shutil.get_terminal_size().lines


def wait_key(msg: str = "  Press any key to continue…") -> None:
    console.print(f"\n[dim]{msg}[/dim]")
    key = getch()
    if key == "\x03":
        raise KeyboardInterrupt


# ─── Forms ────────────────────────────────────────────────────────────────────
# getch() restores the terminal to cooked mode in its finally-block, so
# Prompt.ask is always called with the terminal in a normal (non-raw) state.

def _ask(label: str, default: str = "", hint: str = "") -> str:
    hint_part = f" [dim]({hint})[/dim]" if hint else ""
    return Prompt.ask(
        f"  [bold]{label}[/bold]{hint_part}",
        default=default,
        console=console,
    ).strip()


def _pick_type(current: str = "Movie") -> str:
    """Numbered menu printed once; returns the selected type string."""
    console.print("\n  [bold]Type[/bold]")
    for i, t in enumerate(MEDIA_TYPES, 1):
        s      = TYPE_STYLES.get(t, "white")
        marker = "[bold]▶[/bold]" if t == current else " "
        console.print(f"  {marker} [{s}]{i:2}. {t}[/{s}]")
    while True:
        raw = _ask("Type", hint="1–9 or name prefix")
        if not raw:
            return current
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(MEDIA_TYPES):
                return MEDIA_TYPES[idx]
        matches = [t for t in MEDIA_TYPES if t.lower().startswith(raw.lower())]
        if matches:
            return matches[0]
        # Invalid — show error inline, re-prompt without re-printing the menu
        console.print("  [red]Invalid — enter 1–9 or a name prefix (e.g. 'tv', 'bo').[/red]")


def form_add_edit(media_id: Optional[int] = None) -> bool:
    """Sequential prompts to add or edit a media item. Returns True on save."""
    item = None
    if media_id is not None:
        with get_db() as conn:
            item = conn.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()

    def v(col: str, default: str = "") -> str:
        return str(item[col]) if item and item[col] is not None else default

    console.clear()
    heading = "Edit Media" if item else "Add Media"
    console.print(Panel(f"[bold]{heading}[/bold]", expand=False))
    console.print("  [dim]Enter to keep current value.  Ctrl+C to cancel.[/dim]")

    try:
        global _last_type
        media_type = _pick_type(v("type", _last_type))
        if not item:                       # only update the memory for new entries
            _last_type = media_type
        title      = ""
        while not title:
            title = _ask("Title [red]*[/red]", default=v("title"))
            if not title:
                console.print("  [red]Title is required.[/red]")
        rating_s = _ask("Rating", default=v("rating"), hint="0–10, blank = unrated")
        try:
            rating: Optional[float] = float(rating_s) if rating_s else None
        except ValueError:
            rating = None
        creators  = _ask("Creators / Author / Director", default=v("creators"))  or None
        genres    = _ask("Genres",          default=v("genres"))                 or None
        release   = _ask("Release Date",    default=v("release_date"),
                         hint="2024 or 2024-03-01")                              or None
        length    = _ask("Length",          default=v("length"),
                         hint="166 mins / 300 pages")                            or None
        progress  = _ask("Progress / Status", default=v("progress"),
                         hint="Watched / On-Hold : 82 chs")                      or None
        thumbnail = _ask("Thumbnail URL",   default=v("thumbnail"))              or None
    except KeyboardInterrupt:
        console.print("\n  [yellow]Cancelled.[/yellow]")
        return False

    with get_db() as conn:
        if media_id is not None:
            conn.execute(
                """UPDATE media SET
                     type=?,title=?,rating=?,creators=?,genres=?,
                     release_date=?,length=?,progress=?,thumbnail=?,
                     updated_at=datetime('now')
                   WHERE id=?""",
                (media_type, title, rating, creators, genres,
                 release, length, progress, thumbnail, media_id),
            )
        else:
            conn.execute(
                """INSERT INTO media
                     (type,title,rating,creators,genres,
                      release_date,length,progress,thumbnail)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (media_type, title, rating, creators, genres,
                 release, length, progress, thumbnail),
            )
    console.print("  [green]✓ Saved.[/green]")
    wait_key()
    return True


def form_log_session(media_id: int, title: str, media_type: str) -> bool:
    """Sequential prompts to log a consumption session. Returns True on success."""
    console.clear()
    hint = TYPE_HINTS.get(media_type, "quantity / unit")
    console.print(Panel(f"[bold]Log Session[/bold]  ›  {escape(title)}", expand=False))
    console.print("  [dim]All fields optional.  Ctrl+C to cancel.[/dim]\n")
    try:
        qty  = _ask("Quantity", hint=hint)                                            or None
        note = _ask("Note",     hint="free-form")                                     or None
        dt_s = _ask("Date", default=date.today().isoformat(), hint="blank = now")
        try:
            logged_at = datetime.fromisoformat(dt_s).isoformat() if dt_s else datetime.now().isoformat()
        except ValueError:
            logged_at = datetime.now().isoformat()
    except KeyboardInterrupt:
        console.print("\n  [yellow]Cancelled.[/yellow]")
        return False

    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (media_id, logged_at, quantity, note) VALUES (?,?,?,?)",
            (media_id, logged_at, qty, note),
        )
        conn.execute(
            "UPDATE media SET count=count+1, updated_at=datetime('now') WHERE id=?",
            (media_id,),
        )
    console.print("  [green]✓ Logged.[/green]")
    wait_key()
    return True


# ─── List view ────────────────────────────────────────────────────────────────

_HELP_LIST = (
    "[bold]j/k ↑↓[/bold] move  "
    "[bold]←/→[/bold] page  "
    "[bold]Enter[/bold] open  "
    "[bold]g/G[/bold] top/btm  "
    "[bold]/[/bold] search  "
    "[bold]s/S[/bold] sort  "
    "[bold]t/T[/bold] type  "
    "[bold]r[/bold] reset  "
    "[bold]a[/bold] add  "
    "[bold]l[/bold] log  "
    "[bold]d[/bold] del  "
    "[bold]i[/bold] import  "
    "[bold]q[/bold] quit"
)

# Cycle ends on None (= all types); pressing t from there wraps to first type.
_TYPE_CYCLE = MEDIA_TYPES + [None]

# Each entry: (display label, ORDER BY clause)
# rating sorts push NULLs last via CASE to stay compatible with SQLite < 3.30
_SORTS: list[tuple[str, str]] = [
    ("recent",    "updated_at DESC"),
    ("title A→Z", "title COLLATE NOCASE ASC"),
    ("title Z→A", "title COLLATE NOCASE DESC"),
    ("rating ↓",  "CASE WHEN rating IS NULL THEN 1 ELSE 0 END, rating DESC"),
    ("rating ↑",  "CASE WHEN rating IS NULL THEN 1 ELSE 0 END, rating ASC"),
    ("logged ↓",  "count DESC"),
    ("type",      "type COLLATE NOCASE ASC, title COLLATE NOCASE ASC"),
]


def _fetch(search: str, type_filter: Optional[str], sort_order: str = _SORTS[0][1]) -> list:
    sql  = "SELECT * FROM media WHERE 1=1"
    args: list = []
    if type_filter:
        sql += " AND type=?"
        args.append(type_filter)
    if search:
        sql += " AND (title LIKE ? OR creators LIKE ? OR genres LIKE ?)"
        args += [f"%{search}%"] * 3
    sql += f" ORDER BY {sort_order}"
    with get_db() as conn:
        return conn.execute(sql, args).fetchall()


def _render_list(items: list, cursor: int, scroll: int,
                 search: str, type_filter: Optional[str],
                 sort_label: str = _SORTS[0][0]) -> None:
    height  = term_height()
    visible = max(3, height - 6)

    # Header
    filter_parts = []
    if type_filter:
        s = TYPE_STYLES.get(type_filter, "white")
        filter_parts.append(f"type:[{s}]{type_filter}[/{s}]")
    if search:
        filter_parts.append(f"search:[yellow]{escape(search)}[/yellow]")
    filter_parts.append(f"sort:[cyan]{escape(sort_label)}[/cyan]")
    fstr = "  ".join(filter_parts)
    console.print(f" [bold cyan]MediaLog[/bold cyan]   {fstr}   [dim]{len(items)} items[/dim]")
    console.rule()

    if not items:
        console.print(
            "\n  [dim]Nothing here.  "
            "Press [bold]a[/bold] to add or [bold]i[/bold] to import a CSV.[/dim]"
        )
    else:
        # Mark the sorted column header with an arrow
        _sort_col = {
            "title A→Z": "Title", "title Z→A": "Title",
            "rating ↓":  "Rating", "rating ↑": "Rating",
            "logged ↓":  "×",
            "type":      "Type",
        }
        def _col(name: str) -> str:
            return f"{name} [cyan]↕[/cyan]" if _sort_col.get(sort_label) == name else name

        tbl = Table(
            box=box.SIMPLE, show_header=True, header_style="bold dim",
            pad_edge=False, expand=True, show_edge=False,
        )
        tbl.add_column(" ",             width=1,  no_wrap=True)
        tbl.add_column(_col("Type"),    width=10, no_wrap=True)
        tbl.add_column(_col("Title"),   ratio=3,  no_wrap=True, overflow="ellipsis")
        tbl.add_column(_col("Rating"),  width=7,  no_wrap=True)
        tbl.add_column("Progress",      ratio=2,  no_wrap=True, overflow="ellipsis")
        tbl.add_column(_col("×"),       width=4,  no_wrap=True, justify="right")

        for abs_i in range(scroll, min(scroll + visible, len(items))):
            row       = items[abs_i]
            selected  = abs_i == cursor
            ts        = TYPE_STYLES.get(row["type"], "white")
            type_cell = Text(row["type"], style="" if selected else ts)
            rating    = f"★ {row['rating']}" if row["rating"] is not None else "—"
            tbl.add_row(
                "▶" if selected else " ",
                type_cell,
                Text(row["title"]),
                rating,
                Text(row["progress"] or "—"),
                str(row["count"]),
                style="bold reverse" if selected else "",
            )
        console.print(tbl)

    # Footer
    pos = f" [dim]{cursor + 1}/{len(items)}[/dim]  " if items else " "
    console.rule()
    console.print(f"{pos}{_HELP_LIST}")


def list_view() -> None:
    cursor      = 0
    scroll      = 0
    search      = ""
    type_idx    = len(_TYPE_CYCLE) - 1   # last element = None (all types)
    type_filter: Optional[str] = None
    sort_idx    = 0
    items       = _fetch(search, type_filter, _SORTS[sort_idx][1])

    console.clear()                        # one-time full clear on entry
    sys.stdout.write(_VT_HIDC)
    sys.stdout.flush()
    try:
        while True:
            height  = term_height()
            visible = max(3, height - 6)

            # Clamp cursor and keep it inside the scroll window.
            if items:
                cursor = max(0, min(cursor, len(items) - 1))
            else:
                cursor = 0
            scroll = max(0, min(scroll, max(0, len(items) - visible)))
            if cursor < scroll:
                scroll = cursor
            elif cursor >= scroll + visible:
                scroll = cursor - visible + 1

            with _frame():
                _render_list(items, cursor, scroll, search, type_filter, _SORTS[sort_idx][0])
            key = getch()

            if key in ("q", "\x03"):
                break

            elif key in ("ESC", "\x1b") and search:
                search = ""
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0
                scroll = 0

            elif key in ("j", "DOWN"):
                cursor = min(cursor + 1, max(0, len(items) - 1))

            elif key in ("k", "UP"):
                cursor = max(cursor - 1, 0)

            elif key == "RIGHT":
                scroll = min(scroll + visible, max(0, len(items) - visible))
                cursor = scroll

            elif key == "LEFT":
                scroll = max(scroll - visible, 0)
                cursor = scroll

            elif key == "g":
                cursor = 0

            elif key == "G":
                cursor = max(0, len(items) - 1)

            elif key in ("\r", "\n", " ") and items:
                detail_view(items[cursor]["id"])
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = min(cursor, max(0, len(items) - 1))

            elif key == "a":
                form_add_edit()
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0

            elif key == "l" and items:
                row = items[cursor]
                form_log_session(row["id"], row["title"], row["type"])
                items = _fetch(search, type_filter, _SORTS[sort_idx][1])

            elif key == "/":
                console.clear()
                console.print(Panel("[bold]Search[/bold]", expand=False))
                try:
                    search = _ask("Query", hint="blank = clear")
                except KeyboardInterrupt:
                    pass
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0

            elif key == "s":
                sort_idx = (sort_idx + 1) % len(_SORTS)
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0
                scroll = 0

            elif key == "S":
                sort_idx = (sort_idx - 1) % len(_SORTS)
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0
                scroll = 0

            elif key == "t":
                type_idx    = (type_idx + 1) % len(_TYPE_CYCLE)
                type_filter = _TYPE_CYCLE[type_idx]
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0

            elif key == "T":
                type_idx    = (type_idx - 1) % len(_TYPE_CYCLE)
                type_filter = _TYPE_CYCLE[type_idx]
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0

            elif key == "r":
                search      = ""
                type_filter = None
                type_idx    = len(_TYPE_CYCLE) - 1
                sort_idx    = 0
                items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                cursor = 0

            elif key == "d" and items:
                mid   = items[cursor]["id"]
                title = items[cursor]["title"]
                console.clear()
                console.print(Panel(f"[bold red]Delete[/bold red]  {escape(title)}", expand=False))
                try:
                    if Confirm.ask("  Delete this item and all its sessions?", console=console):
                        with get_db() as conn:
                            conn.execute("DELETE FROM media WHERE id=?", (mid,))
                        items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                        cursor = min(cursor, max(0, len(items) - 1))
                except KeyboardInterrupt:
                    pass

            elif key == "i":
                console.clear()
                console.print(Panel("[bold]Import CSV[/bold]", expand=False))
                try:
                    path = _ask("CSV path")
                    if path:
                        ok, skip = import_csv(path)
                        console.print(f"  [green]✓  Imported : {ok}[/green]")
                        console.print(
                            f"  [yellow]⚑  Skipped  : {skip}[/yellow]"
                            f"  (duplicates / parse errors)"
                        )
                        wait_key()
                        items  = _fetch(search, type_filter, _SORTS[sort_idx][1])
                        cursor = 0
                except KeyboardInterrupt:
                    pass

    finally:
        sys.stdout.write(_VT_SHWC)
        sys.stdout.flush()


# ─── Detail view ──────────────────────────────────────────────────────────────

_HELP_DETAIL = (
    "[bold]l[/bold] log  "
    "[bold]e[/bold] edit  "
    "[bold]d[/bold] delete  "
    "[bold]j/k ↑↓[/bold] scroll sessions  "
    "[bold]q / Esc[/bold] back"
)


def _render_detail(item, sessions: list, sess_scroll: int) -> None:
    height    = term_height()
    sess_rows = max(2, height - 16)

    ts     = TYPE_STYLES.get(item["type"], "white")
    rating = f"★ {item['rating']}" if item["rating"] is not None else "unrated"

    info = Text()
    info.append(item["title"], style="bold")
    info.append(f"  [{item['type']}]", style=ts)
    info.append(f"  {rating}\n")
    for col, lbl in [
        ("creators",     "Creators   "),
        ("genres",       "Genres     "),
        ("release_date", "Released   "),
        ("length",       "Length     "),
        ("progress",     "Progress   "),
    ]:
        if item[col]:
            info.append(f"  {lbl}", style="dim")
            info.append(f"{item[col]}\n")
    info.append(f"\n  Logged ", style="dim")
    info.append(f"{item['count']}×")
    info.append("   |   Added ", style="dim")
    info.append(item["created_at"][:10])
    console.print(Panel(info, expand=True))

    console.print(f"  [bold]Sessions[/bold]  [dim]({len(sessions)} total)[/dim]")
    if not sessions:
        console.print("  [dim]No sessions yet.  Press [bold]l[/bold] to log one.[/dim]")
    else:
        tbl = Table(
            box=box.SIMPLE, show_header=True, header_style="bold dim",
            pad_edge=False, expand=True, show_edge=False,
        )
        tbl.add_column("Date / Time", width=17, no_wrap=True)
        tbl.add_column("Quantity",    width=24, no_wrap=True)
        tbl.add_column("Note",        ratio=1,  overflow="ellipsis")
        end = min(sess_scroll + sess_rows, len(sessions))
        for s in sessions[sess_scroll:end]:
            tbl.add_row(
                s["logged_at"][:16],
                Text(s["quantity"] or "—"),
                Text(s["note"] or "—"),
            )
        console.print(tbl)
        if len(sessions) > sess_rows:
            console.print(f"  [dim]{sess_scroll + 1}–{end} of {len(sessions)}[/dim]")

    console.rule()
    console.print(f" {_HELP_DETAIL}")


def detail_view(media_id: int) -> None:
    sess_scroll = 0

    sys.stdout.write(_VT_HIDC)
    sys.stdout.flush()
    try:
        while True:
            with get_db() as conn:
                item     = conn.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
                sessions = conn.execute(
                    "SELECT * FROM sessions WHERE media_id=? ORDER BY logged_at DESC",
                    (media_id,),
                ).fetchall()

            if not item:
                return

            height    = term_height()
            sess_rows = max(2, height - 16)
            sess_scroll = max(0, min(sess_scroll, max(0, len(sessions) - sess_rows)))

            with _frame():
                _render_detail(item, sessions, sess_scroll)
            key = getch()

            if key in ("q", "ESC", "\x1b", "\x03"):
                return

            elif key in ("j", "DOWN"):
                sess_scroll = min(sess_scroll + 1, max(0, len(sessions) - sess_rows))

            elif key in ("k", "UP"):
                sess_scroll = max(0, sess_scroll - 1)

            elif key == "l":
                form_log_session(media_id, item["title"], item["type"])

            elif key == "e":
                form_add_edit(media_id)

            elif key == "d":
                console.clear()
                console.print(Panel(f"[bold red]Delete[/bold red]  {escape(item['title'])}", expand=False))
                try:
                    if Confirm.ask("  Delete this item and all its sessions?", console=console):
                        with get_db() as conn:
                            conn.execute("DELETE FROM media WHERE id=?", (media_id,))
                        return
                except KeyboardInterrupt:
                    pass

    finally:
        sys.stdout.write(_VT_SHWC)
        sys.stdout.flush()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MediaLog – keyboard-driven media consumption tracker"
    )
    parser.add_argument(
        "--import-csv", metavar="PATH",
        help="Import CSV into the database on startup, then launch the UI.",
    )
    args = parser.parse_args()

    init_db()
    _enable_vt()

    if args.import_csv:
        print(f"Importing {args.import_csv!r} …")
        ok, skip = import_csv(args.import_csv)
        print(f"  ✓ Imported : {ok}")
        print(f"  ⚑ Skipped  : {skip}  (duplicates / parse errors)")
        print()

    try:
        list_view()
    finally:
        sys.stdout.write(_VT_SHWC)
        sys.stdout.flush()
        console.clear()
