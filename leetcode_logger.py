#!/usr/bin/env python3
"""
lc.py — LeetCode problem logger with spaced-repetition review selection.

Usage:
  lc.py log                        Interactive: log a new solve session
  lc.py review                     Pick a problem to re-solve (weighted)
  lc.py review --dry-run           Show top-5 candidates with scores
  lc.py list [--sort date|score|name|times] [--tag TAG] [--diff easy|medium|hard]
  lc.py stats                      Aggregate stats
  lc.py edit <id_or_name>          Edit a problem's metadata
  lc.py delete <id_or_name>        Remove a problem

Storage: ~/.lc_log.json  (override with LC_LOG env var)
"""

import argparse
import json
import math
import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import shutil
import textwrap
import webbrowser

# ─────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────

STORE_PATH = Path(os.environ.get("LC_LOG", r"C:\Users\rodri\Desktop\leetcode\lc_log.json"))

LC_DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.6, "hard": 2.4}


def load() -> dict:
    if not STORE_PATH.exists():
        return {"problems": {}}
    with open(STORE_PATH) as f:
        return json.load(f)


def save(data: dict) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, STORE_PATH)


# ─────────────────────────────────────────────
# Review priority score
# ─────────────────────────────────────────────

def review_score(problem: dict, jitter: float = 0.15) -> float:
    """
    Computes an urgency score; higher → should review sooner.

    Components:
      1. Decay pressure   — days_since / ideal_interval
         Ideal interval grows geometrically with solve count but is
         compressed by subjective difficulty (harder → shorter intervals).
      2. Difficulty bias  — LC difficulty × subjective rating both lift score.
      3. Solve count      — fewer solves → higher urgency (sqrt dampening).
      4. Time modifier    — compares last timed session against your personal
                            average for this problem; getting slower raises score,
                            getting faster lowers it. Neutral when < 2 timed sessions.
                            Clamped to [0.7, 1.5] so one bad session can't dominate.
      5. Jitter           — ±jitter fraction of score to prevent determinism.
    """
    sessions: list[dict] = problem["sessions"]
    if not sessions:
        return 0.0

    last_date = date.fromisoformat(sessions[-1]["date"])
    days_since = (date.today() - last_date).days

    n = len(sessions)                                      # times solved
    subj = sessions[-1]["subjective_difficulty"]           # 1–5 (last session)
    lc_w = LC_DIFFICULTY_WEIGHT.get(problem["lc_difficulty"], 1.6)

    # Ideal interval in days: starts at base, doubles each solve,
    # but a higher subjective difficulty shrinks it (harder = review sooner).
    # difficulty_factor range: subj=1 → ~1.18, subj=5 → ~0.44
    difficulty_factor = 1.0 / (0.5 + 0.5 * subj / 5 * 3.5)
    base_interval = 1.5  # days after first solve before review is useful
    ideal_interval = base_interval * (2 ** (n - 1)) * difficulty_factor
    ideal_interval = max(1.0, min(ideal_interval, 180.0))  # cap at 6 months

    decay_pressure = days_since / ideal_interval           # >1 = overdue

    # Difficulty bias
    diff_bias = lc_w * (1.0 + subj * 0.4)

    # Solve count penalty: fewer solves → higher urgency
    count_factor = 1.0 / math.sqrt(n)

    raw = decay_pressure * diff_bias * count_factor

    # Minimum-exposure floor
    if n == 1:
        raw = max(raw, diff_bias * 0.5)

    # Time modifier: only active when ≥2 sessions have recorded times.
    # Compares the most recent timed session against your previous average
    # for this specific problem — slower than usual raises urgency, faster lowers it.
    timed = [s for s in sessions if s.get("time_minutes") is not None]
    if len(timed) >= 2:
        avg_prev      = sum(s["time_minutes"] for s in timed[:-1]) / len(timed[:-1])
        last_t        = timed[-1]["time_minutes"]
        time_ratio    = last_t / avg_prev          # >1 = getting slower
        time_modifier = max(0.7, min(time_ratio, 1.5))  # clamp to [0.7, 1.5]
        raw *= time_modifier

    # Jitter: uniform ±jitter fraction
    noise = random.uniform(1 - jitter, 1 + jitter)
    return raw * noise


