"""Extra profile cards: 3D contribution city, coding-hours clock + achievements, neofetch.

Imported by generate.py; shares its palette and window/prompt helpers.
"""
import datetime as dt
import math
import os
from xml.sax.saxutils import escape

from generate import BG, BORDER, GREEN, LEVELS, MUTED, PANEL, TEXT, USER, graphql, prompt, window

# commit timestamps are shown in the owner's local time
TZ = dt.timezone(dt.timedelta(hours=float(os.environ.get("TZ_OFFSET_HOURS", "8"))))


def fetch_profile():
    q = """query($login:String!){user(login:$login){createdAt followers{totalCount}
      repositories(first:50,ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false){totalCount nodes{name
        stargazerCount languages(first:10){edges{size node{name}}}
        defaultBranchRef{target{... on Commit{history(first:100){nodes{authoredDate author{user{login}}}}}}}}}}}"""
    u = graphql(q, {"login": USER})["user"]
    times = []
    for r in u["repositories"]["nodes"]:
        target = (r.get("defaultBranchRef") or {}).get("target") or {}
        for c in (target.get("history") or {}).get("nodes", []):
            if ((c.get("author") or {}).get("user") or {}).get("login", "").lower() == USER.lower():
                times.append(dt.datetime.fromisoformat(c["authoredDate"].replace("Z", "+00:00")).astimezone(TZ))
    langs = {e["node"]["name"] for r in u["repositories"]["nodes"] for e in r["languages"]["edges"]}
    return {
        "created": dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00")),
        "followers": u["followers"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "langs": langs,
        "times": times,
    }


# ---------------------------------------------------------------- 3D city

def _shade(hex_color, k):
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{max(0, min(255, int(v * k))):02x}" for v in (r, g, b))


def city_svg(total, weeks, s):
    w, h = 900, 440
    cw = 8.6  # half-width of a tile in screen space
    ox, oy = w / 2 + 40 - (len(weeks) - 7) / 2 * cw, 150
    days = [(wi, d) for wi, week in enumerate(weeks) for d in week["contributionDays"]]
    mx = max((d["contributionCount"] for _, d in days), default=1) or 1
    body = [prompt(w / 2, 60, "./city.sh --render 3d", "middle")]
    tiles = []
    for wi, d in days:
        row = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7
        tiles.append((wi, row, d["contributionCount"], d["date"]))
    # painter's order: back to front
    tiles.sort(key=lambda t: t[0] + t[1])
    for wi, row, n, date in tiles:
        cx = ox + (wi - row) * cw
        cy = oy + (wi + row) * cw * 0.5
        lvl = 0 if n == 0 else min(4, 1 + int(3.999 * n / mx))
        top = LEVELS[lvl] if n else "#1c2128"
        hgt = 3 + (math.sqrt(n / mx) * 110 if n else 0)
        left, right = _shade(top, 0.55), _shade(top, 0.75)
        p = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        t0 = (cx, cy - hgt)
        t1 = (cx + cw, cy + cw * 0.5 - hgt)
        t2 = (cx, cy + cw - hgt)
        t3 = (cx - cw, cy + cw * 0.5 - hgt)
        b1 = (cx + cw, cy + cw * 0.5)
        b2 = (cx, cy + cw)
        b3 = (cx - cw, cy + cw * 0.5)
        body.append(
            f'<g><title>{n} contributions on {date}</title>'
            f'<polygon points="{p([t3, t2, b2, b3])}" fill="{left}"/>'
            f'<polygon points="{p([t2, t1, b1, b2])}" fill="{right}"/>'
            f'<polygon points="{p([t0, t1, t2, t3])}" fill="{top}"/></g>'
        )
    # legend / summary
    lines = [
        ("total", f"{total:,} contributions"),
        ("tallest", f"{s['best']} on {s['best_date']}"),
        ("streak", f"{s['longest']} days best"),
    ]
    for i, (k, v) in enumerate(lines):
        y = 110 + i * 20
        body.append(
            f'<text x="28" y="{y}" font-size="12"><tspan fill="{MUTED}">{k:<8}</tspan>'
            f'<tspan fill="{GREEN}" font-weight="700" xml:space="preserve"> {escape(v)}</tspan></text>'
        )
    return window(w, h, f"{USER.lower()} — city.sh", "".join(body))


# ---------------------------------------------------------------- clock + achievements

def _tier(value, steps):
    """steps: [(threshold, name)] ascending; returns (unlocked_name|None, next_threshold|None)."""
    got, nxt = None, None
    for th, name in steps:
        if value >= th:
            got = name
        elif nxt is None:
            nxt = th
    return got, nxt


TIER_COLORS = {"bronze": "#cd7f32", "silver": "#c0c8d0", "gold": "#f2c94c"}


def habits_svg(days, s, prof):
    w, h = 900, 400
    body = [prompt(w / 2, 60, "./habits.sh", "middle")]
    times = prof["times"]
    hours = [0] * 24
    for t in times:
        hours[t.hour] += 1
    # clock panel
    px0, py0, pw, ph = 20, 80, 340, 300
    body.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{px0 + 12}" y="{py0 + 18}" fill="{MUTED}" font-size="10">commit-clock.txt</text>')
    cx, cy, r0, r1 = px0 + pw / 2, py0 + 158, 34, 104
    mx = max(hours) or 1
    for ring in (0.33, 0.66, 1.0):
        body.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r0 + (r1 - r0) * ring}" fill="none" stroke="{BORDER}" stroke-dasharray="2 4"/>'
        )
    peak = max(range(24), key=lambda i: hours[i])
    for hr in range(24):
        a0 = math.radians(hr * 15 - 90 + 1.5)
        a1 = math.radians((hr + 1) * 15 - 90 - 1.5)
        rr = r0 + (r1 - r0) * (hours[hr] / mx) if hours[hr] else r0 + 2
        pts = [
            (cx + r0 * math.cos(a0), cy + r0 * math.sin(a0)),
            (cx + rr * math.cos(a0), cy + rr * math.sin(a0)),
            (cx + rr * math.cos(a1), cy + rr * math.sin(a1)),
            (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1)),
        ]
        col = GREEN if hr == peak and hours[hr] else ("#238636" if hours[hr] else "#21262d")
        body.append(
            f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="{col}">'
            f"<title>{hr:02d}:00 — {hours[hr]} commits</title></polygon>"
        )
    for hr in (0, 6, 12, 18):
        a = math.radians(hr * 15 - 90)
        body.append(
            f'<text x="{cx + (r1 + 14) * math.cos(a):.1f}" y="{cy + (r1 + 14) * math.sin(a) + 4:.1f}" '
            f'fill="{MUTED}" font-size="10" text-anchor="middle">{hr:02d}</text>'
        )
    night = sum(hours[i] for i in list(range(22, 24)) + list(range(0, 5)))
    morning = sum(hours[i] for i in range(5, 10))
    n = len(times) or 1
    if night / n >= 0.25:
        persona = "Night owl 🦉"
    elif morning / n >= 0.25:
        persona = "Early bird 🐦"
    else:
        persona = "Daytime coder ☀️"
    body.append(f'<text x="{cx}" y="{cy - 2}" fill="{TEXT}" font-size="13" font-weight="700" text-anchor="middle">{peak:02d}:00</text>')
    body.append(f'<text x="{cx}" y="{cy + 13}" fill="{MUTED}" font-size="9" text-anchor="middle">peak</text>')
    body.append(
        f'<text x="{px0 + pw - 12}" y="{py0 + 18}" fill="{GREEN}" font-size="12" font-weight="700" '
        f'text-anchor="end">{escape(persona)}</text>'
    )

    # achievements panel
    ax0, aw = px0 + pw + 20, w - (px0 + pw + 20) - 20
    body.append(f'<rect x="{ax0}" y="{py0}" width="{aw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{ax0 + 12}" y="{py0 + 18}" fill="{MUTED}" font-size="10">achievements.json</text>')
    weekend = sum(d["contributionCount"] for d in days if dt.date.fromisoformat(d["date"]).weekday() >= 5)
    total = sum(d["contributionCount"] for d in days) or 1
    tiers = [("bronze", "bronze"), ("silver", "silver"), ("gold", "gold")]
    badges = [
        ("🔥", "On Fire", "longest streak", s["longest"], [3, 7, 30], "days"),
        ("⚡", "Power Day", "best single day", s["best"], [10, 30, 60], "contribs"),
        ("📅", "Consistent", "active days / year", s["active"], [30, 100, 200], "days"),
        ("🦉", "Night Owl", "commits 22:00–05:00", night, [5, 25, 100], "commits"),
        ("🌐", "Polyglot", "languages used", len(prof["langs"]), [3, 6, 10], "langs"),
        ("🏗️", "Builder", "public repos", prof["repos"], [3, 10, 25], "repos"),
        ("🎮", "Weekend Warrior", "weekend share", round(100 * weekend / total), [15, 25, 40], "%"),
        ("⭐", "Starstruck", "stars earned", prof["stars"], [1, 10, 50], "stars"),
    ]
    bw, bh = (aw - 36) / 2, 60
    for i, (icon, name, desc, val, ths, unit) in enumerate(badges):
        bx = ax0 + 12 + (i % 2) * (bw + 12)
        by = py0 + 30 + (i // 2) * (bh + 7)
        got, nxt = _tier(val, list(zip(ths, [t[0] for t in tiers])))
        col = TIER_COLORS.get(got, BORDER)
        op = "1" if got else "0.45"
        prog = 1.0 if nxt is None else val / nxt
        body.append(
            f'<g opacity="{op}"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="{BG}" stroke="{col}"/>'
            f'<text x="{bx + 22}" y="{by + 38}" font-size="24" text-anchor="middle">{icon}</text>'
            f'<text x="{bx + 44}" y="{by + 20}" fill="{TEXT}" font-size="12" font-weight="700">{escape(name)}'
            f'<tspan fill="{col}" font-size="9" font-weight="400" dx="6">{(got or "locked").upper()}</tspan></text>'
            f'<text x="{bx + 44}" y="{by + 35}" fill="{MUTED}" font-size="9.5">{escape(desc)}: {val} {unit}</text>'
            f'<rect x="{bx + 44}" y="{by + 44}" width="{bw - 58}" height="4" rx="2" fill="#21262d"/>'
            f'<rect x="{bx + 44}" y="{by + 44}" width="{(bw - 58) * min(1, prog):.1f}" height="4" rx="2" '
            f'fill="{col if got else MUTED}"/></g>'
        )
    return window(w, h, f"{USER.lower()} — habits.sh", "".join(body))


# ---------------------------------------------------------------- neofetch

def _soyombo(x0, y0, sc, col):
    """Simplified Soyombo symbol built from primitives (fire, sun, moon, triangles, bars, taijitu, pillars)."""
    g = lambda v: v * sc
    parts = [
        # fire: three tongues
        f'<path d="M{x0 + g(50)},{y0} C{x0 + g(58)},{y0 + g(12)} {x0 + g(58)},{y0 + g(20)} {x0 + g(50)},{y0 + g(28)} '
        f'C{x0 + g(42)},{y0 + g(20)} {x0 + g(42)},{y0 + g(12)} {x0 + g(50)},{y0}Z"/>',
        f'<path d="M{x0 + g(38)},{y0 + g(10)} C{x0 + g(44)},{y0 + g(18)} {x0 + g(44)},{y0 + g(24)} {x0 + g(42)},{y0 + g(30)} '
        f'C{x0 + g(36)},{y0 + g(26)} {x0 + g(35)},{y0 + g(18)} {x0 + g(38)},{y0 + g(10)}Z"/>',
        f'<path d="M{x0 + g(62)},{y0 + g(10)} C{x0 + g(56)},{y0 + g(18)} {x0 + g(56)},{y0 + g(24)} {x0 + g(58)},{y0 + g(30)} '
        f'C{x0 + g(64)},{y0 + g(26)} {x0 + g(65)},{y0 + g(18)} {x0 + g(62)},{y0 + g(10)}Z"/>',
        # sun
        f'<circle cx="{x0 + g(50)}" cy="{y0 + g(40)}" r="{g(8)}"/>',
        # moon (crescent)
        f'<path d="M{x0 + g(36)},{y0 + g(52)} A{g(14)},{g(10)} 0 0 0 {x0 + g(64)},{y0 + g(52)} '
        f'A{g(14)},{g(6)} 0 0 1 {x0 + g(36)},{y0 + g(52)}Z"/>',
        # top triangle + bar
        f'<polygon points="{x0 + g(36)},{y0 + g(66)} {x0 + g(64)},{y0 + g(66)} {x0 + g(50)},{y0 + g(76)}"/>',
        f'<rect x="{x0 + g(36)}" y="{y0 + g(79)}" width="{g(28)}" height="{g(4)}"/>',
        # taijitu
        f'<circle cx="{x0 + g(50)}" cy="{y0 + g(98)}" r="{g(12)}" fill="none" stroke="{col}" stroke-width="{g(2)}"/>',
        f'<path d="M{x0 + g(50)},{y0 + g(86)} A{g(6)},{g(6)} 0 0 1 {x0 + g(50)},{y0 + g(98)} '
        f'A{g(6)},{g(6)} 0 0 0 {x0 + g(50)},{y0 + g(110)} A{g(12)},{g(12)} 0 0 1 {x0 + g(50)},{y0 + g(86)}Z"/>',
        # bottom bar + triangle
        f'<rect x="{x0 + g(36)}" y="{y0 + g(113)}" width="{g(28)}" height="{g(4)}"/>',
        f'<polygon points="{x0 + g(36)},{y0 + g(120)} {x0 + g(64)},{y0 + g(120)} {x0 + g(50)},{y0 + g(130)}"/>',
        # pillars
        f'<rect x="{x0 + g(26)}" y="{y0 + g(66)}" width="{g(5)}" height="{g(64)}"/>',
        f'<rect x="{x0 + g(69)}" y="{y0 + g(66)}" width="{g(5)}" height="{g(64)}"/>',
    ]
    return f'<g fill="{col}">{"".join(parts)}</g>'


def neofetch_svg(total, s, prof):
    w, h = 900, 370
    body = [prompt(w / 2, 60, "neofetch", "middle")]
    body.append(_soyombo(70, 88, 1.65, "#f2c94c"))
    now = dt.datetime.now(dt.timezone.utc)
    months = (now.year - prof["created"].year) * 12 + now.month - prof["created"].month
    uptime = f"{months // 12} years, {months % 12} months" if months >= 12 else f"{months} months"
    info = [
        ("OS", "Mongolia 🇲🇳"),
        ("Host", "github.com/" + USER),
        ("Kernel", "Full-stack developer"),
        ("Uptime", uptime + " on GitHub"),
        ("Packages", f"{prof['repos']} public repos"),
        ("Shell", "zsh"),
        ("Stack", "TypeScript · Next.js · NestJS"),
        ("Also", "Python · Unity · C#"),
        ("Commits", f"{total:,} in the last year"),
        ("Streak", f"{s['current']} current / {s['longest']} best"),
    ]
    x0, y0 = 300, 96
    title = f"{USER.lower()}@github"
    body.append(f'<text x="{x0}" y="{y0}" font-size="15" font-weight="700" fill="{GREEN}">{title}</text>')
    body.append(f'<text x="{x0}" y="{y0 + 14}" font-size="13" fill="{MUTED}">{"-" * len(title)}</text>')
    for i, (k, v) in enumerate(info):
        body.append(
            f'<text x="{x0}" y="{y0 + 36 + i * 19}" font-size="13">'
            f'<tspan fill="{GREEN}" font-weight="700">{k}</tspan><tspan fill="{TEXT}">: {escape(v)}</tspan></text>'
        )
    palette = ["#484f58", "#f85149", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#e6edf3"]
    for i, c in enumerate(palette):
        body.append(f'<rect x="{x0 + i * 26}" y="{y0 + 36 + len(info) * 19 - 6}" width="24" height="14" fill="{c}"/>')
    return window(w, h, f"{USER.lower()} — neofetch", "".join(body))
