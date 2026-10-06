"""Extra profile cards: 3D contribution city, coding-hours clock + achievements, neofetch.

Imported by generate.py; shares its palette and window/prompt helpers.
"""
import datetime as dt
import math
import os
import re
from xml.sax.saxutils import escape

from generate import BG, BORDER, GOLD, GREEN, LEVELS, MUTED, PANEL, TEXT, USER, graphql, prompt, window

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
    body = [prompt(w / 2, 60, "./contributions.sh --city ulaanbaatar", "middle")]
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
    body.append(
        f'<text x="{w - 28}" y="110" fill="{GOLD}" font-size="12" font-weight="700" letter-spacing="2" '
        f'text-anchor="end">CODE CITY / ULAANBAATAR</text>'
        f'<text x="{w - 28}" y="128" fill="{MUTED}" font-size="10" text-anchor="end">one tower per day · height = contributions</text>'
    )
    return window(w, h, f"{USER.lower()} — code-city", "".join(body))


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


def achievements_svg(days, s, prof, shipped):
    w, h = 900, 400
    body = [prompt(w / 2, 60, "./achievements.sh", "middle")]
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
    tiers = [("bronze", "bronze"), ("silver", "silver"), ("gold", "gold")]
    # (icon, name, what is measured, value, bronze/silver/gold thresholds, unit); value None = a fixed badge
    badges = [
        ("🔥", "On Fire", "longest streak", s["longest"], [3, 7, 30], "days"),
        ("⚡", "Power Day", "best single day", s["best"], [10, 30, 60], "contribs"),
        ("🚀", "Shipper", "products live", shipped, [1, 3, 5], "sites"),
        ("🌐", "Polyglot", "languages used", len(prof["langs"]), [3, 6, 10], "langs"),
        ("🦉", "Night Owl", "commits 22:00–05:00", night, [5, 25, 100], "commits"),
        ("📅", "Consistent", "active days / year", s["active"], [30, 100, 200], "days"),
        ("🏗️", "Builder", "public repos", prof["repos"], [3, 10, 25], "repos"),
        ("🏔️", "UB Builder", "shipping from Ulaanbaatar", None, [], ""),
    ]
    bw, bh = (aw - 36) / 2, 60
    for i, (icon, name, desc, val, ths, unit) in enumerate(badges):
        bx = ax0 + 12 + (i % 2) * (bw + 12)
        by = py0 + 30 + (i // 2) * (bh + 7)
        if val is None:
            got, nxt, col = "home", None, GOLD
        else:
            got, nxt = _tier(val, list(zip(ths, [t[0] for t in tiers])))
            col = TIER_COLORS.get(got, BORDER)
        op = "1" if got else "0.45"
        prog = 1.0 if nxt is None else val / nxt
        detail = desc if val is None else f"{desc}: {val} {unit}"
        body.append(
            f'<g opacity="{op}"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="{BG}" stroke="{col}"/>'
            f'<text x="{bx + 22}" y="{by + 38}" font-size="24" text-anchor="middle">{icon}</text>'
            f'<text x="{bx + 44}" y="{by + 20}" fill="{TEXT}" font-size="12" font-weight="700">{escape(name)}'
            f'<tspan fill="{col}" font-size="9" font-weight="400" dx="6">{(got or "locked").upper()}</tspan></text>'
            f'<text x="{bx + 44}" y="{by + 35}" fill="{MUTED}" font-size="9.5">{escape(detail)}</text>'
            f'<rect x="{bx + 44}" y="{by + 44}" width="{bw - 58}" height="4" rx="2" fill="#21262d"/>'
            f'<rect x="{bx + 44}" y="{by + 44}" width="{(bw - 58) * min(1, prog):.1f}" height="4" rx="2" '
            f'fill="{col if got else MUTED}"/></g>'
        )
    return window(w, h, f"{USER.lower()} — achievements.sh", "".join(body))


# ---------------------------------------------------------------- neofetch

SOYOMBO = os.path.join(os.path.dirname(__file__), "..", "assets", "soyombo.svg")


def _soyombo(x0, y0, height, col):
    """The Soyombo (solid-sun variant, traced from Wikimedia Commons) as a nested <svg>."""
    with open(SOYOMBO) as f:
        src = f.read()
    vb = re.search(r'viewBox="([^"]+)"', src).group(1)
    d = re.search(r' d="([^"]+)"', src).group(1)
    _, _, vw, vh = (float(v) for v in vb.split())
    width = height * vw / vh
    return (
        f'<svg x="{x0:.1f}" y="{y0:.1f}" width="{width:.1f}" height="{height:.1f}" viewBox="{vb}">'
        f'<path fill="{col}" fill-rule="evenodd" d="{d}"/></svg>'
    )


def neofetch_svg(total, s, prof):
    w, h = 900, 390
    body = [prompt(w / 2, 60, "neofetch", "middle")]
    body.append(_soyombo(80, 92, 260, GOLD))
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
        ("Status", "shipping products"),
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


# ---------------------------------------------------------------- UB weather + proverb of the day

def fetch_weather():
    import json
    import urllib.request

    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=47.92&longitude=106.92"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day"
        "&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min&timezone=Asia%2FUlaanbaatar&forecast_days=1"
    )
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


