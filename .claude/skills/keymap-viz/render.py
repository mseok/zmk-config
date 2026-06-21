#!/usr/bin/env python3
"""Render a ZMK Corne keymap layer as an inline SVG keyboard widget.

Parses config/corne.keymap, extracts a layer's 42 bindings, and emits an
<svg> string in the claude.ai visualize style (CSS-variable colors, ramp
classes, dark-mode safe). The caller pipes stdout straight into show_widget.

Geometry assumes a 42-key Corne (5 columns + 3 thumbs per half); the outer
phantom columns (always &none) are not drawn.

Usage:
    python3 render.py --list                 # list layer names, in order
    python3 render.py <layer>                # print one layer's SVG
    python3 render.py --all                  # print every layer's SVG,
                                             #   separated by <!--LAYER:name-->
    python3 render.py --keymap PATH <layer>  # override keymap path

<layer> matches either the node name (e.g. navigation, default, mouse) or
the #define name (e.g. NAV, BASE, MOUSE), case-insensitive.
"""
import pathlib
import re
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
# .claude/skills/keymap-viz -> repo root is parents[2]
REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_KEYMAP = REPO_ROOT / "config" / "corne.keymap"

# ---- geometry (matches the hand-built NAV widget) --------------------------
W, H, RX = 52, 46, 6
XL = [20, 78, 136, 194, 252]
XR = [360, 418, 476, 534, 592]
STAGL = [14, 6, 0, 10, 16]
STAGR = [16, 10, 0, 6, 14]
ROWY = {"top": 50, "home": 104, "bottom": 158}
THUMBS = [(170, 226), (228, 236), (286, 246), (344, 246), (402, 236), (460, 226)]
ARROWS = {"←", "↑", "↓", "→"}  # ← ↑ ↓ →

# ---- keycode -> friendly label maps ----------------------------------------
MOD = {
    "LCTRL": "Ctrl", "RCTRL": "Ctrl", "LEFT_CONTROL": "Ctrl", "RIGHT_CONTROL": "Ctrl",
    "LALT": "Alt", "RALT": "Alt", "LEFT_ALT": "Alt", "RIGHT_ALT": "Alt",
    "LGUI": "Cmd", "RGUI": "Cmd", "LEFT_GUI": "Cmd", "RIGHT_GUI": "Cmd",
    "LSHFT": "Shift", "RSHFT": "Shift", "LEFT_SHIFT": "Shift", "RIGHT_SHIFT": "Shift",
}
NAVK = {"LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓",
        "HOME": "Home", "END": "End", "PG_UP": "PgUp", "PG_DN": "PgDn"}
MEDIA = {"C_VOL_UP": "Vol +", "C_VOL_DN": "Vol −", "K_MUTE": "Mute", "C_MUTE": "Mute",
         "C_BRI_UP": "Bri +", "C_BRI_DN": "Bri −", "C_PREV": "Prev", "C_NEXT": "Next",
         "C_PP": "Play", "C_PLAY_PAUSE": "Play"}
SYM = {
    "SEMI": ";", "COLON": ":", "APOS": "'", "DQT": '"', "COMMA": ",", "DOT": ".",
    "SLASH": "/", "BSLH": "\\", "PIPE": "|", "LBKT": "[", "RBKT": "]", "LBRC": "{",
    "RBRC": "}", "LPAR": "(", "RPAR": ")", "MINUS": "−", "UNDER": "_",
    "EQUAL": "=", "PLUS": "+", "GRAVE": "`", "TILDE": "~", "EXCL": "!", "AT": "@",
    "HASH": "#", "DLLR": "$", "PRCNT": "%", "CARET": "^", "AMPS": "&", "STAR": "*",
    "QMARK": "?", "LT": "<", "GT": ">",
}
SPECIAL = {"ESC": "Esc", "TAB": "Tab", "BSPC": "Bspc", "DEL": "Del", "RET": "Enter",
           "ENTER": "Enter", "SPACE": "Space", "CAPS": "Caps"}
