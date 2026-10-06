"""Generate terminal-style SVG cards for the GitHub profile README.

Outputs:
  assets/contributions.svg  - `./contributions.sh` heatmap of the last year
  assets/whoami.svg         - `whoami` panel: ASCII portrait + stats + monthly bars

Requires env GH_TOKEN (or GITHUB_TOKEN) and optionally GH_USER.
"""
import datetime as dt
import io
import json
import os
import urllib.request
from collections import OrderedDict
from xml.sax.saxutils import escape

from PIL import Image, ImageOps, ImageEnhance

USER = os.environ.get("GH_USER", "Batsaikhan8855")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
GREEN = "#3fb950"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"


def graphql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]


def fetch():
    q = """query($login:String!){user(login:$login){avatarUrl(size:400)
      contributionsCollection{contributionCalendar{totalContributions
        weeks{contributionDays{date contributionCount contributionLevel}}}}}}"""
    u = graphql(q, {"login": USER})["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    return u["avatarUrl"], cal["totalContributions"], cal["weeks"], days


def stats(days):
    counts = [d["contributionCount"] for d in days]
    today = dt.date.fromisoformat(days[-1]["date"])
    # current streak: allow today to be empty without breaking it
    cur, i = 0, len(days) - 1
    if counts[i] == 0:
        i -= 1
    while i >= 0 and counts[i] > 0:
        cur, i = cur + 1, i - 1
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    active = sum(1 for c in counts if c > 0)
    best = max(days, key=lambda d: d["contributionCount"])
    months = OrderedDict()
    for k in range(11, -1, -1):
        y, m = today.year, today.month - k
        while m <= 0:
            y, m = y - 1, m + 12
        months[(y, m)] = 0
    for d in days:
        dd = dt.date.fromisoformat(d["date"])
        if (dd.year, dd.month) in months:
            months[(dd.year, dd.month)] += d["contributionCount"]
    return {
        "current": cur,
        "longest": longest,
        "active": active,
        "total_days": len(days),
        "best": best["contributionCount"],
        "best_date": dt.date.fromisoformat(best["date"]).strftime("%b %-d"),
        "avg": (sum(counts) / active) if active else 0,
        "months": months,
    }


def window(w, h, title, body):
    dots = "".join(
        f'<circle cx="{18 + i * 16}" cy="16" r="5" fill="{c}"/>'
        for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"])
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'font-family="{FONT}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'{dots}<text x="{w / 2}" y="20" fill="{MUTED}" font-size="12" text-anchor="middle">{escape(title)}</text>'
        f'<line x1="0" y1="32" x2="{w}" y2="32" stroke="{BORDER}"/>{body}</svg>'
    )


def prompt(x, y, cmd, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-size="14" font-weight="700" text-anchor="{anchor}">'
        f'<tspan fill="{GREEN}">{USER.lower()}@github</tspan><tspan fill="{MUTED}"> ~ $ </tspan>'
        f'<tspan fill="{TEXT}">{escape(cmd)}</tspan><tspan fill="{GREEN}">▋'
        f'<animate attributeName="opacity" values="1;0;1" dur="1.2s" repeatCount="indefinite"/>'
        f"</tspan></text>"
    )


def contributions_svg(total, weeks):
    cell, gap = 13, 3
    left, top = 46, 104
    w = left + len(weeks) * (cell + gap) + 24
    h = top + 7 * (cell + gap) + 46
    body = [prompt(w / 2, 60, "./contributions.sh", "middle")]
    last_month = None
    for wi, week in enumerate(weeks):
        x = left + wi * (cell + gap)
        first = dt.date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last_month and first.day <= 7 and wi < len(weeks) - 2:
            body.append(f'<text x="{x}" y="{top - 8}" fill="{MUTED}" font-size="11">{first:%b}</text>')
            last_month = first.month
        for d in week["contributionDays"]:
            dd = dt.date.fromisoformat(d["date"])
            row = (dd.weekday() + 1) % 7  # Sunday first
            lvl = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"].index(
                d["contributionLevel"]
            )
            body.append(
                f'<rect x="{x}" y="{top + row * (cell + gap)}" width="{cell}" height="{cell}" rx="2.5" '
                f'fill="{LEVELS[lvl]}" stroke="#ffffff0d">'
                f'<title>{d["contributionCount"]} on {dd:%b %-d, %Y}</title></rect>'
            )
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body.append(
            f'<text x="{left - 8}" y="{top + r * (cell + gap) + 10}" fill="{MUTED}" font-size="11" '
            f'text-anchor="end">{name}</text>'
        )
    ly = top + 7 * (cell + gap) + 24
    body.append(
        f'<text x="{left}" y="{ly}" fill="{TEXT}" font-size="12"><tspan font-weight="700">{total:,}</tspan>'
        f" contributions in the last year</text>"
    )
    lx = w - 24 - 5 * (cell + 3) - 40
    body.append(f'<text x="{lx - 8}" y="{ly}" fill="{MUTED}" font-size="11" text-anchor="end">Less</text>')
    for i, c in enumerate(LEVELS):
        body.append(f'<rect x="{lx + i * (cell + 3)}" y="{ly - 11}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"/>')
    body.append(f'<text x="{lx + 5 * (cell + 3) + 4}" y="{ly}" fill="{MUTED}" font-size="11">More</text>')
    return window(w, h, f"{USER.lower()} — contributions.sh", "".join(body))


