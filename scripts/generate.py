"""Generate the terminal-style SVG cards of the BATSAIKHANN OS profile README.

Outputs (assets/):
  hero.svg         banner: pixel name, typing tagline, Mongolian-script name, matrix rain
  whoami.svg       ASCII portrait + identity
  shipping.svg     `git log --shipping`: latest real commits + language breakdown
  neofetch.svg, mission.svg, city.svg, achievements.svg, projects.svg, ub.svg, footer.svg - see extras.py
  light/*.svg      the same cards recoloured for GitHub's light theme

Requires env GH_TOKEN (or GITHUB_TOKEN) and optionally GH_USER.
"""
import datetime as dt
import io
import json
import os
import re
import urllib.request
from collections import OrderedDict
from xml.sax.saxutils import escape

from PIL import Image, ImageFilter, ImageOps

USER = os.environ.get("GH_USER", "Batsaikhann")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
GREEN = "#3fb950"
GOLD = "#f2c94c"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
# light-theme counterparts (GitHub light palette); every card is also written to assets/light/
LIGHT = {
    "#0d1117": "#ffffff", "#161b22": "#f6f8fa", "#1c2128": "#eaeef2", "#21262d": "#eaeef2",
    "#30363d": "#d0d7de", "#484f58": "#8c959f", "#8b949e": "#59636e", "#c0c8d0": "#8c959f",
    "#c9d1d9": "#1f2328", "#e6edf3": "#1f2328", "#ffffff0d": "#1f232814",
    "#3fb950": "#1a7f37", "#2ea043": "#1a7f37", "#56d364": "#2da44e", "#7ee787": "#116329",
    "#1a7f37": "#4ac26b", "#238636": "#2da44e",
    "#0e4429": "#9be9a8", "#006d32": "#40c463", "#26a641": "#30a14e", "#39d353": "#216e39",
    "#58a6ff": "#0969da", "#d29922": "#9a6700", "#f85149": "#cf222e", "#39c5cf": "#1b7c83",
    "#bc8cff": "#8250df", "#f2c94c": "#bf8700",
}
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"


def to_light(svg):
    return re.sub(r"#[0-9a-fA-F]{3,8}\b", lambda m: LIGHT.get(m.group(0).lower(), m.group(0)), svg)