# wttr.in-style icons; each is 5 lines
ICONS = {
    "sun": ["    \\   /    ", "     .-.     ", "  ― (   ) ―  ", "     `-’     ", "    /   \\    "],
    "moon": ["     _.._    ", "   .' .-'`   ", "  /  /       ", "  |  |       ", "   \\  '.___.;"],
    "partly": ["   \\  /      ", " _ /\"\".-.    ", "   \\_(   ).  ", "   /(___(__) ", "             "],
    "cloud": ["             ", "     .--.    ", "  .-(    ).  ", " (___.__)__) ", "             "],
    "fog": ["             ", " _ - _ - _ - ", "  _ - _ - _  ", " _ - _ - _ - ", "             "],
    "rain": ["     .-.     ", "    (   ).   ", "   (___(__)  ", "    ‚‘‚‘‚‘   ", "    ‚’‚’‚’   "],
    "snow": ["     .-.     ", "    (   ).   ", "   (___(__)  ", "    *  *  *  ", "   *  *  *   "],
    "storm": ["     .-.     ", "    (   ).   ", "   (___(__)  ", "    ⚡‘‘⚡‘‘  ", "    ‚’‚’⚡’  "],
}
ICON_COLORS = {"sun": "#f2c94c", "moon": "#c9d1d9", "partly": "#f2c94c", "cloud": "#8b949e",
               "fog": "#8b949e", "rain": "#58a6ff", "snow": "#e6edf3", "storm": "#d29922"}


def _wmo(code, is_day):
    if code == 0:
        return ("sun" if is_day else "moon"), "Clear"
    if code in (1, 2):
        return ("partly" if is_day else "moon"), "Partly cloudy"
    if code == 3:
        return "cloud", "Overcast"
    if code in (45, 48):
        return "fog", "Fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow", "Snow"
    if code >= 95:
        return "storm", "Thunderstorm"
    if code >= 51:
        return "rain", "Rain"
    return "cloud", "Cloudy"


PROVERBS = [
    ("Ажил хийвэл ам тосдоно.", "Work hard, and you will taste the butter."),
    ("Хичээвэл бүтнэ.", "Effort makes it happen."),
    ("Шантарвал шар ус, шамдвал алт.", "Give up and it is muddy water; persist and it is gold."),
    ("Нэг мод гал болдоггүй, нэг хүн айл болдоггүй.", "One log can't make a fire; one person can't make a home."),
    ("Ам алдвал барьж болдоггүй, агт алдвал барьж болдог.", "A runaway horse can be caught; a careless word cannot."),
    ("Хүн болох багаасаа, хүлэг болох унаганаасаа.", "A great person shows it as a child, a great steed as a foal."),
    ("Долоо хэмжиж нэг огтол.", "Measure seven times, cut once."),
    ("Зуун сонсохоор нэг үз.", "Better to see once than to hear a hundred times."),
    ("Усыг нь уувал ёсыг нь дага.", "Drink their water, follow their customs."),
    ("Хүн ахтай, дээл захтай.", "Every person has elders, as every deel has a collar."),
    ("Мянган бээрийн аян нэг алхмаас эхэлдэг.", "A thousand-mile journey starts with a single step."),
    ("Эрт босвол нэг юм үзнэ, орой унтвал нэг юм сонсоно.", "Rise early and you'll see something; stay up late and you'll hear something."),
    ("Явсан нохой яс зууна.", "The dog that roams finds a bone."),
    ("Цаг цагаараа байдаггүй, цахилдаг ногоороо байдаггүй.", "Times change, as the iris won't stay green forever."),
]