def ascii_portrait(avatar_url, cols=56, rows=33):
    with urllib.request.urlopen(avatar_url) as r:
        img = Image.open(io.BytesIO(r.read())).convert("L")
    img = ImageOps.autocontrast(ImageEnhance.Contrast(img).enhance(1.4))
    img = img.resize((cols, rows))
    ramp = " .:-=+*#%@"  # bright pixels -> dense glyphs, since the card background is dark
    px = img.load()
    return ["".join(ramp[px[x, y] * (len(ramp) - 1) // 255] for x in range(cols)) for y in range(rows)]


def whoami_svg(avatar_url, total, s):
    w, h = 900, 470
    body = [prompt(w / 2, 60, "whoami", "middle")]
    # portrait panel
    px0, py0, pw, ph = 20, 80, 400, 370
    body.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{px0 + 12}" y="{py0 + 18}" fill="{MUTED}" font-size="10">portrait.txt</text>')
    lines = ascii_portrait(avatar_url)
    lh = 9.6
    for i, line in enumerate(lines):
        body.append(
            f'<text x="{px0 + pw / 2}" y="{py0 + 36 + i * lh}" fill="{TEXT}" font-size="11.5" '
            f'text-anchor="middle" xml:space="preserve" opacity="0.9">{escape(line)}</text>'
        )
    # stats panel
    sx0, sy0, sw = 440, 80, 440
    body.append(f'<rect x="{sx0}" y="{sy0}" width="{sw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{sx0 + 12}" y="{sy0 + 18}" fill="{MUTED}" font-size="10">stats.json</text>')
    tiles = [
        ("current streak", f"{s['current']}", "days", True),
        ("longest streak", f"{s['longest']}", "days", False),
        ("contributions", f"{total:,}", "in the last year", True),
        ("active days", f"{s['active']}", f"/ {s['total_days']}", False),
        ("best day", f"{s['best']}", s["best_date"], False),
        ("avg / active day", f"{s['avg']:.1f}", "contributions", False),
    ]
    tw, th = 200, 54
    for i, (label, val, unit, hi) in enumerate(tiles):
        tx = sx0 + 14 + (i % 2) * (tw + 12)
        ty = sy0 + 30 + (i // 2) * (th + 8)
        body.append(
            f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="6" fill="{BG}" stroke="{BORDER}"/>'
            f'<text x="{tx + 10}" y="{ty + 16}" fill="{MUTED}" font-size="10">$ {escape(label)}</text>'
            f'<text x="{tx + 10}" y="{ty + 42}" font-size="22" font-weight="700" fill="{GREEN if hi else TEXT}">'
            f'{escape(val)}<tspan fill="{MUTED}" font-size="10" font-weight="400" dx="6">{escape(unit)}</tspan></text>'
        )
    # monthly bars
    by = sy0 + 30 + 3 * (th + 8) + 4
    bh_area = ph - (by - sy0) - 30
    body.append(f'<text x="{sx0 + 14}" y="{by + 10}" fill="{MUTED}" font-size="10">$ contributions / month</text>')
    vals = list(s["months"].values())
    mx = max(vals) or 1
    bw, bgap = 26, 9
    bx0 = sx0 + 14 + (sw - 28 - 12 * bw - 11 * bgap) / 2
    base = by + bh_area + 4
    for i, ((y, m), v) in enumerate(s["months"].items()):
        bh = max(2, (bh_area - 34) * v / mx)
        x = bx0 + i * (bw + bgap)
        color = GREEN if v == mx else "#238636"
        body.append(
            f'<rect x="{x}" y="{base - bh}" width="{bw}" height="{bh}" rx="2" fill="{color}">'
            f'<title>{v} in {dt.date(y, m, 1):%b %Y}</title>'
            f'<animate attributeName="height" from="0" to="{bh}" begin="{0.5 + i * 0.05:.2f}s" dur="0.5s" fill="freeze"/>'
            f'<animate attributeName="y" from="{base}" to="{base - bh}" begin="{0.5 + i * 0.05:.2f}s" dur="0.5s" fill="freeze"/>'
            f"</rect>"
            f'<text x="{x + bw / 2}" y="{base + 14}" fill="{MUTED}" font-size="9" text-anchor="middle">'
            f"{dt.date(y, m, 1):%b}</text>"
        )
        if v == mx:
            body.append(
                f'<text x="{x + bw / 2}" y="{base - bh - 5}" fill="{GREEN}" font-size="10" '
                f'text-anchor="middle">{v}</text>'
            )
    return window(w, h, f"{USER.lower()} — whoami", "".join(body))


def main():
    if not TOKEN:
        raise SystemExit("GH_TOKEN is required")
    avatar, total, weeks, days = fetch()
    s = stats(days)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "contributions.svg"), "w") as f:
        f.write(contributions_svg(total, weeks))
    with open(os.path.join(OUT, "whoami.svg"), "w") as f:
        f.write(whoami_svg(avatar, total, s))
    print(f"total={total} current={s['current']} longest={s['longest']} active={s['active']}")


if __name__ == "__main__":
    main()