NUMS = {f"N{i}": str(i) for i in range(10)}
WRAP = {"LS": "⇧", "RS": "⇧", "LC": "⌃", "RC": "⌃",
        "LA": "⌥", "RA": "⌥", "LG": "⌘", "RG": "⌘"}

# category -> (ramp class, legend label).  Categories not listed render gray
# with no legend entry (plain letters / numbers / symbols are self-evident).
LEGEND = {
    "media": ("c-purple", "media / vol / bri"),
    "nav": ("c-teal", "cursor / page"),
    "mod": ("c-gray", "modifier"),
    "hrm": ("c-blue", "home-row mod (tap / hold)"),
    "layer": ("c-coral", "layer (tap / hold)"),
    "held": ("c-coral", "held → this layer"),
    "boot": ("c-red", "bootloader"),
    "bt": ("c-pink", "bluetooth"),
    "mmove": ("c-blue", "mouse move"),
    "mclick": ("c-amber", "mouse click"),
    "mscroll": ("c-green", "mouse scroll"),
}
LEGEND_ORDER = ["held", "layer", "hrm", "mod", "nav", "media",
                "bt", "mmove", "mclick", "mscroll", "boot"]

# ramp -> (light fill, light stroke, light text, dark fill, dark stroke, dark text).
# Used only in --standalone mode (GitHub/offline): the claude.ai host CSS that
# powers the widget classes is absent there, so colors are baked in literally.
PALETTE = {
    "c-purple": ("#EEEDFE", "#534AB7", "#26215C", "#3C3489", "#AFA9EC", "#CECBF6"),
    "c-teal":   ("#E1F5EE", "#0F6E56", "#04342C", "#085041", "#5DCAA5", "#9FE1CB"),
    "c-coral":  ("#FAECE7", "#993C1D", "#4A1B0C", "#712B13", "#F0997B", "#F5C4B3"),
    "c-pink":   ("#FBEAF0", "#993556", "#4B1528", "#72243E", "#ED93B1", "#F4C0D1"),
    "c-gray":   ("#F1EFE8", "#5F5E5A", "#2C2C2A", "#444441", "#B4B2A9", "#D3D1C7"),
    "c-blue":   ("#E6F1FB", "#185FA5", "#042C53", "#0C447C", "#85B7EB", "#B5D4F4"),
    "c-green":  ("#EAF3DE", "#3B6D11", "#173404", "#27500A", "#97C459", "#C0DD97"),
    "c-amber":  ("#FAEEDA", "#854F0B", "#412402", "#633806", "#EF9F27", "#FAC775"),
    "c-red":    ("#FCEBEB", "#A32D2D", "#501313", "#791F1F", "#F09595", "#F7C1C1"),
}


def standalone_style():
    light = [
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}",
        ".bg{fill:#FFFFFF;stroke:#E5E4DF;stroke-width:1}",
        ".t{fill:#2C2C2A}", ".ts{fill:#5F5E5A}",
        ".empty{fill:#EFEEE9;stroke:#C9C7BE;stroke-width:1;stroke-dasharray:3 3}",
    ]
    dark = [
        ".bg{fill:#0D1117;stroke:#2A2D32}",
        ".t{fill:#D3D1C7}", ".ts{fill:#B4B2A9}",
        ".empty{fill:#242422;stroke:#4A4A47}",
    ]
    for cls, (lf, ls, lt, df, ds, dt) in PALETTE.items():
        light.append(f".{cls} rect{{fill:{lf};stroke:{ls};stroke-width:1.4}}")
        light.append(f".{cls} .t{{fill:{lt}}}")
        dark.append(f".{cls} rect{{fill:{df};stroke:{ds}}}")
        dark.append(f".{cls} .t{{fill:{dt}}}")
    return "<style>" + "".join(light) + "@media(prefers-color-scheme:dark){" + "".join(dark) + "}</style>"


