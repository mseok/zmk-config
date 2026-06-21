---
name: keymap-viz
description: Render the Corne ZMK keymap layers as inline SVG keyboard widgets (one per layer), color-coded by key function. Use when the user wants to see, show, draw, visualize, or diagram their keymap / a layer / "내 배열".
---

# Visualize the Corne keymap

Turns `config/corne.keymap` into clean SVG keyboard diagrams — one per layer — rendered inline via the `visualize` (`show_widget`) tool. Each key is colored by function (media, navigation, modifier, home-row mod, layer, bluetooth, mouse, bootloader) with an auto-generated legend, and the thumb that *activates* a layer is marked `held`.

Helper script: `.claude/skills/keymap-viz/render.py` (pure Python 3, no deps). It parses the keymap and emits one `<svg>…</svg>` string per layer, already styled for claude.ai light/dark mode.

## Procedure

1. **List the layers**
   `python3 .claude/skills/keymap-viz/render.py --list`
   → prints `index, NAME, node_layer, (key count)`. Sanity-check every layer is `42 keys`.

2. **Render each layer the user asked for** (default: all of them)
   For each layer name:
   `python3 .claude/skills/keymap-viz/render.py <NAME>`  (e.g. `NAV`, `BASE`, `mouse` — node name or `#define` name, case-insensitive)
   The command prints a single-line SVG to stdout. Pass that string **verbatim** as `widget_code` to `show_widget` (call `visualize.read_me` once first if you haven't this session). Use a distinct `title` per layer, e.g. `corne_base_layer`.
   - In your text around each widget, name the layer and how it's reached (the `held` key), and call out anything non-obvious. Don't restate the grid — it's in the widget.

3. **Keep prose out of the SVG.** The diagram carries the keys + legend; explanation goes in your chat message.

## Color legend (encoded by the script)

| Color | Meaning |
|-------|---------|
| coral | layer key (tap/hold) · `held` = activates this layer |
| blue | home-row mod (tap/hold) — and mouse-move on the mouse layer |
| gray | plain letters/numbers/symbols, and standalone modifiers |
| teal | cursor / page navigation |
| purple | media / volume / brightness |
| pink | bluetooth (`BT_SEL`, `BT_CLR`, `OUT_TOG`) |
| amber / green | mouse click / mouse scroll |
| red | bootloader |
| dashed | `&none` (inactive on this layer) |

Colors never collide *within* a single layer (e.g. blue means home-row-mod on BASE/NUM and mouse-move on MOUSE, which never co-occur), so the per-layer legend is unambiguous.

## Notes / extending

- Geometry assumes a **42-key Corne** (5 columns + 3 thumbs per half); the phantom outer columns (always `&none`) are not drawn. Coordinates live at the top of `render.py` (`XL/XR/STAGL/STAGR/ROWY/THUMBS`).
- To support a new behavior or relabel a keycode, edit the `classify()` / `kp_label()` maps and the `LEGEND` table in `render.py`.
- The `held` marker is derived by scanning the BASE layer for `&lt`/`&mo` whose target resolves (via the `#define`s) to the layer being drawn — so layers reached from two thumbs (e.g. MOUSE, SHIFT) show both.
- `render.py --all` prints every layer separated by `<!--LAYER:NAME-->` for scripting; `--keymap PATH` overrides the default `config/corne.keymap`.
- Pairs with the [flash-corne](../flash-corne/SKILL.md) skill: edit keymap → visualize to confirm → flash.
