#!/usr/bin/env python3
"""Generates the animated SVG assets and README.md of the GitHub profile from profile.json.

    python3 generate.py

Everything is plain SVG (SMIL animations), no JavaScript, no external services, so it
animates on GitHub exactly like in a browser. If a viewer does not support animation,
the SVGs fall back to their final, fully visible state.
"""
import json
import os
import re
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
FONT = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
C = dict(bg="#0d1117", panel="#161b22", chip="#21262d", line="#30363d", text="#e6edf3",
         dim="#8b949e", green="#3fb950", blue="#58a6ff", purple="#bc8cff", orange="#f0883e",
         yellow="#d29922", red="#ff7b72")


# ------------------------------------------------------------------ helpers
def f(x):
    return f"{x:.5f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def anim(attr, values, times, dur, calc="discrete"):
    """SMIL <animate> that loops forever."""
    return (f'<animate attributeName="{attr}" values="{";".join(f(v) for v in values)}" '
            f'keyTimes="{";".join(f(t) for t in times)}" dur="{f(dur)}s" '
            f'repeatCount="indefinite" calcMode="{calc}"/>')


def appear(t, cyc, off=0, on=1):
    """Animation that switches an attribute from `off` to `on` at time t (seconds)."""
    return anim("opacity", [off, on], [0.0, t / cyc], cyc)


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img">'
            f'<defs>{defs}</defs><style>text{{font-family:{FONT};}}</style>{body}</svg>')


def window(w, h, title, inner, defs=""):
    body = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{C["bg"]}" stroke="{C["line"]}"/>'
            f'<rect x=".5" y=".5" width="{w - 1}" height="38" rx="12" fill="{C["panel"]}"/>'
            f'<rect x=".5" y="26" width="{w - 1}" height="12" fill="{C["panel"]}"/>'
            f'<line x1="1" y1="38.5" x2="{w - 1}" y2="38.5" stroke="{C["line"]}"/>'
            '<circle cx="22" cy="19" r="6" fill="#ff5f56"/><circle cx="42" cy="19" r="6" fill="#ffbd2e"/>'
            '<circle cx="62" cy="19" r="6" fill="#27c93f"/>'
            f'<text x="{w / 2}" y="24" text-anchor="middle" font-size="13" fill="{C["dim"]}">{esc(title)}</text>'
            + inner)
    return svg(w, h, body, defs)


class Typer:
    """Character-by-character typing with a moving block cursor."""

    def __init__(self, cyc, fs=15, cw=9):
        self.cyc, self.fs, self.cw = cyc, fs, cw
        self.defs, self.body, self.keys, self.n = [], [], [], 0

    def line(self, x, y, parts, t0, dt=0.06):
        total = sum(len(t) for t, _ in parts)
        self.n += 1
        cid = f"ty{self.n}"
        w = total * self.cw
        times = [0.0] + [(t0 + i * dt) / self.cyc for i in range(1, total + 1)]
        vals = [0] + [i * self.cw for i in range(1, total + 1)]
        self.defs.append(
            f'<clipPath id="{cid}"><rect x="{x}" y="{y - self.fs}" width="{w}" height="{self.fs + 8}">'
            f'{anim("width", vals, times, self.cyc)}</rect></clipPath>')
        spans = "".join(f'<tspan fill="{c}">{esc(t)}</tspan>' for t, c in parts)
        self.body.append(
            f'<text x="{x}" y="{y}" font-size="{self.fs}" textLength="{w}" lengthAdjust="spacingAndGlyphs" '
            f'clip-path="url(#{cid})" xml:space="preserve">{spans}</text>')
        self.keys.append((t0, x, y))
        for i in range(1, total + 1):
            self.keys.append((t0 + i * dt, x + i * self.cw, y))
        return t0 + total * dt

    def cmd(self, x, y, command, t0, dt=0.06):
        return self.line(x, y, [("$ ", C["green"]), (command, C["text"])], t0, dt)

    def cursor(self, x0, y0, extra=()):
        keys = sorted([(0.0, x0, y0)] + self.keys + list(extra))
        times, xs, ys = [], [], []
        for t, x, y in keys:
            tn = t / self.cyc
            if times and tn <= times[-1]:
                tn = times[-1] + 1e-5
            times.append(tn)
            xs.append(x)
            ys.append(y - self.fs + 1)
        return (f'<rect width="{self.cw - 1}" height="{self.fs + 3}" fill="{C["green"]}" opacity="0" '
                f'x="{xs[-1]}" y="{ys[-1]}">{anim("x", xs, times, self.cyc)}{anim("y", ys, times, self.cyc)}'
                '<animate attributeName="opacity" values="1;0" dur="1s" repeatCount="indefinite" '
                'calcMode="discrete"/></rect>')