_score_cache: dict = {}  # (slug, n_sessions, last_date) -> float

def compute_scores(problems: dict, jitter: float = 0.0) -> dict[str, float]:
    """Return {slug: score} using a simple cache keyed on stable problem state."""
    out = {}
    for slug, p in problems.items():
        sessions = p["sessions"]
        if not sessions:
            out[slug] = 0.0
            continue
        key = (slug, len(sessions), sessions[-1]["date"], str(date.today()))
        if jitter == 0.0 and key in _score_cache:
            out[slug] = _score_cache[key]
        else:
            s = review_score(p, jitter=jitter)
            if jitter == 0.0:
                _score_cache[key] = s
            out[slug] = s
    return out


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def slugify(name: str) -> str:
    """Normalised key: lowercase, strip surrounding whitespace."""
    return name.strip().lower()


def find_problem(data: dict, key: str, fatal: bool = False) -> Optional[tuple[str, dict]]:
    """Resolve by number prefix, exact slug, or partial name match."""
    problems = data["problems"]
    slug = slugify(key)
    # exact
    if slug in problems:
        return slug, problems[slug]
    # by lc_number
    for k, v in problems.items():
        if str(v.get("lc_number", "")) == key.strip():
            return k, v
    # partial
    matches = [(k, v) for k, v in problems.items() if slug in k]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous match — {len(matches)} problems contain '{key}':")
        for k, _ in matches:
            print(f"  {k}")
        if fatal:
            sys.exit(1)
        return None, None
    # Check trash and hint if found there
    deleted = data.get("deleted", {})
    if deleted:
        slug_d = slugify(key)
        for k, v in deleted.items():
            if k == slug_d or str(v.get("lc_number", "")) == key.strip() or slug_d in k:
                print(f"  (#{v.get('lc_number', '?')} '{v['name']}' is in trash — use 'restore {k}' to recover it)")
                break
    return None, None


def prompt(label: str, default=None, cast=str, choices=None) -> str:
    hint = f" [{default}]" if default is not None else ""
    if choices:
        hint += f" ({'/'.join(choices)})"
    while True:
        raw = input(f"  {label}{hint}: ").strip()
        if not raw and default is not None:
            return default
        if not raw:
            print("    ↳ required.")
            continue
        if choices and raw.lower() not in choices:
            print(f"    ↳ must be one of: {', '.join(choices)}")
            continue
        try:
            return cast(raw)
        except (ValueError, TypeError):
            print(f"    ↳ invalid input.")


def parse_date(raw: str):
    """
    Accept:
      dd            -> current month and year
      dd-mm         -> current year
      dd-mm-yyyy
    Always stores as ISO yyyy-mm-dd internally.
    Raises ValueError on bad input.
    """
    today = date.today()
    parts = raw.strip().split("-")
    if len(parts) == 1:
        d = int(parts[0])
        return date(today.year, today.month, d)
    elif len(parts) == 2:
        d, m = int(parts[0]), int(parts[1])
        return date(today.year, m, d)
    elif len(parts) == 3:
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, m, d)
    raise ValueError(f"Unrecognised date format: {raw}")


def prompt_date() -> str:
    """Prompt for a date in dd, dd-mm, or dd-mm-yyyy format. Returns ISO string."""
    today = date.today()
    default_display = f"{today.day:02d}-{today.month:02d}-{today.year}"
    while True:
        raw = input(f"  Date (dd / dd-mm / dd-mm-yyyy) [{default_display}]: ").strip()
        if not raw:
            return str(today)
        try:
            parsed = parse_date(raw)
            return str(parsed)
        except (ValueError, TypeError):
            print("    \u21b3 invalid date.")


