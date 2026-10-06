"""Generate terminal-style SVG cards for the GitHub profile README.

Outputs:
  assets/contributions.svg  - `./contributions.sh` heatmap of the last year
  assets/whoami.svg         - `whoami` panel: ASCII portrait + stats + monthly bars
  assets/header.svg         - block-letter name banner with a typing tagline
  assets/activity.svg       - `git log` of recent commits + language breakdown
  assets/city.svg, habits.svg, neofetch.svg - see extras.py

Requires env GH_TOKEN (or GITHUB_TOKEN) and optionally GH_USER.
"""
import datetime as dt
import io
import json
import os
import urllib.request
from collections import OrderedDict
from xml.sax.saxutils import escape

from PIL import Image, ImageFilter, ImageOps

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


def fetch_repos():
    q = """query($login:String!){user(login:$login){repositories(first:30,ownerAffiliations:OWNER,
      privacy:PUBLIC,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){nodes{name
        languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}
        defaultBranchRef{target{... on Commit{history(first:15){nodes{abbreviatedOid messageHeadline
          committedDate additions deletions author{user{login}}}}}}}}}}}"""
    return graphql(q, {"login": USER})["user"]["repositories"]["nodes"]


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


PORTRAIT_SRC = os.path.join(OUT, "portrait-source.png")