# who says the proverb today: a ger, a Bactrian camel or the classic cow (max 5 lines)
SAYERS = [
    [
        r"        \        _/\_",
        r"         \     /`    `\ ",
        r"             /__________\ ",
        r"             |  |    |  |",
        r"             |__|_[]_|__|",
    ],
    [
        r"        \       __    __",
        r"         \     /  \__/  \     _",
        r"            __/          \___/ o\ ",
        r"           /                  __/",
        r"           \_|_|-------|_|_|",
    ],
    [
        r"        \   ^__^",
        r"         \  (oo)\_______",
        r"            (__)\       )\/\ ",
        r"                ||----w |",
        r"                ||     ||",
    ],
]


def _wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


def ub_svg(weather):
    w, h = 900, 330
    body = [prompt(w / 2, 60, "curl wttr.in/ulaanbaatar && fortune mn | mongolsay", "middle")]
    # weather panel
    px0, py0, pw, ph = 20, 80, 420, 230
    body.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{px0 + 12}" y="{py0 + 18}" fill="{MUTED}" font-size="10">Weather report: Ulaanbaatar, Mongolia</text>')
    cur, daily = weather["current"], weather["daily"]
    kind, label = _wmo(cur["weather_code"], cur["is_day"])
    for i, line in enumerate(ICONS[kind]):
        body.append(
            f'<text x="{px0 + 16}" y="{py0 + 52 + i * 16}" fill="{ICON_COLORS[kind]}" font-size="14" '
            f'xml:space="preserve">{escape(line)}</text>'
        )
    t = cur["temperature_2m"]
    tcol = "#58a6ff" if t <= 0 else "#39c5cf" if t < 10 else GREEN if t < 22 else "#d29922" if t < 30 else "#f85149"
    hhmm = lambda iso: iso.split("T")[1]
    rows = [
        (label, None),
        (f"{t:+.0f}°C", f"feels {cur['apparent_temperature']:+.0f}°C"),
        (f"↓{daily['temperature_2m_min'][0]:+.0f}°  ↑{daily['temperature_2m_max'][0]:+.0f}°C", None),
        (f"{cur['wind_speed_10m']:.0f} km/h wind", f"{cur['relative_humidity_2m']}% hum"),
        (f"☀ {hhmm(daily['sunrise'][0])}  ☾ {hhmm(daily['sunset'][0])}", None),
    ]
    tx = px0 + 160
    for i, (a, b) in enumerate(rows):
        col = tcol if i == 1 else TEXT
        size = 22 if i == 1 else 13
        y = py0 + 50 + i * 26 + (4 if i > 1 else 0)
        extra = f'<tspan fill="{MUTED}" font-size="11" font-weight="400" dx="10">{escape(b)}</tspan>' if b else ""
        body.append(
            f'<text x="{tx}" y="{y}" fill="{col}" font-size="{size}" font-weight="{700 if i < 2 else 400}">'
            f"{escape(a)}{extra}</text>"
        )
    body.append(
        f'<text x="{px0 + 12}" y="{py0 + ph - 12}" fill="{MUTED}" font-size="10">'
        f"updated {cur['time'].replace('T', ' ')} UB time · open-meteo.com</text>"
    )
    # fortune | cowsay panel
    fx0, fw = px0 + pw + 20, w - (px0 + pw + 20) - 20
    body.append(f'<rect x="{fx0}" y="{py0}" width="{fw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<text x="{fx0 + 12}" y="{py0 + 18}" fill="{MUTED}" font-size="10">proverb of the day</text>')
    today = dt.datetime.now(TZ).date()
    mn, en = PROVERBS[today.toordinal() % len(PROVERBS)]
    text = _wrap(mn, 34) + [""] + _wrap(en, 34)
    width = max(len(l) for l in text)
    bs = "\\"
    bubble = [" " + "_" * (width + 2)]
    for i, l in enumerate(text):
        lo, hi = ("/", bs) if i == 0 else (bs, "/") if i == len(text) - 1 else ("|", "|")
        bubble.append(f"{lo} {l.ljust(width)} {hi}")
    bubble.append(" " + "-" * (width + 2))
    cow = SAYERS[today.toordinal() % len(SAYERS)]
    fs, lh = 11, 13
    for i, l in enumerate(bubble + cow):
        y = py0 + 38 + i * lh
        is_mn = 0 < i <= len(_wrap(mn, 34))
        col = GREEN if is_mn else (TEXT if i < len(bubble) else MUTED)
        # each line types in left-to-right, staggered
        lw = len(l) * fs * 0.6
        body.append(
            f'<clipPath id="f{i}"><rect x="{fx0 + 14}" y="{y - lh}" height="{lh + 3}" width="{lw + 4}">'
            f'<animate attributeName="width" from="0" to="{lw + 4}" begin="{0.2 + i * 0.12:.2f}s" dur="0.4s" fill="freeze"/>'
            f'</rect></clipPath>'
            f'<text x="{fx0 + 14}" y="{y}" fill="{col}" font-size="{fs}" xml:space="preserve" '
            f'textLength="{lw:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'clip-path="url(#f{i})">{escape(l)}</text>'
        )
    return window(w, h, f"{USER.lower()} — ub.sh", "".join(body))