def xesc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def kp_label(code):
    """Return (label, category) for a &kp keycode."""
    m = re.match(r"^([A-Z]{2})\((.+)\)$", code)
    if m:
        pre = WRAP.get(m.group(1), "")
        inner, _ = kp_label(m.group(2))
        return (pre + inner, "combo")
    if code in NAVK:
        return (NAVK[code], "nav")
    if code in MEDIA:
        return (MEDIA[code], "media")
    if code in MOD:
        return (MOD[code], "mod")
    if code in SPECIAL:
        return (SPECIAL[code], "special")
    if code in SYM:
        return (SYM[code], "sym")
    if code in NUMS:
        return (NUMS[code], "num")
    if re.match(r"^[A-Z]$", code):
        return (code, "letter")
    if re.match(r"^F\d+$", code):
        return (code, "special")
    return (code, "other")


def classify(b):
    """binding [behavior, *params] -> dict(lines, cls, cat)."""
    beh = b[0]
    p = b[1:]
    if beh == "none":
        return {"lines": [], "cls": "empty", "cat": None}
    if beh == "trans":
        return {"lines": ["▽"], "cls": "c-gray", "cat": None}
    if beh == "bootloader":
        return {"lines": ["Boot"], "cls": "c-red", "cat": "boot"}
    if beh in ("sys_reset", "reset"):
        return {"lines": ["Reset"], "cls": "c-red", "cat": "boot"}
    if beh == "bt":
        sub = p[0] if p else ""
        if sub == "BT_SEL":
            return {"lines": ["BT", p[1] if len(p) > 1 else ""], "cls": "c-pink", "cat": "bt"}
        tail = {"BT_CLR": "clear", "BT_CLR_ALL": "clr all",
                "BT_NXT": "next", "BT_PRV": "prev"}.get(sub, sub.replace("BT_", "").lower())
        return {"lines": ["BT", tail], "cls": "c-pink", "cat": "bt"}
    if beh == "out":
        sub = p[0] if p else ""
        lab = {"OUT_TOG": ["USB", "/ BT"], "OUT_USB": ["USB"], "OUT_BLE": ["BT"]}.get(sub, [sub])
        return {"lines": lab, "cls": "c-pink", "cat": "bt"}
    if beh == "kp":
        lbl, cat = kp_label(p[0]) if p else ("?", "other")
        cls = {"nav": "c-teal", "media": "c-purple", "mod": "c-gray"}.get(cat, "c-gray")
        return {"lines": [lbl], "cls": cls, "cat": cat if cat in ("nav", "media", "mod") else "key"}
    if beh in ("ml", "mr", "mt"):
        mod = MOD.get(p[0], p[0]) if p else ""
        key = kp_label(p[1])[0] if len(p) > 1 else ""
        return {"lines": [key, mod], "cls": "c-blue", "cat": "hrm"}
    if beh == "lt":
        key = kp_label(p[1])[0] if len(p) > 1 else ""
        return {"lines": [key, p[0] if p else ""], "cls": "c-coral", "cat": "layer"}
    if beh == "mo":
        return {"lines": ["L", p[0] if p else ""], "cls": "c-coral", "cat": "layer"}
    if beh == "mkp":
        lab = {"LCLK": ["L", "click"], "RCLK": ["R", "click"], "MCLK": ["M", "click"],
               "MB4": ["M4"], "MB5": ["M5"]}.get(p[0] if p else "", [p[0] if p else "?"])
        return {"lines": lab, "cls": "c-amber", "cat": "mclick"}
    if beh == "mmv":
        a = {"MOVE_UP": "↑", "MOVE_DOWN": "↓", "MOVE_LEFT": "←",
             "MOVE_RIGHT": "→"}.get(p[0] if p else "", "?")
        return {"lines": ["Move", a], "cls": "c-blue", "cat": "mmove"}
    if beh == "msc":
        a = {"SCRL_UP": "↑", "SCRL_DOWN": "↓", "SCRL_LEFT": "←",
             "SCRL_RIGHT": "→"}.get(p[0] if p else "", "?")
        return {"lines": ["Scroll", a], "cls": "c-green", "cat": "mscroll"}
    return {"lines": [beh], "cls": "c-gray", "cat": "key"}