def fade_out_overlay(w, h, cyc, top=39):
    """Fades the content to the background right before the loop restarts."""
    return (f'<rect x="1" y="{top}" width="{w - 2}" height="{h - top - 1}" fill="{C["bg"]}" opacity="0">'
            f'{anim("opacity", [0, 0, 1], [0.0, (cyc - 0.7) / cyc, 1.0], cyc, "linear")}</rect>')


# ------------------------------------------------------------------ hero terminal
def hero(p):
    W = 900
    host = p.get("host", "devops")
    user = re.sub(r"[^a-z0-9]", "", p["name"].split()[0].lower()) or "me"
    info = p["info"]
    steps = p["deploy_steps"]
    n = len(info)

    # timeline
    t = 0.8
    info_y0 = 112
    info_rows = n + 2
    y2 = info_y0 + 24 * info_rows + 34
    # we need the cycle length before building; compute the schedule first
    t_neo_end = t + len("neofetch") * 0.07
    t_info = t_neo_end + 0.45
    t_cmd2 = t_info + 0.16 * info_rows + 1.3
    cmd2 = "./deploy.sh --env production"
    t_cmd2_end = t_cmd2 + len(cmd2) * 0.05
    t_steps = [t_cmd2_end + 0.6 + 0.75 * k for k in range(len(steps))]
    t_status = t_steps[-1] + 0.9
    y_status = y2 + 28 * (len(steps) + 1) + 6
    y_prompt = y_status + 34
    t_prompt = t_status + 1.0
    cyc = t_prompt + 6.0
    H = y_prompt + 34

    ty = Typer(cyc)
    ty.cmd(30, 72, "neofetch", t, 0.07)
    ty.cmd(30, y2, cmd2, t_cmd2, 0.05)
    body = []

    # logo
    cx, cy = 105, info_y0 + 70
    letter = esc(p["name"].strip()[:1].upper() or "Z")
    body.append(
        f'<g opacity="1">{appear(t_info, cyc)}'
        f'<circle cx="{cx}" cy="{cy}" r="64" fill="none" stroke="url(#lg)" stroke-width="3" stroke-dasharray="12 9">'
        f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" '
        f'dur="14s" repeatCount="indefinite"/></circle>'
        f'<circle cx="{cx}" cy="{cy}" r="50" fill="{C["panel"]}" stroke="{C["line"]}"/>'
        f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="68" font-weight="800" fill="url(#lg)">{letter}</text>'
        '</g>')

    # info block
    rows = [("title", None)] + [("sep", None)] + [("kv", kv) for kv in info]
    for i, (kind, kv) in enumerate(rows):
        y = info_y0 + 24 * i
        ti = t_info + 0.16 * i
        if kind == "title":
            inner = (f'<text x="215" y="{y}" font-size="15" font-weight="700">'
                     f'<tspan fill="{C["green"]}">{esc(user)}</tspan><tspan fill="{C["dim"]}">@</tspan>'
                     f'<tspan fill="{C["blue"]}">{esc(host)}</tspan></text>')
        elif kind == "sep":
            inner = f'<line x1="215" y1="{y - 5}" x2="640" y2="{y - 5}" stroke="{C["line"]}"/>'
        else:
            k, v = kv
            inner = (f'<text x="215" y="{y}" font-size="15" xml:space="preserve">'
                     f'<tspan fill="{C["blue"]}" font-weight="700">{esc(k)}</tspan>'
                     f'<tspan fill="{C["dim"]}">: </tspan><tspan fill="{C["text"]}">{esc(v)}</tspan></text>')
        body.append(f'<g opacity="1">{appear(ti, cyc)}{inner}</g>')

    # deploy output
    for k, (name, detail) in enumerate(steps):
        y = y2 + 28 * (k + 1)
        body.append(
            f'<g opacity="1">{appear(t_steps[k], cyc)}<text x="30" y="{y}" font-size="15" xml:space="preserve">'
            f'<tspan fill="{C["dim"]}">[ </tspan><tspan fill="{C["green"]}" font-weight="700">OK</tspan>'
            f'<tspan fill="{C["dim"]}"> ] </tspan><tspan fill="{C["text"]}">{esc(name)}</tspan>'
            f'<tspan fill="{C["dim"]}"> - {esc(detail)}</tspan></text></g>')
    body.append(
        f'<g opacity="1">{appear(t_status, cyc)}'
        f'<circle cx="38" cy="{y_status - 5}" r="5" fill="{C["green"]}">'
        f'<animate attributeName="r" values="4;7;4" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="54" y="{y_status}" font-size="15" font-weight="700" fill="{C["green"]}">all systems operational</text></g>')
    body.append(
        f'<g opacity="1">{appear(t_prompt, cyc)}<text x="30" y="{y_prompt}" font-size="15" fill="{C["green"]}">$ </text></g>')

    cursor = ty.cursor(30 + 2 * 9, 72, extra=[(t_prompt, 30 + 2 * 9, y_prompt)])
    defs = (f'<linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C["blue"]}"/>'
            f'<stop offset=".55" stop-color="{C["purple"]}"/><stop offset="1" stop-color="{C["green"]}"/></linearGradient>'
            + "".join(ty.defs))
    inner = "".join(ty.body) + "".join(body) + cursor + fade_out_overlay(W, H, cyc)
    return window(W, H, f"{user}@{host}: ~", inner, defs)