# ---------------------------------------------------------------- projects (live screenshots)

# screenshots come from scripts/screenshots.sh; `own` = False marks a team repo owned by someone else
PROJECTS = [
    {"key": "sporthub", "host": "sporthub-eight.vercel.app", "name": "SportHub Mongolia",
     "tagline": "One membership. Every sport.", "own": True, "featured": True,
     "tree": [("backend", "NestJS · PostgreSQL"), ("web", "React · Vite · TypeScript"),
              ("admin", "Next.js"), ("deploy", "Railway · Vercel")]},
    {"key": "100ail", "host": "100ail.vercel.app", "name": "BarilgaHUB",
     "tagline": "Construction materials marketplace", "own": True,
     "stack": ["NestJS", "Next.js", "PostgreSQL"]},
    {"key": "gymhub", "host": "gymhubmn.vercel.app", "name": "GymHub",
     "tagline": "One membership for 30+ fitness clubs", "own": False,
     "stack": ["Next.js", "TypeScript"]},
    {"key": "sparkxp", "host": "spark-xp-web.vercel.app", "name": "SparkXP",
     "tagline": "Gamified English learning app", "own": False,
     "stack": ["React Native", "NestJS", "PostgreSQL"]},
]


def _data_uri(path, mime):
    import base64

    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _live(x, y, label="live"):
    return (
        f'<circle cx="{x}" cy="{y - 4}" r="3.5" fill="{GREEN}"><animate attributeName="opacity" '
        f'values="1;0.3;1" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="{x + 9}" y="{y}" font-size="11" fill="{GREEN}">{escape(label)}</text>'
    )