def print_problem(slug: str, p: dict, score: float = None) -> None:
    sessions = p["sessions"]
    last = sessions[-1] if sessions else {}
    score_str = f"  score={score:.3f}" if score is not None else ""
    tags = ", ".join(p.get("tags", [])) or "—"
    print(
        f"  [{p.get('lc_number', '?'):>4}] {p['name']}\n"
        f"         LC={p['lc_difficulty'].capitalize()}  "
        f"subj={last.get('subjective_difficulty','?')}/5  "
        f"solves={len(sessions)}  "
        f"last={last.get('date','never')}  "
        f"tags=[{tags}]{score_str}"
    )


# ─────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────

def cmd_log(data: dict) -> None:
    print("\n── Log a solve ─────────────────────────────")
    lc_number = prompt("LeetCode number", cast=int)

    # Try to find an existing problem by that number
    existing_slug, existing = next(
        ((k, v) for k, v in data["problems"].items()
         if v.get("lc_number") == lc_number),
        (None, None)
    )

    if existing:
        slug = existing_slug
        print(f"  Found existing: {existing['name']}  ({len(existing['sessions'])} prior solves)")
        print(f"  URL: {existing.get('url', 'n/a')}")
    else:
        # Reject if number exists in soft-deleted bin (active already ruled out above)
        if any(v.get("lc_number") == lc_number for v in data.get("deleted", {}).values()):
            print(f"  ✗ #{lc_number} is in trash. Use 'restore {lc_number}' first.")
            return
        print("  (new problem — fill in metadata)")
        name     = prompt("Problem name")
        slug     = slugify(name)
        # Guard against slug collision (same name, different number)
        if slug in data["problems"]:
            print(f"  ✗ A problem named '{name}' already exists (#{data['problems'][slug]['lc_number']}). Choose a different name or log by number.")
            return
        lc_diff  = prompt("LC difficulty", choices=["easy", "medium", "hard"])
        tags_raw = input("  Tags (comma-separated, optional): ").strip()
        tags     = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]
        url_slug = name.strip().lower().replace(" ", "-")
        url      = f"https://leetcode.com/problems/{url_slug}/description/"
        data["problems"][slug] = {
            "name":          name,
            "lc_number":     lc_number,
            "lc_difficulty": lc_diff,
            "tags":          tags,
            "url":           url,
            "sessions":      [],
        }

    problem = data["problems"][slug]

    print("\n  ── Session details")
    solve_date  = prompt_date()
    _t          = input("  Time taken (minutes, Enter to skip): ").strip()
    time_mins   = int(_t) if _t.isdigit() else None
    subj        = prompt("Subjective difficulty 1–5", cast=int, choices=["1","2","3","4","5"])
    got_it      = prompt("Got it without help?", choices=["y", "n"])
    notes       = input("  Notes (optional): ").strip()

    session = {
        "date":                  solve_date,
        "time_minutes":          time_mins,
        "subjective_difficulty": int(subj),
        "solved_unaided":        got_it == "y",
        "notes":                 notes,
    }
    problem["sessions"].append(session)
    save(data)
    print(f"\n  ✓ Logged. Total solves: {len(problem['sessions'])}\n")


def cmd_review(data: dict, dry_run: bool = False) -> None:
    problems = data["problems"]
    if not problems:
        print("No problems logged yet.")
        return

    scores = compute_scores(problems, jitter=0.15)
    scored = [
        (scores[slug], slug, p)
        for slug, p in problems.items()
        if p["sessions"]
    ]

    if not scored:
        print("No problems with sessions.")
        return

    scored.sort(reverse=True, key=lambda x: x[0])

    if dry_run:
        print("\n── Top review candidates ───────────────────")
        for score, slug, p in scored[:10]:
            print_problem(slug, p, score)
        print()
        return

    # Weighted random selection from top-half by score to preserve some
    # non-determinism while strongly biasing toward high-urgency problems.
    # We softmax over scores with temperature T to get a probability distribution.
    T = max(s for s, *_ in scored) * 0.4  # temperature = 40% of max score
    T = max(T, 0.01)
    weights = [math.exp(s / T) for s, *_ in scored]
    total   = sum(weights)
    probs   = [w / total for w in weights]

    chosen_idx = random.choices(range(len(scored)), weights=probs, k=1)[0]
    score, slug, p = scored[chosen_idx]

    url = p.get("url", "")
    print("\n── Recommended review ──────────────────────")
    print_problem(slug, p, score)
    print(f"\n  URL: {url or 'n/a'}")

    if url:
        open_it = input("  Open in browser? (y/n) [y]: ").strip().lower()
        if open_it != "n":
            webbrowser.open(url)

    go = input("  Log a session now? (y/n) [n]: ").strip().lower()
    if go == "y":
        cmd_log(data)