# ------------------------------------------------------------------ pipeline
def pipeline(p):
    stages = p["pipeline"]
    n = len(stages)
    W, H = 900, 230
    x0, xn = 80, W - 80
    y = 108
    T = 1.1 * (n - 1)
    start = 0.9
    cyc = start + T + 4.5
    tn = [start + i * T / (n - 1) for i in range(n)]
    xs = [x0 + i * (xn - x0) / (n - 1) for i in range(n)]
    kt = [0.0, start / cyc, (start + T) / cyc, 1.0]
    body = [f'<text x="26" y="34" font-size="13" fill="{C["dim"]}">pipeline: profile-deploy</text>',
            f'<text x="{W - 26}" y="34" font-size="13" text-anchor="end" fill="{C["dim"]}">on: push to main</text>',
            f'<rect x="{x0}" y="{y - 2}" width="{xn - x0}" height="4" rx="2" fill="{C["line"]}"/>',
            f'<rect x="{x0}" y="{y - 2}" width="{xn - x0}" height="4" rx="2" fill="{C["green"]}">'
            f'{anim("width", [0, 0, xn - x0, xn - x0], kt, cyc, "linear")}</rect>']
    for i, name in enumerate(stages):
        t = tn[i]
        cx = xs[i]
        run, done = max(t - 0.35, 0.05), t + 0.35
        fill_anim = anim("fill", [C["panel"], C["blue"], "#238636"], [0.0, run / cyc, done / cyc], cyc)
        stroke_anim = anim("stroke", [C["line"], C["blue"], C["green"]], [0.0, run / cyc, done / cyc], cyc)
        body.append(
            f'<circle cx="{cx}" cy="{y}" r="26" fill="{C["blue"]}" opacity="0">'
            f'{anim("opacity", [0, 0.35, 0, 0], [0.0, run / cyc, done / cyc, 1.0], cyc, "linear")}</circle>'
            f'<circle cx="{cx}" cy="{y}" r="20" fill="#238636" stroke="{C["green"]}" stroke-width="2">'
            f'{fill_anim}{stroke_anim}</circle>'
            f'<path d="M{cx - 8} {y + 1} L{cx - 2} {y + 7} L{cx + 8} {y - 6}" fill="none" stroke="#fff" '
            f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{appear(done, cyc)}</path>'
            f'<text x="{cx}" y="{y + 50}" text-anchor="middle" font-size="13" fill="{C["text"]}">{esc(name)}'
            f'{anim("fill", [C["dim"], C["text"]], [0.0, run / cyc], cyc)}</text>')
    body.append(
        f'<circle r="7" cy="{y}" cx="{xn}" fill="#fff" opacity="0">'
        f'{anim("cx", [x0, x0, xn, xn], kt, cyc, "linear")}'
        f'{anim("opacity", [0, 1, 0], [0.0, start / cyc, (start + T) / cyc], cyc)}</circle>')
    t_end = start + T + 0.6
    body.append(
        f'<g opacity="1">{appear(t_end, cyc)}<circle cx="{W / 2 - 150}" cy="{H - 34}" r="5" fill="{C["green"]}">'
        f'<animate attributeName="r" values="4;7;4" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="{W / 2 - 134}" y="{H - 29}" font-size="14" fill="{C["green"]}" font-weight="700">'
        f'pipeline passed - {len(stages)} stages, 0 failures</text></g>')
    body.append(fade_out_overlay(W, H, cyc, top=1))
    base = (f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{C["bg"]}" stroke="{C["line"]}"/>')
    return svg(W, H, base + "".join(body))


# ------------------------------------------------------------------ infrastructure
def infra(p):
    L = p["infra"]
    W, H = 900, 340
    out = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{C["bg"]}" stroke="{C["line"]}"/>',
           f'<rect x="165" y="22" width="715" height="258" rx="14" fill="none" stroke="{C["line"]}" '
           'stroke-dasharray="6 6"/>',
           f'<text x="180" y="42" font-size="12" fill="{C["dim"]}">cloud / private network</text>']

    def node(x, y, w, h, label, color, led_dur):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{C["panel"]}" stroke="{color}" stroke-width="1.5"/>'
                f'<text x="{x + w / 2}" y="{y + h / 2 + 5}" text-anchor="middle" font-size="13" fill="{C["text"]}">{esc(label)}</text>'
                f'<circle cx="{x + w - 10}" cy="{y + 10}" r="3.5" fill="{color}">'
                f'<animate attributeName="opacity" values="1;0.15" dur="{led_dur}s" repeatCount="indefinite" calcMode="discrete"/></circle>')

    boxes = [(20, 140, 120, 52, L["clients"], C["dim"], 1.3),
             (195, 140, 130, 52, L["lb"], C["orange"], 0.9)]
    api_y = [62, 140, 218]
    for i, yy in enumerate(api_y):
        boxes.append((395, yy, 130, 52, f'{L["api"]} #{i + 1}', C["blue"], 1.1 + i * 0.4))
    data_y = [62, 140, 218]
    for yy, key, col, d in zip(data_y, ("db", "cache", "queue"), (C["purple"], C["green"], C["yellow"]), (1.7, 1.2, 0.8)):
        boxes.append((665, yy, 190, 52, L[key], col, d))

    paths = [("M140 166 L195 166", C["dim"])]
    for yy in api_y:
        paths.append((f"M325 166 C360 166 360 {yy + 26} 395 {yy + 26}", C["orange"]))
    links = [(0, 0), (0, 1), (1, 1), (1, 0), (2, 2), (2, 1), (1, 2)]
    for a, b in links:
        paths.append((f"M525 {api_y[a] + 26} C595 {api_y[a] + 26} 595 {data_y[b] + 26} 665 {data_y[b] + 26}",
                      C["blue"]))
    for d, col in paths:
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-opacity="0.35" stroke-width="1.5"/>')
    for x, y, w, h, label, col, d in boxes:
        out.append(node(x, y, w, h, label, col, d))

    # data packets
    pk = []
    for i, (d, col) in enumerate(paths):
        dur = 1.6 + (i % 3) * 0.5
        for j in range(2):
            pk.append(f'<circle r="4" fill="{col}"><animateMotion dur="{dur}s" begin="{(i * 0.37 + j * dur / 2) % dur:.2f}s" '
                      f'repeatCount="indefinite" path="{d}"/></circle>')
    out.extend(pk)
    out.append(f'<rect x="20" y="294" width="{W - 40}" height="32" rx="8" fill="{C["panel"]}" stroke="{C["line"]}"/>'
               f'<circle cx="40" cy="310" r="4.5" fill="{C["green"]}"><animate attributeName="r" values="3.5;6;3.5" '
               'dur="1.6s" repeatCount="indefinite"/></circle>'
               f'<text x="56" y="315" font-size="13" fill="{C["text"]}">{esc(L["obs"])}</text>')
    return svg(W, H, "".join(out))