def write_card(name, svg):
    """Write the dark card to assets/ and its light twin to assets/light/."""
    os.makedirs(os.path.join(OUT, "light"), exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(svg)
    with open(os.path.join(OUT, "light", name), "w") as f:
        f.write(to_light(svg))


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
      privacy:PUBLIC,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){nodes{name pushedAt
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


def whoami_svg(avatar_url, last_push=None):
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
    # identity panel
    sx0, sy0, sw = 440, 80, 440
    body.append(f'<rect x="{sx0}" y="{sy0}" width="{sw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{sx0 + 12}" y="{sy0 + 18}" fill="{MUTED}" font-size="10">identity.yml</text>')
    rows = [
        ("Name", "Batsaikhan", TEXT),
        ("Location", "Ulaanbaatar, Mongolia 🇲🇳", TEXT),
        ("Role", "Full-stack Developer", TEXT),
        ("Focus", "Web · Mobile · Systems", TEXT),
        ("Currently", "SportHub Mongolia", GOLD),
    ]
    if last_push:
        rows.append(("Last push", f"{last_push[0]} · {rel_time(last_push[1])}", TEXT))
    for i, (k, v, col) in enumerate(rows):
        y = sy0 + 62 + i * 40
        body.append(
            f'<text x="{sx0 + 24}" y="{y}" font-size="15" xml:space="preserve">'
            f'<tspan fill="{GREEN}" font-weight="700">{k:<10}</tspan><tspan fill="{col}">{escape(v)}</tspan></text>'
        )
    y = sy0 + 62 + len(rows) * 40
    body.append(
        f'<text x="{sx0 + 24}" y="{y}" font-size="15" xml:space="preserve">'
        f'<tspan fill="{GREEN}" font-weight="700">{"Status":<10}</tspan><tspan fill="{TEXT}">🚀 shipping</tspan>'
        f'<tspan fill="{GREEN}">.<animate attributeName="opacity" values="0;1;1;0" dur="1.8s" repeatCount="indefinite"/></tspan>'
        f'<tspan fill="{GREEN}">.<animate attributeName="opacity" values="0;0;1;0" dur="1.8s" repeatCount="indefinite"/></tspan>'
        f'<tspan fill="{GREEN}">.<animate attributeName="opacity" values="0;0;0;1;0" dur="1.8s" repeatCount="indefinite"/></tspan></text>'
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


def matrix_rain(w, h, cols=46, seed=8855):
    """Falling columns of Mongolian Cyrillic + code glyphs behind the banner."""
    import random

    rnd = random.Random(seed)  # fixed seed keeps the file stable between runs
    glyphs = "АБВГДЕЁЖЗИЙКЛМНОӨПРСТУҮФХЦЧШЩЪЫЬЭЮЯ0123456789{}<>/=;$#"
    fs = 12
    out = [f'<clipPath id="rain"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="12"/></clipPath><g clip-path="url(#rain)" font-size="{fs}">']
    for c in range(cols):
        x = 10 + c * (w - 20) / cols
        n = rnd.randint(8, 16)
        dur = rnd.uniform(4, 9)
        delay = -rnd.uniform(0, dur)
        chars = "".join(
            f'<tspan x="{x:.1f}" dy="{fs + 2}" fill="{"#7ee787" if i == n - 1 else "#1a7f37"}" '
            f'fill-opacity="{0.25 + 0.6 * i / n:.2f}">{escape(rnd.choice(glyphs))}</tspan>'
            for i in range(n)
        )
        span = n * (fs + 2)
        out.append(
            f'<text opacity="0.45">{chars}<animateTransform attributeName="transform" type="translate" '
            f'from="0 {-span}" to="0 {h}" dur="{dur:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite"/></text>'
        )
    out.append("</g>")
    return "".join(out)


def bogd_khan(w, h):
    """Bogd Khan Uul, the ridge south of Ulaanbaatar, as a quiet silhouette along the bottom edge."""
    import math

    def ridge(peaks, base, jag):
        pts = []
        for x in range(0, w + 1, 5):
            y = max(hh * max(0.0, 1 - abs(x - px) / pw) for px, hh, pw in peaks)
            y += jag * (math.sin(x / 9.0) + 0.6 * math.sin(x / 4.1 + 2))
            pts.append(f"{x},{base - max(0, y):.1f}")
        return " L".join(pts)

    far = ridge([(150, 34, 190), (380, 26, 160), (700, 36, 210), (880, 24, 140)], h - 26, 0.35)
    near = ridge([(70, 16, 130), (250, 26, 140), (430, 18, 120), (610, 46, 190), (790, 28, 150)], h - 14, 0.5)
    return (
        f'<clipPath id="ridge"><rect x="1" y="33" width="{w - 2}" height="{h - 34}" rx="12"/></clipPath>'
        f'<g clip-path="url(#ridge)">'
        f'<path d="M{far}" fill="none" stroke="{GOLD}" stroke-opacity="0.14" stroke-width="1"/>'
        f'<path d="M0,{h} L{near} L{w},{h} Z" fill="{PANEL}"/>'
        f'<path d="M{near}" fill="none" stroke="{GOLD}" stroke-opacity="0.4" stroke-width="1.2"/></g>'
    )


def _mongol_name(x, y, height, col):
    """The name in traditional Mongolian script, drawn in `col` through the PNG's alpha as a mask."""
    import base64

    path = os.path.join(OUT, "mongol-name.png")
    if not os.path.exists(path):
        return ""
    img = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", img.size, (255, 255, 255, 0))
    white.putalpha(img.getchannel("A"))  # white glyphs on transparent: a clean luminance mask
    buf = io.BytesIO()
    white.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    iw = img.width * height / img.height
    x0 = x - iw / 2
    return (
        f'<mask id="mn"><image x="{x0:.1f}" y="{y}" width="{iw:.1f}" height="{height}" href="{uri}"/></mask>'
        f'<rect x="{x0:.1f}" y="{y}" width="{iw:.1f}" height="{height}" fill="{col}" mask="url(#mn)"/>'
    )


def hero_svg(name="BATSAIKHAN"):
    w, h, px = 900, 190, 9.4
    cols = sum(len(GLYPHS[c][0]) + 1 for c in name) - 1
    gx0, gy0 = (w - cols * px) / 2, 40
    shadow, front = [], []
    x = 0
    for c in name:
        g = GLYPHS[c]
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    cx, cy = gx0 + (x + k) * px, gy0 + r * px
                    shadow.append(f'<rect x="{cx + 4:.1f}" y="{cy + 4:.1f}" width="{px}" height="{px}"/>')
                    front.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{px + 0.5}" height="{px + 0.5}"/>')
        x += len(g[0]) + 1
    # each tagline types in, holds, then erases; chained so exactly one is visible at a time
    ty, per = gy0 + 5 * px + 50, 4.0
    total = per * len(TAGLINES)
    lines = []
    for i, t in enumerate(TAGLINES):
        tw = len(t) * 9.65 + 4
        start, end = i * per / total, (i + 1) * per / total
        kt = f"0;{start:.4f};{start + 1.4 / total:.4f};{end - 0.6 / total:.4f};{end:.4f};1"
        lines.append(
            f'<clipPath id="t{i}"><rect x="{(w - tw) / 2:.1f}" y="{ty - 18}" height="26" width="0">'
            f'<animate attributeName="width" dur="{total}s" repeatCount="indefinite" '
            f'keyTimes="{kt}" values="0;0;{tw:.1f};{tw:.1f};0;0"/></rect></clipPath>'
            f'<text x="{w / 2}" y="{ty}" fill="{TEXT}" font-size="16" font-weight="700" text-anchor="middle" '
            f'clip-path="url(#t{i})">{escape(t)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">'
        f'<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" x1="{gx0}" x2="{gx0 + cols * px}" y1="0" y2="0">'
        f'<stop offset="0" stop-color="#2ea043"/><stop offset="0.5" stop-color="#56d364"/><stop offset="1" stop-color="#2ea043"/>'
        f'</linearGradient><linearGradient id="shine"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="#fff" stop-opacity="0.55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f'</linearGradient><clipPath id="letters">{"".join(front)}</clipPath></defs>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f"{matrix_rain(w, h)}"
        f'<g fill="#0e4429">{"".join(shadow)}</g><g fill="url(#g)">{"".join(front)}</g>'
        f'<g clip-path="url(#letters)"><rect x="-200" y="0" width="160" height="{h}" fill="url(#shine)">'
        f'<animate attributeName="x" values="-200;{w + 40}" dur="3.5s" repeatCount="indefinite"/></rect></g>'
        f'<rect x="{w / 2 - 260}" y="{ty - 22}" width="520" height="32" rx="6" fill="{BG}" fill-opacity="0.85"/>'
        f'{"".join(lines)}'
        f"{_mongol_name(46, 20, h - 40, GREEN)}</svg>"
    )


def rel_time(iso):
    d = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    for unit, sec in (("y", 31536000), ("mo", 2592000), ("d", 86400), ("h", 3600), ("m", 60)):
        if d.total_seconds() >= sec:
            return f"{int(d.total_seconds() // sec)}{unit} ago"
    return "just now"


def shipping_svg(repos):
    w, h = 900, 330
    body = [prompt(w / 2, 60, "git log --shipping", "middle")]
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
    return window(w, h, f"{USER.lower()} — shipping.log", "".join(body))


def main():
    if not TOKEN:
        raise SystemExit("GH_TOKEN is required")
    avatar, total, weeks, days = fetch()
    s = stats(days)
    repos = fetch_repos()
    pushed = [r for r in repos if r["name"].lower() != USER.lower()]
    last_push = None
    if pushed and pushed[0].get("pushedAt"):
        last_push = (pushed[0]["name"], pushed[0]["pushedAt"])
    write_card("hero.svg", hero_svg())
    write_card("whoami.svg", whoami_svg(avatar, last_push))
    write_card("shipping.svg", shipping_svg(repos))

    import extras  # imported late: extras reuses this module's helpers

    prof = extras.fetch_profile()
    shots = os.path.join(OUT, "shots")
    write_card("neofetch.svg", extras.neofetch_svg(total, s, prof))
    write_card("mission.svg", extras.mission_svg(shots))
    write_card("city.svg", extras.city_svg(total, weeks, s))
    write_card("achievements.svg", extras.achievements_svg(days, s, prof, len(extras.PROJECTS)))
    write_card("projects.svg", extras.projects_svg(shots))
    write_card("ub.svg", extras.ub_svg(extras.fetch_weather()))
    write_card("footer.svg", extras.footer_svg())
    print(f"total={total} current={s['current']} longest={s['longest']} active={s['active']}")


if __name__ == "__main__":
    main()