PAGE_SIZE = 10

def cmd_list(data: dict, sort_by: str, tag_filter: Optional[str], diff_filter: Optional[str], name_filter: Optional[str] = None) -> None:
    problems = list(data["problems"].items())
    if not problems:
        print("No problems logged.")
        return

    if name_filter:
        needle = name_filter.strip().lower()
        problems = [(k, v) for k, v in problems if needle in k or needle in str(v.get("lc_number", ""))]
    if tag_filter:
        problems = [(k, v) for k, v in problems if tag_filter.lower() in v.get("tags", [])]
    if diff_filter:
        problems = [(k, v) for k, v in problems if v["lc_difficulty"] == diff_filter.lower()]

    if not problems:
        print("  No problems match the given filters.")
        return

    scores: dict = {}
    if sort_by == "score":
        scores = compute_scores(dict(problems), jitter=0.0)
        problems.sort(key=lambda kv: scores.get(kv[0], 0.0), reverse=True)
    elif sort_by == "date":
        problems.sort(key=lambda kv: kv[1]["sessions"][-1]["date"] if kv[1]["sessions"] else "", reverse=True)
    elif sort_by == "times":
        problems.sort(key=lambda kv: len(kv[1]["sessions"]), reverse=True)
    else:  # name
        problems.sort(key=lambda kv: kv[0])
    total = len(problems)
    page  = 0
    while True:
        start = page * PAGE_SIZE
        end   = min(start + PAGE_SIZE, total)
        chunk = problems[start:end]

        print(f"\n── Problems ({start + 1}–{end} of {total}) ────────────────────")
        for slug, p in chunk:
            score = scores.get(slug) if sort_by == "score" else None
            print_problem(slug, p, score)

        if end >= total:
            print()
            break

        remaining = total - end
        try:
            cont = input(f"\n  Enter for next page ({remaining} remaining), q to stop: ").strip().lower()
        except EOFError:
            print()
            break
        if cont == "q":
            print()
            break
        page += 1



def cmd_view(data: dict, key: str) -> None:
    slug, p = find_problem(data, key)
    if not p:
        print(f"  Problem '{key}' not found.")
        return

    sessions = p["sessions"]
    print(f"\n── {p['name']} ({'#' + str(p.get('lc_number', '?'))})")
    print(f"  LC difficulty : {p['lc_difficulty'].capitalize()}")
    print(f"  Tags          : {', '.join(p.get('tags', [])) or '—'}")
    print(f"  URL           : {p.get('url', 'n/a')}")
    print(f"  Total solves  : {len(sessions)}")

    if not sessions:
        print()
        return

    timed   = [s for s in sessions if s.get("time_minutes") is not None]
    unaided = sum(1 for s in sessions if s.get("solved_unaided"))
    avg_t   = sum(s["time_minutes"] for s in timed) / len(timed) if timed else None
    avg_s   = sum(s["subjective_difficulty"] for s in sessions) / len(sessions)

    print(f"  Avg time      : {avg_t:.0f} min" if avg_t is not None else "  Avg time      : —")
    print(f"  Avg subj diff : {avg_s:.1f}/5")
    print(f"  Unaided       : {unaided}/{len(sessions)}")
    print(f"\n  Sessions:")
    term_width = shutil.get_terminal_size(fallback=(100, 24)).columns
    for i, s in enumerate(sessions, 1):
        t     = f"{s['time_minutes']} min" if s.get("time_minutes") is not None else "—"
        aided = "" if s.get("solved_unaided") else "  [aided]"
        header = f"    {i:>2}. {s['date']}  {t}  subj={s['subjective_difficulty']}/5{aided}"
        if s.get("notes"):
            # indent continuation lines to align under the note text
            note_indent = " " * (len(header) + 2)
            wrapped = textwrap.fill(
                s['notes'],
                width=term_width,
                initial_indent=header + "  \"",
                subsequent_indent=note_indent,
            )
            print(wrapped + "\"")
        else:
            print(header)
    print()