# ------------------------------------------------------------------ skills table
def skills(p):
    rows = [(g["namespace"], n, s) for g in p["skills"] for n, s in g["items"]]
    W = 900
    y0 = 108
    H = y0 + 24 * len(rows) + 34
    t0 = 0.6
    t_hdr = t0 + len("kubectl get skills -A") * 0.06 + 0.4
    t_rows = [t_hdr + 0.4 + 0.14 * i for i in range(len(rows))]
    cyc = t_rows[-1] + 6.5
    ty = Typer(cyc)
    ty.cmd(30, 72, "kubectl get skills -A", t0)
    body = [f'<g opacity="1">{appear(t_hdr, cyc)}<text y="{y0 - 6}" font-size="13" font-weight="700" fill="{C["dim"]}" '
            'xml:space="preserve"><tspan x="52">NAMESPACE</tspan><tspan x="230">NAME</tspan>'
            '<tspan x="470">READY</tspan><tspan x="570">STATUS</tspan></text></g>']
    for i, (ns, name, st) in enumerate(rows):
        y = y0 + 24 * (i + 1) - 6
        running = st.lower() == "running"
        col = C["green"] if running else C["yellow"]
        label = "Running" if running else "Learning"
        dot = (f'<circle cx="38" cy="{y - 5}" r="4" fill="{col}">'
               + ('<animate attributeName="r" values="3.5;5.5;3.5" dur="2s" repeatCount="indefinite"/>' if running else
                  '<animate attributeName="opacity" values="1;0.2" dur="1s" repeatCount="indefinite" calcMode="discrete"/>')
               + '</circle>')
        body.append(
            f'<g opacity="1">{appear(t_rows[i], cyc)}{dot}'
            f'<text y="{y}" font-size="14" xml:space="preserve"><tspan x="52" fill="{C["purple"]}">{esc(ns)}</tspan>'
            f'<tspan x="230" fill="{C["text"]}">{esc(name)}</tspan><tspan x="470" fill="{C["dim"]}">{"1/1" if running else "0/1"}</tspan>'
            f'<tspan x="570" fill="{col}" font-weight="700">{label}</tspan></text></g>')
    t_prompt = t_rows[-1] + 0.8
    y_prompt = H - 14
    body.append(f'<g opacity="1">{appear(t_prompt, cyc)}<text x="30" y="{y_prompt}" font-size="15" fill="{C["green"]}">$ </text></g>')
    cursor = ty.cursor(48, 72, extra=[(t_prompt, 48, y_prompt)])
    inner = "".join(ty.body) + "".join(body) + cursor + fade_out_overlay(W, H, cyc)
    return window(W, H, "zeyad@k8s: ~", inner, "".join(ty.defs))