def ascii_portrait(avatar_url, cols=120, rows=72):
    """Return rows of (char, brightness) pairs, from a face-cropped source if present."""
    if os.path.exists(PORTRAIT_SRC):
        img = Image.open(PORTRAIT_SRC)
    else:
        with urllib.request.urlopen(avatar_url) as r:
            img = Image.open(io.BytesIO(r.read()))
    img = img.convert("L").filter(ImageFilter.UnsharpMask(2, 180, 2))
    img = ImageOps.equalize(img).point(lambda v: int(255 * (v / 255) ** 0.75))  # lift shadows in the hair
    img = img.resize((cols, rows), Image.LANCZOS)
    # bright pixels -> dense glyphs, since the card background is dark
    ramp = " .'`^\",:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
    px = img.load()
    return [
        [(ramp[max(1, px[x, y] * (len(ramp) - 1) // 255)], px[x, y]) for x in range(cols)]
        for y in range(rows)
    ]


def whoami_svg(avatar_url, total, s):
    w, h = 900, 470
    body = [prompt(w / 2, 60, "whoami", "middle")]
    # portrait panel
    px0, py0, pw, ph = 20, 80, 400, 370
    body.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{px0 + 12}" y="{py0 + 18}" fill="{MUTED}" font-size="10">portrait.txt</text>')
    lines = ascii_portrait(avatar_url)
    lh = 4.8

    def tint(v):
        # dark -> green midtones (hair) -> light gray highlights (skin)
        v = v // 12 * 12 + 6  # quantize so neighbouring glyphs share one <tspan>
        t = v / 255
        lo, mid, hi = (30, 36, 44), (35, 134, 54), (230, 237, 243)
        a, b, k = (lo, mid, t / 0.45) if t < 0.45 else (mid, hi, (t - 0.45) / 0.55)
        return "#" + "".join(f"{int(a[i] + (b[i] - a[i]) * k):02x}" for i in range(3))

    for i, line in enumerate(lines):
        runs = []
        for ch, v in line:
            c = tint(v)
            if runs and runs[-1][0] == c:
                runs[-1][1].append(ch)
            else:
                runs.append((c, [ch]))
        spans = "".join(f'<tspan fill="{c}">{escape("".join(chs))}</tspan>' for c, chs in runs)
        body.append(
            f'<text x="{px0 + pw / 2}" y="{py0 + 27 + i * lh}" font-size="5.3" '
            f'text-anchor="middle" xml:space="preserve">{spans}</text>'
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


# ANSI-Shadow-style glyphs drawn as pixel blocks; the shadow is rendered as an offset copy
GLYPHS = {
    "A": [" ##### ", "##   ##", "#######", "##   ##", "##   ##"],
    "B": ["###### ", "##   ##", "###### ", "##   ##", "###### "],
    "H": ["##   ##", "##   ##", "#######", "##   ##", "##   ##"],
    "I": ["##", "##", "##", "##", "##"],
    "K": ["##   ##", "##  ## ", "#####  ", "##  ## ", "##   ##"],
    "N": ["###   ##", "####  ##", "## ## ##", "##  ####", "##   ###"],
    "S": [" ######", "##     ", " ##### ", "     ##", "###### "],
    "T": ["########", "   ##   ", "   ##   ", "   ##   ", "   ##   "],
}

TAGLINES = [
    "Full-stack developer",
    "Building marketplaces with NestJS + Next.js",
    "Shipping web apps, maps & games",
    "Always learning, always shipping",
]


def header_svg(name="BATSAIKHAN"):
    px, gap = 11, 0
    cols = sum(len(GLYPHS[c][0]) + 1 for c in name) - 1
    w = 900
    gx0 = (w - cols * px) / 2
    gy0 = 40
    shadow, front = [], []
    x = 0
    for c in name:
        g = GLYPHS[c]
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    cx, cy = gx0 + (x + k) * px, gy0 + r * px
                    shadow.append(f'<rect x="{cx + 4}" y="{cy + 4}" width="{px}" height="{px}"/>')
                    front.append(f'<rect x="{cx}" y="{cy}" width="{px + 0.5}" height="{px + 0.5}"/>')
        x += len(g[0]) + 1
    h = 190
    ty = gy0 + 5 * px + 50
    # each tagline types in, holds, then erases; lines are chained so exactly one is visible at a time
    per = 4.0
    total = per * len(TAGLINES)
    lines = []
    for i, t in enumerate(TAGLINES):
        tw = len(t) * 9.65 + 4
        start, end = i * per / total, (i + 1) * per / total
        typed = start + 1.4 / total
        hold = end - 0.6 / total
        kt = f"0;{start:.4f};{typed:.4f};{hold:.4f};{end:.4f};1"
        lines.append(
            f'<clipPath id="c{i}"><rect x="{(w - tw) / 2}" y="{ty - 18}" height="26" width="0">'
            f'<animate attributeName="width" dur="{total}s" repeatCount="indefinite" '
            f'keyTimes="{kt}" values="0;0;{tw};{tw};0;0"/></rect></clipPath>'
            f'<text x="{w / 2}" y="{ty}" fill="{TEXT}" font-size="16" text-anchor="middle" '
            f'clip-path="url(#c{i})">{escape(t)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">'
        f'<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" x1="{gx0}" x2="{gx0 + cols * px}" y1="0" y2="0"><stop offset="0" stop-color="#2ea043"/>'
        f'<stop offset="0.5" stop-color="#56d364"/><stop offset="1" stop-color="#2ea043"/></linearGradient>'
        f'<linearGradient id="shine"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="#fff" stop-opacity="0.55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f'</linearGradient><clipPath id="letters">{"".join(front)}</clipPath></defs>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<g fill="#0e4429">{"".join(shadow)}</g><g fill="url(#g)">{"".join(front)}</g>'
        f'<g clip-path="url(#letters)"><rect x="-200" y="0" width="160" height="{h}" fill="url(#shine)">'
        f'<animate attributeName="x" values="-200;{w + 40}" dur="3.5s" repeatCount="indefinite"/></rect></g>'
        f'{"".join(lines)}</svg>'
    )


def rel_time(iso):
    d = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    for unit, sec in (("y", 31536000), ("mo", 2592000), ("d", 86400), ("h", 3600), ("m", 60)):
        if d.total_seconds() >= sec:
            return f"{int(d.total_seconds() // sec)}{unit} ago"
    return "just now"


def activity_svg(repos):
    w, h = 900, 330
    body = [prompt(w / 2, 60, "git log --all --oneline | head", "middle")]
    # git log panel
    lx0, ly0, lw, lh = 20, 80, 540, 230
    body.append(f'<rect x="{lx0}" y="{ly0}" width="{lw}" height="{lh}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{lx0 + 12}" y="{ly0 + 18}" fill="{MUTED}" font-size="10">recent-commits.log</text>')
    commits = []
    for r in repos:
        if r["name"].lower() == USER.lower():
            continue
        target = (r.get("defaultBranchRef") or {}).get("target") or {}
        for c in (target.get("history") or {}).get("nodes", []):
            mine = ((c.get("author") or {}).get("user") or {}).get("login", "").lower() == USER.lower()
            if mine and not c["messageHeadline"].startswith("Merge "):
                commits.append((c["committedDate"], r["name"], c))
    commits.sort(key=lambda t: t[0], reverse=True)
    for i, (date, repo, c) in enumerate(commits[:9]):
        y = ly0 + 42 + i * 20
        msg = c["messageHeadline"]
        room = 40 - len(repo)
        if len(msg) > room:
            msg = msg[: room - 1] + "…"
        body.append(
            f'<text x="{lx0 + 14}" y="{y}" font-size="12" xml:space="preserve">'
            f'<tspan fill="#d29922">{c["abbreviatedOid"]}</tspan> '
            f'<tspan fill="#58a6ff">{escape(repo)}</tspan><tspan fill="{MUTED}">:</tspan> '
            f'<tspan fill="{TEXT}">{escape(msg)}</tspan></text>'
            f'<text x="{lx0 + lw - 14}" y="{y}" font-size="11" fill="{MUTED}" text-anchor="end">'
            f'<tspan fill="{GREEN}">+{c["additions"]}</tspan> <tspan fill="#f85149">-{c["deletions"]}</tspan>'
            f'  {rel_time(date)}</text>'
        )
    if not commits:
        body.append(f'<text x="{lx0 + 14}" y="{ly0 + 42}" font-size="12" fill="{MUTED}">no public commits yet</text>')
    # languages panel
    rx0, rw = lx0 + lw + 20, w - (lx0 + lw + 20) - 20
    body.append(f'<rect x="{rx0}" y="{ly0}" width="{rw}" height="{lh}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{rx0 + 12}" y="{ly0 + 18}" fill="{MUTED}" font-size="10">languages.sh</text>')
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or MUTED
    tot = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:6]
    # stacked bar
    bx, bw = rx0 + 14, rw - 28
    acc = 0
    body.append(f'<clipPath id="bar"><rect x="{bx}" y="{ly0 + 32}" width="{bw}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">')
    body.append(f'<rect x="{bx}" y="{ly0 + 32}" width="{bw}" height="10" fill="{BORDER}"/>')
    for n, v in top:
        seg = bw * v / tot
        body.append(f'<rect x="{bx + acc}" y="{ly0 + 32}" width="{seg}" height="10" fill="{colors[n]}"/>')
        acc += seg
    body.append("</g>")
    for i, (n, v) in enumerate(top):
        y = ly0 + 68 + i * 26
        pct = 100 * v / tot
        body.append(
            f'<circle cx="{bx + 5}" cy="{y - 4}" r="5" fill="{colors[n]}"/>'
            f'<text x="{bx + 16}" y="{y}" font-size="12" fill="{TEXT}">{escape(n)}</text>'
            f'<text x="{bx + bw}" y="{y}" font-size="12" fill="{MUTED}" text-anchor="end">{pct:.1f}%</text>'
            f'<rect x="{bx + 16}" y="{y + 5}" width="{(bw - 16) * pct / 100}" height="3" rx="1.5" fill="{colors[n]}" opacity="0.6"/>'
        )
    return window(w, h, f"{USER.lower()} — activity", "".join(body))


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
    with open(os.path.join(OUT, "header.svg"), "w") as f:
        f.write(header_svg())
    with open(os.path.join(OUT, "activity.svg"), "w") as f:
        f.write(activity_svg(fetch_repos()))

    import extras  # imported late: extras reuses this module's helpers

    prof = extras.fetch_profile()
    for name, svg in (
        ("city.svg", extras.city_svg(total, weeks, s)),
        ("habits.svg", extras.habits_svg(days, s, prof)),
        ("neofetch.svg", extras.neofetch_svg(total, s, prof)),
    ):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)
    print(f"total={total} current={s['current']} longest={s['longest']} active={s['active']}")


if __name__ == "__main__":
    main()