# ---- keymap parsing --------------------------------------------------------
def tokenize(body):
    body = re.sub(r"//[^\n]*", " ", body)
    body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
    out, cur = [], None
    for t in body.split():
        if t.startswith("&"):
            if cur is not None:
                out.append(cur)
            cur = [t[1:]]
        elif cur is not None:
            cur.append(t)
    if cur is not None:
        out.append(cur)
    return out


def parse_layers(text):
    layers = []
    for m in re.finditer(r"(\w+)_layer\s*\{.*?bindings\s*=\s*<(.*?)>\s*;", text, re.S):
        layers.append((m.group(1), tokenize(m.group(2))))
    return layers


def parse_defines(text):
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r"#define\s+(\w+)\s+(\d+)\b", text)}


# ---- svg emission ----------------------------------------------------------
def key_svg(x, y, info, standalone=False):
    if info["cls"] == "empty":
        if standalone:
            return f'<rect class="empty" x="{x}" y="{y}" width="{W}" height="{H}" rx="{RX}"/>'
        return (f'<rect x="{x}" y="{y}" width="{W}" height="{H}" rx="{RX}" '
                f'fill="var(--color-background-secondary)" '
                f'stroke="var(--color-border-tertiary)" stroke-dasharray="3 3"/>')
    cx = x + W // 2
    lines = [s for s in info["lines"] if s != ""]
    txt = ""
    if len(lines) == 1:
        lab = lines[0]
        fs = 17 if lab in ARROWS else (13 if len(lab) <= 5 else 11)
        txt = f'<text class="t" x="{cx}" y="{y+28}" text-anchor="middle" font-size="{fs}">{xesc(lab)}</text>'
    elif len(lines) >= 2:
        l1, l2 = lines[0], lines[1]
        fs1 = 13 if len(l1) <= 5 else 11
        fs2 = 16 if l2 in ARROWS else (12 if len(l2) <= 6 else 11)
        txt = (f'<text class="t" x="{cx}" y="{y+19}" text-anchor="middle" font-size="{fs1}">{xesc(l1)}</text>'
               f'<text class="t" x="{cx}" y="{y+34}" text-anchor="middle" font-size="{fs2}">{xesc(l2)}</text>')
    return (f'<g class="{info["cls"]}"><rect x="{x}" y="{y}" width="{W}" height="{H}" rx="{RX}"/>{txt}</g>')


def placements():
    out = []
    for c in range(5):
        out.append((1 + c, XL[c], ROWY["top"] + STAGL[c]))
        out.append((6 + c, XR[c], ROWY["top"] + STAGR[c]))
        out.append((13 + c, XL[c], ROWY["home"] + STAGL[c]))
        out.append((18 + c, XR[c], ROWY["home"] + STAGR[c]))
        out.append((25 + c, XL[c], ROWY["bottom"] + STAGL[c]))
        out.append((30 + c, XR[c], ROWY["bottom"] + STAGR[c]))
    for i in range(6):
        out.append((36 + i, THUMBS[i][0], THUMBS[i][1]))
    return out