# ------------------------------------------------------------------ project cards
def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur] if cur else lines


def card(pr):
    W, H = 440, 170
    lines = wrap(pr["description"], 50)[:4]
    out = [f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="14" fill="{C["panel"]}" stroke="url(#cg)" stroke-width="2.5"/>',
           f'<rect x="24" y="26" width="10" height="10" rx="2" fill="{C["green"]}">'
           '<animate attributeName="opacity" values="1;0.25" dur="1.2s" repeatCount="indefinite" calcMode="discrete"/></rect>',
           f'<text x="44" y="36" font-size="18" font-weight="700" fill="{C["text"]}">{esc(pr["name"])}</text>']
    for i, ln in enumerate(lines):
        out.append(f'<text x="24" y="{64 + 18 * i}" font-size="12.5" fill="{C["dim"]}">{esc(ln)}</text>')
    x = 24
    for tag in pr["tags"]:
        w = len(tag) * 7 + 18
        if x + w > W - 20:
            break
        out.append(f'<rect x="{x}" y="{H - 40}" width="{w}" height="22" rx="11" fill="{C["chip"]}"/>'
                   f'<text x="{x + w / 2}" y="{H - 25}" text-anchor="middle" font-size="11" fill="{C["blue"]}">{esc(tag)}</text>')
        x += w + 8
    defs = (f'<linearGradient id="cg" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="{H}">'
            f'<stop offset="0" stop-color="{C["blue"]}"/><stop offset=".5" stop-color="{C["purple"]}"/>'
            f'<stop offset="1" stop-color="{C["green"]}"/>'
            f'<animateTransform attributeName="gradientTransform" type="rotate" from="0 {W / 2} {H / 2}" '
            f'to="360 {W / 2} {H / 2}" dur="6s" repeatCount="indefinite"/></linearGradient>')
    return svg(W, H, "".join(out), defs)


