# Bandcamp Upload Playbook

**GitHub (latest always):** https://github.com/ezixen/BandCamp-uploader · [releases](https://github.com/ezixen/BandCamp-uploader/releases/latest)

Repeatable steps for uploading **one album** to Bandcamp. Update this file whenever the process is smoothed.

Artist: **ezixen**  
Related plan: [`../main.md`](../main.md) (canonical rules)  
Simple agent checklist: [`workflow-guidance.md`](workflow-guidance.md)

---

## Preconditions

1. External Chrome is running with remote debugging on **`127.0.0.1:9222`** and **`--remote-allow-origins=*`**.
2. Isolated profile: `--user-data-dir=D:\Dev\musicstuff\local-secrets\chrome-debug-profile`.
3. User is logged into Bandcamp in that browser (agent does not handle passwords).
4. User provided one album folder path.
5. Defaults:
   - Album price: **9.99**
   - Track price: **0.99** each
   - Cover: largest `.jpg` by bytes
   - Tracks: only `.wav` files whose names **start with a number**, in numeric order

---

## What to fill (only these)

- Album title (from folder name; strip `ezixen` if present)
- Album cover (largest jpg)
- Album price `9.99`
- Track titles (from wav filenames; strip `ezixen`)
- Track prices `0.99`

Do **not** fill other metadata. Do **not** publish — user publishes manually after review.

---

## Title rules

Track title = **only the song title** (no artist, no track number, no extension).

1. Start from the **filename** (not folder name for tracks).
2. Remove the extension.
3. Remove leading track number (`01`, `01.`, `02 -`, …).
4. Remove artist name **`ezixen`** if present (prefix/suffix; separators `-`, `_`, `–`, spaces).
5. Replace every **`_`** with **`?`**.
6. Trim leftover separators and whitespace.
7. That string is the **track title**. Do not invent alternate titles.

Example: `01. ezixen - Midnight Drift.wav` → `Midnight Drift`  
Example: `02. ezixen - what's the password, doll_.wav` → `what's the password, doll?`

---

## Upload procedure (one album)

### A. Open new album

1. Dashboard → click **`+ Add`**.
2. Snapshot the page; map cover, prices, track upload, title fields before editing.

### B. Album-level fields

1. Album title from folder name (cleaned).
2. Album price `9.99`.
3. Cover = largest `.jpg` in the folder.

### C. Tracks (strict: one upload at a time)

Only `.wav` files starting with a number, sorted by that number.

For each track:

1. Add / choose the next wav.
2. **Wait** until upload completes.
3. Set title; set price `0.99`.
4. Confirm order; then next file.

### D. Finish — human gate

1. Recheck cover, prices, titles, order.
2. Click **Save Album Draft**. **Do not publish.**
3. Tell the user the draft is ready (editor URL + short summary). Prefer leaving the **visible** debug Chrome on that page so they can fix small mistakes and publish right away.
4. Wait for the user to review/publish and send the **next folder** — do not start another album until then.

---

## Browser launch (reference)

```powershell
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$userData = "D:\Dev\musicstuff\local-secrets\chrome-debug-profile"
Start-Process $chrome -ArgumentList @(
  "--remote-debugging-port=9222",
  "--remote-allow-origins=*",
  "--user-data-dir=$userData",
  "https://bandcamp.com/login"
)
```

Drive UI via CDP on `9222` (DevTools MCP attached to this browser, or Python websocket + CDP).

---

## Lessons (update during test runs)

- External Chrome must use `--remote-debugging-port=9222` **and** `--remote-allow-origins=*` or CDP/WebSocket clients get `403 Forbidden`.
- Use isolated `--user-data-dir` under `local-secrets/chrome-debug-profile` (gitignored).
- If port 9222 is already taken by an old Chrome without allow-origins, kill that listener and relaunch with the flags above.
- Cursor internal browser ≠ Bandcamp login session; always use the external debug Chrome.
- `+ Add` lives in `<menu-bar>` **shadow DOM**; Album URL is `https://ezixen.bandcamp.com/edit_album`.
- File inputs on edit album: `[0]` cover (`.art-upload`), `[1]` bonus items, track audio under `li.add-audio`.
- Automation helper: `scripts/bandcamp_upload_album.py <album-folder>` (CDP; draft save only).
- Title cleanup: filenames like `01. ezixen - title.wav` → `title` only (no number, no artist, no extension). Allow leading `07,` (comma) as a track-number separator; keep internal hyphens (`little-boy`); replace `_` with `?`.