def cmd_stats(data: dict) -> None:
    problems = data["problems"]
    if not problems:
        print("No data.")
        return

    all_sessions = [s for p in problems.values() for s in p["sessions"]]
    total_time   = sum(s["time_minutes"] for s in all_sessions if s.get("time_minutes") is not None)
    avg_subj     = sum(s["subjective_difficulty"] for s in all_sessions) / max(len(all_sessions), 1)
    unaided      = sum(1 for s in all_sessions if s.get("solved_unaided"))

    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for p in problems.values():
        diff_counts[p["lc_difficulty"]] = diff_counts.get(p["lc_difficulty"], 0) + 1

    all_tags: dict[str, int] = {}
    for p in problems.values():
        for t in p.get("tags", []):
            all_tags[t] = all_tags.get(t, 0) + 1

    print("\n── Stats ───────────────────────────────────")
    print(f"  Unique problems : {len(problems)}")
    print(f"  Total sessions  : {len(all_sessions)}")
    print(f"  Total time      : {total_time} min  ({total_time/60:.1f} h)")
    print(f"  Avg subj diff   : {avg_subj:.2f}/5")
    print(f"  Unaided solves  : {unaided}/{len(all_sessions)}")
    print(f"  By LC difficulty: Easy={diff_counts['easy']}  Medium={diff_counts['medium']}  Hard={diff_counts['hard']}")
    if all_tags:
        top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:8]
        print(f"  Top tags        : {', '.join(f'{t}({c})' for t, c in top_tags)}")

    # streak — only count if last solve was today or yesterday
    solve_dates = sorted({s["date"] for s in all_sessions})
    streak = 0
    if solve_dates:
        today_d = date.today()
        last_d  = date.fromisoformat(solve_dates[-1])
        gap     = (today_d - last_d).days
        if gap <= 1:
            streak = 1
            for i in range(len(solve_dates) - 1, 0, -1):
                d1 = date.fromisoformat(solve_dates[i])
                d0 = date.fromisoformat(solve_dates[i - 1])
                if (d1 - d0).days == 1:
                    streak += 1
                else:
                    break
    print(f"  Current streak  : {streak} day(s)")
    print()


