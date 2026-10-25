"""Render the neofetch-style profile card (dark and light SVG) with live GitHub stats.

Usage:
    GITHUB_TOKEN=... python scripts/neofetch.py [--offline]

The card text lives in ``SECTIONS`` below; stats are pulled from the GitHub
GraphQL API and written into ``dark_mode.svg`` / ``light_mode.svg``.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

USER = "sodinokibii"
ROOT = Path(__file__).resolve().parent.parent
ASCII_FILE = ROOT / "assets" / "ascii.txt"

WIDTH = 1000
LINE_HEIGHT = 20
TOP = 30
ART_X = 15
INFO_X = 425
INFO_COLS = 58  # characters in a full info row, dots included


@dataclass(frozen=True)
class Theme:
    """Colour set for one rendering of the card."""

    name: str
    background: str
    text: str
    key: str
    value: str
    dots: str
    accent: str
    border: str


DARK = Theme("dark_mode", "#0d1117", "#c9d1d9", "#ff7b72", "#a5d6ff", "#484f58", "#e05d5d", "#30363d")
LIGHT = Theme("light_mode", "#f6f8fa", "#24292f", "#b31d28", "#0a3069", "#afb8c1", "#b91c1c", "#d0d7de")


@dataclass(frozen=True)
class Stats:
    """Numbers shown in the GitHub Stats block."""

    repos: int
    contributed: int
    stars: int
    followers: int
    commits: int
    created: date


@dataclass(frozen=True)
class Row:
    """A ``key: ..... value`` line; ``key`` may be dotted (``Languages.Programming``)."""

    key: str
    value: str


@dataclass(frozen=True)
class SplitRow:
    """Two ``key: value`` pairs on one line, separated by ``|``."""

    left: Row
    right: Row
    left_cols: int = 27


Line = Union[Row, SplitRow, None]


@dataclass
class Section:
    """A titled block of rows in the info column."""

    title: str
    rows: List[Line] = field(default_factory=list)


def uptime(since: date, today: Optional[date] = None) -> str:
    """Format the time elapsed since ``since`` as years, months and days.

    Args:
        since: Start date (account creation).
        today: End date; defaults to the current date.

    Returns:
        A string such as ``"1 year, 8 months, 3 days"``.
    """
    today = today or date.today()
    months = (today.year - since.year) * 12 + today.month - since.month
    if today.day < since.day:
        months -= 1
    anchor_year, anchor_month = since.year + (since.month - 1 + months) // 12, (since.month - 1 + months) % 12 + 1
    anchor_day = min(since.day, calendar.monthrange(anchor_year, anchor_month)[1])
    days = (today - date(anchor_year, anchor_month, anchor_day)).days
    years, months = divmod(months, 12)

    def plural(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    return ", ".join([plural(years, "year"), plural(months, "month"), plural(days, "day")])


def build_sections(stats: Stats) -> List[Section]:
    """Lay out the card's info column.

    Args:
        stats: Live numbers for the GitHub Stats block.

    Returns:
        Sections in display order.
    """
    return [
        Section(f"{USER}@github", [
            Row("OS", "Windows 11, Linux"),
            Row("Uptime", uptime(stats.created)),
            Row("Kernel", "Windows NT internals"),
            Row("Shell", "PowerShell, bash"),
            Row("IDE", "Visual Studio, VS Code"),
            None,
            Row("Languages.Programming", "C++, C, Python, x86-64 asm"),
            Row("Languages.Real", "Russian, English"),
            None,
            Row("Tools.Reversing", "IDA Pro, Ghidra, x64dbg, WinDbg"),
            Row("Tools.Runtime", "Frida, Process Monitor, Wireshark"),
            Row("Tools.Build", "CMake, MSBuild, WDK"),
        ]),
        Section("Current Case", [
            Row("Case", "lbp810_capt"),
            Row("Evidence", "Canon LBP-810 -> Windows 11"),
            Row("Verdict", "solved, it prints"),
        ]),
        Section("GitHub Stats", [
            SplitRow(Row("Repos", f"{stats.repos} {{Contributed: {stats.contributed}}}"), Row("Stars", f"{stats.stars:,}")),
            SplitRow(Row("Commits", f"{stats.commits:,}"), Row("Followers", f"{stats.followers:,}")),
        ]),
    ]


def render_row(row: Row, cols: int) -> Tuple[str, int]:
    """Render one ``key: .... value`` pair as SVG tspans padded to ``cols`` characters.

    Args:
        row: The pair to render.
        cols: Total character width, dots included.

    Returns:
        The tspan markup and its width in characters.
    """
    keys = row.key.split(".")
    key_markup = ".".join(f'<tspan class="key">{escape(k)}</tspan>' for k in keys)
    dots = max(1, cols - len(row.key) - len(row.value) - 3)
    markup = f'{key_markup}:<tspan class="cc"> {"." * dots} </tspan><tspan class="value">{escape(row.value)}</tspan>'
    return markup, len(row.key) + dots + len(row.value) + 3


def render_svg(theme: Theme, art: Sequence[str], sections: Sequence[Section]) -> str:
    """Build the full SVG document for one theme.

    Args:
        theme: Colours to use.
        art: ASCII art lines for the left column.
        sections: Info column content.

    Returns:
        The SVG source.
    """
    info: List[str] = []
    y = TOP
    for index, section in enumerate(sections):
        if index:
            y += LINE_HEIGHT
        prefix = "" if index == 0 else "- "
        rule = "-" * max(3, INFO_COLS - len(prefix) - len(section.title) - 1)
        info.append(f'<tspan x="{INFO_X}" y="{y}" class="accent">{prefix}{escape(section.title)}</tspan> <tspan class="cc">{rule}</tspan>')
        for line in section.rows:
            y += LINE_HEIGHT
            lead = f'<tspan x="{INFO_X}" y="{y}" class="cc">. </tspan>'
            if line is None:
                info.append(lead)
            elif isinstance(line, Row):
                info.append(lead + render_row(line, INFO_COLS - 2)[0])
            else:
                left, _ = render_row(line.left, line.left_cols)
                right, _ = render_row(line.right, INFO_COLS - 2 - line.left_cols - 3)
                info.append(f"{lead}{left} | {right}")
    y += LINE_HEIGHT
    info.append(f'<tspan x="{INFO_X}" y="{y}" class="accent">&gt; </tspan><tspan class="value">every binary has a motive</tspan><tspan class="caret">_</tspan>')

    height = max(y, TOP + LINE_HEIGHT * (len(art) - 1)) + 20
    art_markup = "\n".join(
        f'<tspan x="{ART_X}" y="{TOP + i * LINE_HEIGHT}" class="art" style="animation-delay:{i * 0.04:.2f}s">{escape(line)}</tspan>'
        for i, line in enumerate(art)
    )
    info_markup = "\n".join(
        f'<tspan class="row" style="animation-delay:{0.3 + i * 0.05:.2f}s">{line}</tspan>' for i, line in enumerate(info)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,'SFMono-Regular',Menlo,monospace" width="{WIDTH}px" height="{height}px" font-size="16px" role="img" aria-label="{USER} profile card">
<style>
@font-face {{ src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback'; font-display: swap; size-adjust: 109%; }}
text, tspan {{ white-space: pre; }}
.key {{ fill: {theme.key}; }}
.value {{ fill: {theme.value}; }}
.cc {{ fill: {theme.dots}; }}
.accent {{ fill: {theme.accent}; font-weight: bold; }}
.art {{ fill: {theme.text}; }}
/* Visible by default; the hidden state only exists while the animation runs. */
.art, .row {{ animation: reveal 0.4s ease-out backwards; }}
.caret {{ fill: {theme.accent}; animation: blink 1s steps(1) infinite; }}
@keyframes reveal {{ from {{ opacity: 0; }} }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
</style>
<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" fill="{theme.background}" stroke="{theme.border}" rx="15"/>
<text fill="{theme.text}">
{art_markup}
</text>
<text fill="{theme.text}">
{info_markup}
</text>
</svg>
"""