def render(layers, defmap, idx, standalone=False):
    name, binds = layers[idx]
    defmap = {k: v for k, v in defmap.items() if v < len(layers)}
    inv = {}
    for k, v in defmap.items():
        inv.setdefault(v, k)
    fname = inv.get(idx, name.upper())

    # positions in BASE (layer 0) that activate THIS layer via lt / mo
    acts = {}
    if idx != 0 and layers:
        for pidx, b in enumerate(layers[0][1]):
            if b and b[0] in ("lt", "mo") and len(b) > 1 and defmap.get(b[1]) == idx:
                acts[pidx] = fname

    body, cats = [], []
    for pidx, x, y in placements():
        if pidx in acts:
            info = {"lines": [acts[pidx], "held"], "cls": "c-coral", "cat": "held"}
        else:
            info = classify(binds[pidx]) if pidx < len(binds) else {"lines": [], "cls": "empty", "cat": None}
        if info["cat"]:
            cats.append(info["cat"])
        body.append(key_svg(x, y, info, standalone))

    # legend
    present = [c for c in LEGEND_ORDER if c in cats]
    seen, items = set(), []
    for c in present:
        cls, lab = LEGEND[c]
        if lab in seen:
            continue
        seen.add(lab)
        items.append((cls, lab))
    leg, lx, ly = [], 20, 312
    for cls, lab in items:
        w = 22 + int(len(lab) * 6.4) + 18
        if lx + w > 660:
            lx, ly = 20, ly + 22
        leg.append(f'<g class="{cls}"><rect x="{lx}" y="{ly}" width="14" height="14" rx="3"/></g>')
        leg.append(f'<text class="ts" x="{lx+20}" y="{ly+11}" font-size="12">{xesc(lab)}</text>')
        lx += w
    vh = ly + 30

    title = f"Corne {fname} layer"
    desc = f"{fname} layer key arrangement for a 42-key Corne split keyboard."
    meta = f'<title>{xesc(title)}</title><desc>{xesc(desc)}</desc>'
    if standalone:
        head = f'<svg viewBox="0 0 680 {vh}" xmlns="http://www.w3.org/2000/svg" role="img">'
        bg = f'<rect class="bg" x="0" y="0" width="680" height="{vh}" rx="16"/>'
        return head + meta + standalone_style() + bg + "".join(body) + "".join(leg) + "</svg>"
    head = (f'<svg viewBox="0 0 680 {vh}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" font-family="var(--font-sans)">')
    return head + meta + "".join(body) + "".join(leg) + "</svg>"


def find_index(layers, defmap, q):
    ql = q.lower()
    for i, (name, _) in enumerate(layers):
        if name.lower() == ql or name.lower() == ql + "_layer":
            return i
    for k, v in defmap.items():
        if k.lower() == ql and v < len(layers):
            return v
    # also accept "navigation_layer"
    for i, (name, _) in enumerate(layers):
        if (name + "_layer").lower() == ql:
            return i
    return None


def main(argv):
    keymap = DEFAULT_KEYMAP
    args = list(argv)
    if "--keymap" in args:
        i = args.index("--keymap")
        keymap = pathlib.Path(args[i + 1])
        del args[i:i + 2]
    standalone = "--standalone" in args
    if standalone:
        args.remove("--standalone")
    text = pathlib.Path(keymap).read_text()
    layers = parse_layers(text)
    defmap = parse_defines(text)
    small = {k: v for k, v in defmap.items() if v < len(layers)}
    inv = {}
    for k, v in small.items():
        inv.setdefault(v, k)

    if not args or args[0] == "--list":
        for i, (name, binds) in enumerate(layers):
            print(f"{i}\t{inv.get(i, name.upper())}\t{name}_layer\t({len(binds)} keys)")
        return 0
    if args[0] == "--all":
        for i, (name, _) in enumerate(layers):
            print(f"<!--LAYER:{inv.get(i, name.upper())}-->")
            print(render(layers, defmap, i, standalone))
        return 0
    idx = find_index(layers, small, args[0])
    if idx is None:
        avail = ", ".join(inv.get(i, n.upper()) for i, (n, _) in enumerate(layers))
        sys.stderr.write(f"layer '{args[0]}' not found. available: {avail}\n")
        return 1
    print(render(layers, defmap, idx, standalone))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