def cmd_edit(data: dict, key: str, fatal: bool = False) -> None:
    slug, problem = find_problem(data, key, fatal=fatal)
    if not problem:
        print(f"Problem '{key}' not found.")
        return

    print(f"\n── Edit: {problem['name']}  (leave blank to keep current)")

    # ── Problem metadata ──────────────────────────────────────────────────────
    lc_diff = input(f"  LC difficulty [{problem['lc_difficulty']}]: ").strip()
    if lc_diff in ("easy", "medium", "hard"):
        problem["lc_difficulty"] = lc_diff

    tags_raw = input(f"  Tags [{','.join(problem.get('tags', []))}]: ").strip()
    if tags_raw:
        problem["tags"] = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]

    url = input(f"  URL [{problem.get('url','')}]: ").strip()
    if url:
        problem["url"] = url

    # ── Session editing ───────────────────────────────────────────────────────
    sessions = problem["sessions"]
    if sessions:
        print(f"\n  Sessions (leave blank to keep current):")
        for i, s in enumerate(sessions, 1):
            t = f"{s['time_minutes']} min" if s.get("time_minutes") is not None else "—"
            note_preview = s.get("notes", "") or "—"
            print(f"    {i}. {s['date']}  {t}  subj={s['subjective_difficulty']}/5  \"{note_preview}\"")

        raw_idx = input(f"\n  Edit which session? (1–{len(sessions)}, Enter to skip): ").strip()
        if raw_idx.isdigit() and 1 <= int(raw_idx) <= len(sessions):
            s = sessions[int(raw_idx) - 1]

            new_date = input(f"  Date [{s['date']}]: ").strip()
            if new_date:
                try:
                    s["date"] = str(parse_date(new_date))
                except (ValueError, TypeError):
                    print("    ↳ invalid date, kept original.")

            cur_t = str(s["time_minutes"]) if s.get("time_minutes") is not None else ""
            new_t = input(f"  Time in minutes [{cur_t or '—'}]: ").strip()
            if new_t:
                s["time_minutes"] = int(new_t) if new_t.isdigit() else None

            new_subj = input(f"  Subjective difficulty [{s['subjective_difficulty']}]: ").strip()
            if new_subj in ("1", "2", "3", "4", "5"):
                s["subjective_difficulty"] = int(new_subj)

            cur_aided = "y" if s.get("solved_unaided") else "n"
            new_aided = input(f"  Solved unaided? [{cur_aided}] (y/n): ").strip().lower()
            if new_aided in ("y", "n"):
                s["solved_unaided"] = new_aided == "y"

            cur_note = s.get("notes", "")
            new_note = input(f"  Notes [{cur_note or '—'}]: ").strip()
            if new_note:
                s["notes"] = new_note
            elif new_note == "" and cur_note:
                clear = input("  Clear existing note? (y/n) [n]: ").strip().lower()
                if clear == "y":
                    s["notes"] = ""

    save(data)
    print("  ✓ Updated.\n")


def cmd_delete(data: dict, key: str, fatal: bool = False) -> None:
    slug, problem = find_problem(data, key, fatal=fatal)
    if not problem:
        print(f"  Problem '{key}' not found.")
        return
    confirm = input(f"  Move '{problem['name']}' ({len(problem['sessions'])} sessions) to trash? (yes/no): ").strip()
    if confirm == "yes":
        data.setdefault("deleted", {})[slug] = problem
        del data["problems"][slug]
        save(data)
        print(f"  ✓ Moved to trash.  (restore with: restore {slug})\n")
    else:
        print("  Aborted.\n")


def cmd_restore(data: dict, key: str) -> None:
    deleted = data.get("deleted", {})
    if not deleted:
        print("  Trash is empty.")
        return
    # resolve: exact slug, number, or partial
    slug = None
    for k, v in deleted.items():
        if k == key.strip().lower() or str(v.get("lc_number", "")) == key:
            slug = k
            break
    if slug is None:
        matches = [k for k in deleted if key.strip().lower() in k]
        if len(matches) == 1:
            slug = matches[0]
        elif len(matches) > 1:
            print(f"  Ambiguous — matches: {', '.join(matches)}")
            return
    if slug is None:
        print(f"  '{key}' not found in trash.")
        return
    data["problems"][slug] = deleted.pop(slug)
    save(data)
    restored_name = data["problems"][slug]["name"]
    print(f"  ✓ Restored '{restored_name}'.\n")


# ─────────────────────────────────────────────
# Interactive shell
# ─────────────────────────────────────────────

SHELL_COMMANDS = ["log", "review", "list", "stats", "view", "edit", "delete", "restore", "help", "clear", "exit", "quit"]

