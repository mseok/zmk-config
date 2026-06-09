---
name: flash-corne
description: Download the latest GitHub Actions firmware and flash the Corne keyboard halves over UF2 (nice!nano v2). Use when the user wants to update, flash, or reflash their Corne / ZMK firmware on macOS.
---

# Flash Corne firmware

Automates fetching the latest CI firmware and copying it onto the nice!nano Corne halves. The **only** manual step is putting each half into bootloader mode — the host cannot trigger that remotely (a running ZMK board is just a USB HID device).

Helper script: `.claude/skills/flash-corne/flash.sh` (run via `bash`).

## Procedure

1. **Download the latest firmware**
   Run `bash .claude/skills/flash-corne/flash.sh download`. Report the build (title + commit) it found so the user knows it's current.

2. **Decide which halves to flash**
   - Keymap / behavior / combo / `.conf` changes → usually **only the left (central)** half needs reflashing.
   - ZMK version bumps or split-config changes → flash **both**.
   - If unsure, ask. Default to **left only** for keymap edits.

3. **Flash each half, one at a time**
   For each half:
   - Tell the user: *"Put the **<half>** half into bootloader now — NAV layer + top outer corner (left corner = left half, right corner = right half), or double-tap the reset button."*
   - Run `bash .claude/skills/flash-corne/flash.sh flash <half>` **with `run_in_background: true`** — the script polls with `sleep`, which is blocked when run in the foreground via the Bash tool. Read the task output file when it completes.
   - Report success/failure.

4. **Verify (optional)**
   `ioreg -p IOUSB -l | grep '"USB Product Name" = "Corne"'` confirms the half rebooted back into ZMK firmware (so it isn't bricked / still stuck in the bootloader).

## Notes

- macOS `cp` prints `could not copy extended attributes ... Device not configured` — this is **normal**; only metadata fails, the firmware payload transfers fine. The script treats `NICENANO` **unmounting** as the success signal.
- Only the USB-connected half can enter the bootloader. To do both halves, flash one, then plug USB into / bootloader the other.
- Bootloader keys live on the **NAV layer top outer corners** (added to `config/corne.keymap`): left pinky-top = left half, right pinky-top = right half. They only work after the keymap that defines them has itself been flashed once.
- Repo override: set `CORNE_REPO` if the GitHub repo isn't `mseok/zmk-config`. Wait override: `WAIT_SECS`.
- Direct use (no agent): the user can also just run `bash .claude/skills/flash-corne/flash.sh both` in a terminal and press the bootloader combo when prompted.