# ------------------------------------------------------------------ heartbeat footer
def heartbeat(p):
    W, H = 900, 110
    d, x = "M0 62", 0
    while x < W:
        d += (f" L{x + 40} 62 L{x + 52} 50 L{x + 62} 62 L{x + 80} 62 L{x + 92} 14 L{x + 106} 100 "
              f"L{x + 118} 62 L{x + 160} 62")
        x += 160
    out = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{C["bg"]}" stroke="{C["line"]}"/>',
           f'<path d="{d}" fill="none" stroke="{C["green"]}" stroke-opacity="0.2" stroke-width="2"/>',
           f'<path d="{d}" fill="none" stroke="{C["green"]}" stroke-width="3" stroke-linecap="round" '
           'stroke-linejoin="round" pathLength="1000" stroke-dasharray="130 870">'
           '<animate attributeName="stroke-dashoffset" values="0;-1000" dur="3.2s" repeatCount="indefinite"/></path>',
           f'<text x="26" y="30" font-size="13" fill="{C["dim"]}">{esc(p.get("footer", ""))}</text>',
           f'<text x="{W - 26}" y="30" text-anchor="end" font-size="13" fill="{C["green"]}">status: operational</text>']
    return svg(W, H, "".join(out))


# ------------------------------------------------------------------ README
def badge(label, color, logo, logo_color):
    lab = label.replace("-", "--").replace("_", "__").replace(" ", "_")
    return (f'<img src="https://img.shields.io/badge/{lab}-{color}?style=for-the-badge&logo={logo}'
            f'&logoColor={logo_color}" alt="{esc(label)}"/>')


def readme(p):
    user = p["username"]
    links = p.get("links", {})
    contact = []
    if links.get("email"):
        contact.append(f'<a href="mailto:{links["email"]}"><img src="https://img.shields.io/badge/Email-0d1117?style=for-the-badge&logo=gmail&logoColor=ff7b72" alt="email"/></a>')
    if links.get("linkedin"):
        contact.append(f'<a href="{links["linkedin"]}"><img src="https://img.shields.io/badge/LinkedIn-0d1117?style=for-the-badge&logo=linkedin&logoColor=58a6ff" alt="linkedin"/></a>')
    if links.get("twitter"):
        contact.append(f'<a href="{links["twitter"]}"><img src="https://img.shields.io/badge/X-0d1117?style=for-the-badge&logo=x&logoColor=white" alt="x"/></a>')
    if links.get("website"):
        contact.append(f'<a href="{links["website"]}"><img src="https://img.shields.io/badge/Website-0d1117?style=for-the-badge&logo=googlechrome&logoColor=3fb950" alt="website"/></a>')
    cards = "".join(
        f'<td width="50%" align="center"><a href="{pr["url"]}"><img src="assets/card-{i + 1}.svg" alt="{esc(pr["name"])}" width="100%"/></a></td>'
        for i, pr in enumerate(p["projects"]))
    snake = f"https://raw.githubusercontent.com/{user}/{user}/output"
    return f'''<!-- Generated by generate.py from profile.json - edit profile.json, then run: python3 generate.py -->
<div align="center">
  <img src="assets/hero.svg" alt="terminal" width="100%"/>
</div>

<div align="center">

{" ".join(contact)}

</div>

### How I ship

<div align="center"><img src="assets/pipeline.svg" alt="ci/cd pipeline" width="100%"/></div>

### How I think about systems

<div align="center"><img src="assets/infra.svg" alt="infrastructure" width="100%"/></div>

### What is running

<div align="center"><img src="assets/skills.svg" alt="kubectl get skills" width="100%"/></div>

<div align="center">

{" ".join(badge(*b) for b in p["badges"])}

</div>

### Featured projects

<table>
  <tr>
    {cards}
  </tr>
</table>

### Contribution snake

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="{snake}/github-snake-dark.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="{snake}/github-snake.svg"/>
  <img alt="contribution snake" src="{snake}/github-snake.svg" width="100%"/>
</picture>
</div>

<div align="center"><img src="assets/heartbeat.svg" alt="heartbeat" width="100%"/></div>
'''


def main():
    with open(os.path.join(HERE, "profile.json"), encoding="utf-8") as fh:
        p = json.load(fh)
    os.makedirs(OUT, exist_ok=True)
    files = {"hero.svg": hero(p), "pipeline.svg": pipeline(p), "infra.svg": infra(p),
             "skills.svg": skills(p), "heartbeat.svg": heartbeat(p)}
    for i, pr in enumerate(p["projects"]):
        files[f"card-{i + 1}.svg"] = card(pr)
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"assets/{name}  {len(content) // 1024 + 1} KB")
    with open(os.path.join(HERE, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(readme(p))
    print("README.md")


if __name__ == "__main__":
    main()