SHELL_HELP = """
Commands:
  log    (l)                   Log a new solve session
  review        [--dry-run]    Pick a problem to re-solve
  list          [--sort date|name|times|score] [--tag TAG] [--diff easy|medium|hard] [--name TEXT]
                 bare word also works as name filter: `list median`
  stats                        Aggregate stats
  view   <name|number>         Show full details and session history
  edit   <name|number>         Edit problem metadata
  delete <name|number>         Move a problem to trash
  restore <name|number>        Restore a problem from trash
  clear  (cls)                 Clear the terminal
  help   (h)                   Show this message
  exit / quit (q) / Ctrl-D     Leave
"""


class ShellCompleter:
    """Tab-completes commands and problem names/numbers."""

    def __init__(self, data_ref: list) -> None:
        # data_ref is a 1-element list so completer always sees fresh data
        self._data = data_ref
        self._matches: list[str] = []

    def _candidates(self) -> list[str]:
        data = self._data[0]
        problem_names  = list(data["problems"].keys())
        problem_nums   = [str(v["lc_number"]) for v in data["problems"].values()]
        return SHELL_COMMANDS + problem_names + problem_nums

    def complete(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            self._matches = [c for c in self._candidates() if c.startswith(text.lower())]
        try:
            return self._matches[state]
        except IndexError:
            return None


def _setup_readline(data_ref: list) -> None:
    try:
        import readline
        completer = ShellCompleter(data_ref)
        readline.set_completer(completer.complete)
        readline.parse_and_bind(
            "tab: complete" if sys.platform != "darwin" else "bind ^I rl_complete"
        )
        readline.set_completer_delims(" \t\n")

        # Persist history across sessions
        hist = Path.home() / ".lc_history"
        try:
            readline.read_history_file(hist)
        except FileNotFoundError:
            pass
        import atexit
        atexit.register(readline.write_history_file, hist)
    except ImportError:
        pass  # Windows without pyreadline — degrade gracefully


def _shell_dashboard(data: dict) -> None:
    """Single-line summary shown each time we enter / refresh the shell."""
    problems     = data["problems"]
    all_sessions = [s for p in problems.values() for s in p["sessions"]]
    unaided      = sum(1 for s in all_sessions if s.get("solved_unaided"))
    diff_counts  = {"easy": 0, "medium": 0, "hard": 0}
    for p in problems.values():
        diff_counts[p["lc_difficulty"]] += 1

    # Next-up hint — use cached deterministic scores
    next_up = ""
    if problems:
        scores = compute_scores(problems, jitter=0.0)
        if scores:
            best_slug = max(scores, key=lambda k: scores[k])
            next_up = f"  │  next-up: {problems[best_slug]['name']}"

    print(
        f"\n  lc shell  │  {len(problems)} problems  │  "
        f"E:{diff_counts['easy']} M:{diff_counts['medium']} H:{diff_counts['hard']}  │  "
        f"sessions:{len(all_sessions)}  unaided:{unaided}{next_up}"
    )
    print("  Type 'help' for commands, Tab to complete, Ctrl-D to exit.\n")


def _dispatch_shell_line(line: str, data: dict) -> dict:
    """Parse and execute one shell line. Returns (possibly mutated) data."""
    parts = line.split()
    if not parts:
        return data
    cmd, rest = parts[0].lower(), parts[1:]

    # Always reload from disk so external edits are visible
    data = load()

    # aliases
    cmd = {"q": "quit", "h": "help", "l": "log", "cls": "clear", "ll": "list"}.get(cmd, cmd)

    if cmd in ("exit", "quit"):
        raise EOFError

    elif cmd == "help":
        print(SHELL_HELP)

    elif cmd == "clear":
        os.system("cls" if sys.platform == "win32" else "clear")

    elif cmd == "log":
        cmd_log(data)

    elif cmd == "review":
        dry = "--dry-run" in rest
        cmd_review(data, dry_run=dry)

    elif cmd == "list":
        sort_by     = "date"
        tag_filter  = None
        diff_filter = None
        name_filter = None
        i = 0
        while i < len(rest):
            if rest[i] == "--sort" and i + 1 < len(rest):
                sort_by = rest[i + 1]; i += 2
            elif rest[i] == "--tag" and i + 1 < len(rest):
                tag_filter = rest[i + 1]; i += 2
            elif rest[i] == "--diff" and i + 1 < len(rest):
                diff_filter = rest[i + 1]; i += 2
            elif rest[i] == "--name" and i + 1 < len(rest):
                name_filter = rest[i + 1]; i += 2
            elif not rest[i].startswith("--"):
                # bare word treated as name filter: `list median`
                name_filter = rest[i]; i += 1
            else:
                i += 1
        cmd_list(data, sort_by=sort_by, tag_filter=tag_filter, diff_filter=diff_filter, name_filter=name_filter)

    elif cmd == "stats":
        cmd_stats(data)

    elif cmd in ("view", "search"):
        if not rest:
            print("  Usage: view <name|number>")
        else:
            cmd_view(data, " ".join(rest))

    elif cmd == "edit":
        if not rest:
            print("  Usage: edit <name|number>")
        else:
            cmd_edit(data, " ".join(rest))

    elif cmd == "delete":
        if not rest:
            print("  Usage: delete <name|number>")
        else:
            cmd_delete(data, " ".join(rest))

    elif cmd == "restore":
        if not rest:
            print("  Usage: restore <name|number>")
        else:
            cmd_restore(data, " ".join(rest))

    else:
        print(f"  Unknown command '{cmd}'. Type 'help'.")

    return data


def cmd_shell() -> None:
    data    = load()
    data_ref = [data]   # mutable container for completer
    _setup_readline(data_ref)
    _shell_dashboard(data)

    while True:
        try:
            line = input("lc > ").strip()
        except EOFError:
            print("\n  ~~")
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line:
            continue

        try:
            data = _dispatch_shell_line(line, data)
            data_ref[0] = data
        except EOFError:
            print("\n  ~~")
            break
        except KeyboardInterrupt:
            print("  (interrupted)")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LeetCode solve logger with spaced-repetition review.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("shell", help="Interactive shell (default when no command given)")
    sub.add_parser("log",   help="Log a solve session")

    rev = sub.add_parser("review", help="Pick a problem to re-solve")
    rev.add_argument("--dry-run", action="store_true", help="Show top candidates without picking one")

    lst = sub.add_parser("list", help="List problems")
    lst.add_argument("--sort", choices=["date", "name", "times", "score"], default="date")
    lst.add_argument("--tag",  dest="tag",  default=None)
    lst.add_argument("--diff", dest="diff", choices=["easy", "medium", "hard"], default=None)
    lst.add_argument("--name", dest="name", default=None, help="Filter by name substring")

    sub.add_parser("stats", help="Show aggregate stats")

    vw = sub.add_parser("view", help="Show full details of a problem")
    vw.add_argument("problem")

    edt = sub.add_parser("edit", help="Edit problem metadata")
    edt.add_argument("problem", help="Problem name, number, or partial name")

    dlt = sub.add_parser("delete", help="Move a problem to trash")
    dlt.add_argument("problem")

    rst = sub.add_parser("restore", help="Restore a problem from trash")
    rst.add_argument("problem")

    args = parser.parse_args()

    # No subcommand → drop into interactive shell
    if not args.cmd or args.cmd == "shell":
        cmd_shell()
        return

    data = load()

    if args.cmd == "log":
        cmd_log(data)
    elif args.cmd == "review":
        cmd_review(data, dry_run=args.dry_run)
    elif args.cmd == "list":
        cmd_list(data, sort_by=args.sort, tag_filter=args.tag, diff_filter=args.diff, name_filter=args.name)
    elif args.cmd == "stats":
        cmd_stats(data)
    elif args.cmd == "view":
        cmd_view(data, args.problem)
    elif args.cmd == "edit":
        cmd_edit(data, args.problem, fatal=True)
    elif args.cmd == "delete":
        cmd_delete(data, args.problem, fatal=True)
    elif args.cmd == "restore":
        cmd_restore(data, args.problem)


if __name__ == "__main__":
    main()
