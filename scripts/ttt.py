"""Community tic-tac-toe played through GitHub issues.

Visitors are X and open an issue titled `ttt: move <0-8>`; the bot answers as O.
Usage:
  python scripts/ttt.py move <cell> <github-login>   # apply a move, write comment.md, update README
  python scripts/ttt.py render                       # only re-render README section + cell images
"""
import json
import os
import random
import re
import sys
import urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "game", "ttt.json")
README = os.path.join(ROOT, "README.md")
CELLS = os.path.join(ROOT, "assets", "ttt")
REPO = os.environ.get("GITHUB_REPOSITORY", "Batsaikhann/Batsaikhann")
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
START, END = "<!-- TTT:START -->", "<!-- TTT:END -->"


def load():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"board": [""] * 9, "players": [], "stats": {"X": 0, "O": 0, "draw": 0}, "last": None, "log": []}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)


def winner(b):
    for a, c, d in LINES:
        if b[a] and b[a] == b[c] == b[d]:
            return b[a]
    return "draw" if all(b) else None


def minimax(b, me):
    w = winner(b)
    if w == "O":
        return 1, None
    if w == "X":
        return -1, None
    if w == "draw":
        return 0, None
    best = (-2, None) if me == "O" else (2, None)
    for i in range(9):
        if not b[i]:
            b[i] = me
            score, _ = minimax(b, "X" if me == "O" else "O")
            b[i] = ""
            if (me == "O" and score > best[0]) or (me == "X" and score < best[0]):
                best = (score, i)
    return best


def bot_move(b):
    free = [i for i in range(9) if not b[i]]
    # a little randomness so the bot is beatable
    if random.random() < 0.3:
        return random.choice(free)
    return minimax(list(b), "O")[1]


def cell_svg(kind, idx):
    base = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80">'
        '<rect x="2" y="2" width="76" height="76" rx="10" fill="#161b22" stroke="#30363d" stroke-width="2"/>'
    )
    if kind == "X":
        body = ('<path d="M24 24 L56 56 M56 24 L24 56" stroke="#3fb950" stroke-width="8" stroke-linecap="round"/>')
    elif kind == "O":
        body = '<circle cx="40" cy="40" r="17" fill="none" stroke="#39c5cf" stroke-width="8"/>'
    else:
        body = (
            f'<text x="40" y="47" font-family="ui-monospace,Menlo,monospace" font-size="20" fill="#484f58" '
            f'text-anchor="middle">{idx}</text>'
        )
    return base + body + "</svg>"


def render(st):
    os.makedirs(CELLS, exist_ok=True)
    for kind in ("X", "O"):
        with open(os.path.join(CELLS, f"{kind.lower()}.svg"), "w") as f:
            f.write(cell_svg(kind, 0))
    for i in range(9):
        with open(os.path.join(CELLS, f"empty-{i}.svg"), "w") as f:
            f.write(cell_svg("", i))
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            i = r * 3 + c
            v = st["board"][i]
            if v:
                cells.append(f'<img src="assets/ttt/{v.lower()}.svg" width="64" alt="{v}"/>')
            else:
                q = urllib.parse.urlencode(
                    {"title": f"ttt: move {i}", "body": "Just press **Create** — the bot plays your move and answers within a minute."}
                )
                cells.append(
                    f'<a href="https://github.com/{REPO}/issues/new?{q}">'
                    f'<img src="assets/ttt/empty-{i}.svg" width="64" alt="play {i}"/></a>'
                )
        rows.append("".join(cells))
    s = st["stats"]
    recent = ", ".join(f"[@{p}](https://github.com/{p})" for p in st["players"][-5:][::-1]) or "nobody yet — be the first!"
    last = f"<sub>last game: <b>{st['last']}</b></sub><br/>" if st["last"] else ""
    section = "\n".join([
        START,
        '<div align="center">',
        "",
        "```console",
        f"{REPO.split('/')[0].lower()}@github ~ $ ./tictactoe.sh --vs visitors",
        "```",
        "",
        "<sub>you are <b>X</b> · click an empty square to play · the bot is <b>O</b></sub><br/><br/>",
        "<br/>".join(rows),
        "<br/><br/>",
        last,
        f"<sub>🟢 visitors won <b>{s['X']}</b> · 🔵 bot won <b>{s['O']}</b> · draws <b>{s['draw']}</b></sub><br/>",
        f"<sub>recent players: {recent}</sub>",
        "",
        "</div>",
        END,
    ])
    with open(README) as f:
        text = f.read()
    if START in text:
        text = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: section, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    with open(README, "w") as f:
        f.write(text)


def finish(st, result):
    if result == "draw":
        st["stats"]["draw"] += 1
        st["last"] = "draw 🤝"
    elif result == "X":
        st["stats"]["X"] += 1
        st["last"] = "visitors won 🎉"
    else:
        st["stats"]["O"] += 1
        st["last"] = "bot won 🤖"
    st["board"] = [""] * 9


def move(cell, login):
    st = load()
    b = st["board"]
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        login = "someone"
    if not 0 <= cell <= 8 or b[cell]:
        msg = f"Square **{cell}** is already taken — pick an empty one on the [profile](https://github.com/{REPO})."
        return msg, False
    b[cell] = "X"
    st["players"] = [p for p in st["players"] if p != login] + [login]
    lines = [f"@{login} played **X** on square **{cell}**."]
    result = winner(b)
    if not result:
        o = bot_move(b)
        b[o] = "O"
        lines.append(f"🤖 The bot answered with **O** on square **{o}**.")
        result = winner(b)
    if result:
        lines.append({"X": "🎉 **Visitors win!**", "O": "🤖 **The bot wins.**", "draw": "🤝 **It's a draw.**"}[result])
        lines.append("A new game has started.")
        finish(st, result)
    lines.append(f"\n[Back to the board →](https://github.com/{REPO})")
    save(st)
    render(st)
    return "\n".join(lines), True


def main():
    if sys.argv[1] == "render":
        render(load())
        return
    cell = int(sys.argv[2]) if sys.argv[2].isdigit() else -1
    msg, _ = move(cell, sys.argv[3])
    with open(os.path.join(ROOT, "comment.md"), "w") as f:
        f.write(msg)
    print(msg)


if __name__ == "__main__":
    main()