def _browser(x0, y0, bw, host, shot, cid):
    """A mini browser window around a 16:10 screenshot; returns (svg, height)."""
    iw = bw - 20
    ih = iw * 500 / 800
    out = [
        f'<rect x="{x0}" y="{y0}" width="{bw}" height="{ih + 42}" rx="8" fill="{BG}" stroke="{BORDER}"/>',
        "".join(f'<circle cx="{x0 + 16 + i * 12}" cy="{y0 + 15}" r="4" fill="{c}"/>'
                for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"])),
        f'<rect x="{x0 + 54}" y="{y0 + 6}" width="{bw - 64}" height="18" rx="9" fill="{PANEL}" stroke="{BORDER}"/>',
        f'<text x="{x0 + 66}" y="{y0 + 19}" font-size="10" fill="{MUTED}"><tspan fill="{GREEN}">https://</tspan>{escape(host)}</text>',
        f'<clipPath id="{cid}"><rect x="{x0 + 10}" y="{y0 + 32}" width="{iw}" height="{ih}" rx="4"/></clipPath>',
    ]
    if os.path.exists(shot):
        out.append(
            f'<image x="{x0 + 10}" y="{y0 + 32}" width="{iw}" height="{ih}" clip-path="url(#{cid})" '
            f'preserveAspectRatio="xMidYMin slice" href="{_data_uri(shot, "image/jpeg")}"/>'
        )
    out.append(f'<rect x="{x0 + 10}" y="{y0 + 32}" width="{iw}" height="{ih}" rx="4" fill="none" stroke="{BORDER}"/>')
    return "".join(out), ih + 42


def mission_svg(shots_dir):
    p = next(p for p in PROJECTS if p.get("featured"))
    w = 900
    body = [prompt(w / 2, 60, "./current-mission.sh", "middle")]
    shot, bh = _browser(20, 84, 500, p["host"], os.path.join(shots_dir, f"{p['key']}.jpg"), "mission")
    body.append(shot)
    x = 548
    body.append(
        f'<text x="{x}" y="108" fill="{GOLD}" font-size="11" font-weight="700" letter-spacing="2">MAIN PROJECT</text>'
        f'<text x="{x}" y="142" fill="{TEXT}" font-size="24" font-weight="700">{escape(p["name"])}</text>'
        f'<text x="{x}" y="170" fill="{TEXT}" font-size="15">{escape(p["tagline"])}</text>'
        + _live(x + 4, 200, f"LIVE · {p['host']}")
        + f'<text x="{x}" y="240" fill="{MUTED}" font-size="12">~/sporthub</text>'
    )
    for i, (k, v) in enumerate(p["tree"]):
        branch = "└──" if i == len(p["tree"]) - 1 else "├──"
        body.append(
            f'<text x="{x}" y="{266 + i * 24}" font-size="13" xml:space="preserve">'
            f'<tspan fill="{BORDER}">{branch} </tspan><tspan fill="{GREEN}">{k:<8}</tspan>'
            f'<tspan fill="{TEXT}">{escape(v)}</tspan></text>'
        )
    h = 84 + bh + 22
    return window(w, h, f"{USER.lower()} — current-mission.sh", "".join(body))


def projects_svg(shots_dir):
    rest = [p for p in PROJECTS if not p.get("featured")]
    w, row, gap = 900, 248, 16
    h = 80 + len(rest) * (row + gap) + 4
    body = [prompt(w / 2, 60, "ls ~/projects --live", "middle")]
    for i, p in enumerate(rest):
        y0 = 80 + i * (row + gap)
        body.append(f'<rect x="20" y="{y0}" width="{w - 40}" height="{row}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
        shot, _ = _browser(32, y0 + 12, 340, p["host"], os.path.join(shots_dir, f"{p['key']}.jpg"), f"shot{i}")
        body.append(shot)
        x = 404
        tag, tcol = ("own project", MUTED) if p["own"] else ("team project", GOLD)
        body.append(
            f'<text x="{x}" y="{y0 + 48}" fill="{TEXT}" font-size="22" font-weight="700">{escape(p["name"])}</text>'
            f'<text x="{w - 40}" y="{y0 + 46}" fill="{tcol}" font-size="11" text-anchor="end">● {tag}</text>'
            f'<text x="{x}" y="{y0 + 78}" fill="{MUTED}" font-size="14">{escape(p["tagline"])}</text>'
            + _live(x + 4, y0 + 112, p["host"])
        )
        cx = x
        for t in p["stack"]:
            tw = len(t) * 7.4 + 20
            body.append(
                f'<rect x="{cx}" y="{y0 + 140}" width="{tw:.0f}" height="24" rx="12" fill="{BG}" stroke="{BORDER}"/>'
                f'<text x="{cx + tw / 2:.0f}" y="{y0 + 156}" fill="{GREEN}" font-size="12" text-anchor="middle">{escape(t)}</text>'
            )
            cx += tw + 8
    return window(w, h, f"{USER.lower()} — projects", "".join(body))


# ---------------------------------------------------------------- footer

def footer_svg():
    from generate import bogd_khan

    w, h = 900, 200
    body = [
        bogd_khan(w, h),
        f'<text x="28" y="66" font-size="14" font-weight="700"><tspan fill="{GREEN}">{USER.lower()}@github</tspan>'
        f'<tspan fill="{MUTED}"> ~ $ </tspan><tspan fill="{TEXT}">echo "still building..."</tspan></text>',
        f'<text x="28" y="94" font-size="14" fill="{TEXT}">still building useful things from Ulaanbaatar.</text>',
        prompt(28, 130, ""),
    ]
    return window(w, h, f"{USER.lower()} — zsh", "".join(body))