def graphql(query: str, variables: Dict[str, object], token: str) -> Dict[str, object]:
    """Run a GitHub GraphQL query.

    Args:
        query: GraphQL document.
        variables: Query variables.
        token: GitHub token with read access to public data.

    Returns:
        The ``data`` object of the response.

    Raises:
        RuntimeError: If the API reports errors.
    """
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub API error: {payload['errors']}")
    return payload["data"]


def fetch_stats(token: str) -> Stats:
    """Collect repo, star, follower and all-time commit counts for ``USER``.

    Args:
        token: GitHub token.

    Returns:
        The current stats.
    """
    data = graphql(
        """query($login: String!) { user(login: $login) {
             createdAt
             followers { totalCount }
             repositories(ownerAffiliations: OWNER, isFork: false, first: 100) { totalCount nodes { stargazerCount } }
             repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
           } }""",
        {"login": USER},
        token,
    )["user"]
    created = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
    commits = 0
    for year in range(created.year, date.today().year + 1):
        window = graphql(
            """query($login: String!, $from: DateTime!, $to: DateTime!) { user(login: $login) {
                 contributionsCollection(from: $from, to: $to) { totalCommitContributions restrictedContributionsCount }
               } }""",
            {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
            token,
        )["user"]["contributionsCollection"]
        commits += window["totalCommitContributions"] + window["restrictedContributionsCount"]
    return Stats(
        repos=data["repositories"]["totalCount"],
        contributed=data["repositoriesContributedTo"]["totalCount"],
        stars=sum(node["stargazerCount"] for node in data["repositories"]["nodes"]),
        followers=data["followers"]["totalCount"],
        commits=commits,
        created=created.date(),
    )


def main() -> None:
    """Fetch stats (unless ``--offline``) and write both SVG themes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="use placeholder stats instead of the API")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if args.offline or not token:
        stats = Stats(repos=0, contributed=0, stars=0, followers=0, commits=0, created=date(2025, 2, 1))
    else:
        stats = fetch_stats(token)

    with ASCII_FILE.open(encoding="utf-8") as handle:
        art = [line.rstrip("\n") for line in handle]
    sections = build_sections(stats)
    for theme in (DARK, LIGHT):
        (ROOT / f"{theme.name}.svg").write_text(render_svg(theme, art, sections), encoding="utf-8")
    print(f"rendered {stats}")


if __name__ == "__main__":
    main()
