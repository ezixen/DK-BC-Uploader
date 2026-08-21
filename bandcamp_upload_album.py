"""
Bandcamp album draft uploader (no AI).

Drives a visible Chrome via Chrome DevTools Protocol (CDP) on port 9222.
Fills only: album title, cover (largest jpg/jpeg), prices from prices.txt,
numbered .wav tracks (title-only). Saves draft. Does NOT publish.

Filename pattern:  01. Artist - track title.wav
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import websocket

from cdp_owned_tab import claim_tab

CDP = "http://127.0.0.1:9222"
# Chrome is launched with --remote-allow-origins=CDP_ORIGIN, so the CDP
# WebSocket handshake must send a matching Origin or Chrome answers 403.
CDP_ORIGIN = "http://127.0.0.1"
EDIT_ALBUM = "https://ezixen.bandcamp.com/edit_album"


def app_dir() -> Path:
    """Folder next to the running script or frozen EXE (writable: prices, chrome profile)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


REPO_ROOT = app_dir()
PRICES_FILE = REPO_ROOT / "prices.txt"


def load_prices() -> tuple[str, str]:
    """Read album/track prices from prices.txt every run. Defaults 9.99 / 0.99."""
    album, track = "9.99", "0.99"
    if PRICES_FILE.is_file():
        for raw in PRICES_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip().lower(), val.strip()
            if key == "album" and val:
                album = val
            elif key == "track" and val:
                track = val
    return album, track


def title_from_filename(name: str) -> str:
    """
    Expect: 01. Artist - track title.wav
    Result: track title only (_ → ?).
    """
    stem = Path(name).stem
    stem = re.sub(r"^\d+[.,\s-]*", "", stem).strip()
    if " - " in stem:
        title = stem.split(" - ", 1)[1]
    else:
        title = re.sub(r"(?i)\bezixen\b", "", stem)
    title = title.replace("_", "?")
    # Keep trailing "..." / punctuation that belongs to the title (do NOT strip ".")
    return title.strip(" -")


def album_title_from_folder(folder: Path) -> str:
    stem = folder.name
    if " - " in stem:
        # Prefer text after first " - " (Artist - Album Name)
        left, right = stem.split(" - ", 1)
        if re.search(r"(?i)ezixen", left) or len(left) < 40:
            stem = right
    else:
        stem = re.sub(r"(?i)\bezixen\b", "", stem)
    # Keep "..." in album names; only trim spaces / dashes / underscores
    return re.sub(r"\s{2,}", " ", stem).strip(" -_")


def numbered_wavs(folder: Path) -> list[Path]:
    wavs = [p for p in folder.iterdir() if p.suffix.lower() == ".wav" and re.match(r"^\d", p.name)]
    wavs.sort(key=lambda p: int(re.match(r"^(\d+)", p.name).group(1)))
    return wavs


def largest_jpg(folder: Path) -> Path:
    jpgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg"}]
    if not jpgs:
        raise SystemExit("No jpg/jpeg cover found in folder")
    return max(jpgs, key=lambda p: p.stat().st_size)



def cdp_alive() -> bool:
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=2)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


class Cdp:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(
            ws_url, timeout=60, suppress_origin=True, header=[f"Origin: {CDP_ORIGIN}"]
        )
        self.n = 0

    def call(self, method: str, params: dict | None = None, timeout: float = 60):
        self.n += 1
        msg = {"id": self.n, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = json.loads(self.ws.recv())
            if data.get("id") == msg["id"]:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})
        raise TimeoutError(method)

    def eval(self, expression: str, timeout: float = 60):
        return self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )["result"]

    def close(self):
        self.ws.close()


def pick_bandcamp_page() -> dict:
    """Legacy URL match — prefer claim_owned_bandcamp_tab() for multi-instance safety."""
    pages = json.load(urllib.request.urlopen(f"{CDP}/json/list"))
    for p in pages:
        if p.get("type") == "page" and "edit_album" in p.get("url", ""):
            return p
    for p in pages:
        if p.get("type") == "page" and "bandcamp.com" in p.get("url", ""):
            return p
    for p in pages:
        if p.get("type") == "page":
            return p
    raise SystemExit("No Chrome page targets on CDP 9222")


def claim_owned_bandcamp_tab() -> dict:
    """Open a new Bandcamp tab on first use; reuse this process's tab afterward."""
    return claim_tab("bandcamp", "https://bandcamp.com/", cdp=CDP)


def connect() -> Cdp:
    page = claim_owned_bandcamp_tab()
    print(f"Using owned Bandcamp tab id={page.get('id')}", flush=True)
    return Cdp(page["webSocketDebuggerUrl"])


def set_input_value(cdp: Cdp, selector: str, value: str):
    js = f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) return {{ok:false, reason:'missing'}};
  el.focus();
  el.value = {json.dumps(value)};
  el.dispatchEvent(new Event('input', {{bubbles:true}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  el.blur();
  return {{ok:true, value: el.value}};
}})()
"""
    return cdp.eval(js)["value"]


def set_file_on_indexed_input(cdp: Cdp, index: int, path: Path):
    doc = cdp.call("DOM.getDocument", {"depth": -1})
    root = doc["root"]["nodeId"]
    mark = cdp.eval(
        f"""
(() => {{
  const files = [...document.querySelectorAll('input[type=file]')];
  files.forEach((el,i) => el.setAttribute('data-bc-idx', String(i)));
  return {{count: files.length, has: files.length > {index}}};
}})()
"""
    )["value"]
    if not mark.get("has"):
        raise RuntimeError(f"file input index {index} missing; count={mark.get('count')}")
    node = cdp.call(
        "DOM.querySelector",
        {"nodeId": root, "selector": f'input[type=file][data-bc-idx="{index}"]'},
    )
    node_id = node["nodeId"]
    if not node_id:
        raise RuntimeError("querySelector returned empty nodeId")
    cdp.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(path)]})
    cdp.eval(
        f"""
(() => {{
  const el = document.querySelector('input[type=file][data-bc-idx="{index}"]');
  if (el) el.dispatchEvent(new Event('change', {{bubbles:true}}));
  return true;
}})()
"""
    )


def wait_until(cdp: Cdp, expression: str, timeout: float, label: str) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        val = cdp.eval(expression)["value"]
        if val:
            print(f"  OK {label}: {val}", flush=True)
            return True
        time.sleep(2)
    print(f"  TIMEOUT waiting for {label}", flush=True)
    return False


def track_row_count(cdp: Cdp) -> int:
    return int(
        cdp.eval(
            """
(() => {
  const rows = [...document.querySelectorAll('ol.tracks > li')]
    .filter(li => !li.classList.contains('add-audio'));
  return rows.length;
})()
"""
        )["value"]
    )


def set_last_track_fields(cdp: Cdp, title: str, price: str):
    js = f"""
(() => {{
  const rows = [...document.querySelectorAll('ol.tracks > li')]
    .filter(li => !li.classList.contains('add-audio'));
  if (!rows.length) return {{ok:false, reason:'no rows'}};
  const row = rows[rows.length - 1];
  const titleEl = row.querySelector('input[name*="title_"]')
    || row.querySelector('input.title');
  const priceEl = row.querySelector('input[name*="price_"]')
    || row.querySelector('input.price');
  const out = {{ok:true}};
  if (titleEl) {{
    titleEl.focus();
    titleEl.value = {json.dumps(title)};
    titleEl.dispatchEvent(new Event('input', {{bubbles:true}}));
    titleEl.dispatchEvent(new Event('change', {{bubbles:true}}));
    out.title = titleEl.value;
  }} else out.missingTitle = true;
  if (priceEl) {{
    priceEl.focus();
    priceEl.value = {json.dumps(price)};
    priceEl.dispatchEvent(new Event('input', {{bubbles:true}}));
    priceEl.dispatchEvent(new Event('change', {{bubbles:true}}));
    out.price = priceEl.value;
  }} else out.missingPrice = true;
  return out;
}})()
"""
    return cdp.eval(js)["value"]


def upload_busy(cdp: Cdp) -> bool:
    return bool(
        cdp.eval(
            """
(() => {
  if (/uploading/i.test(document.body.innerText)) return true;
  if (document.querySelector('.html5-upload-wrapper.uploading, .uploading')) return true;
  return false;
})()
"""
        )["value"]
    )


def ensure_new_album_page(cdp: Cdp):
    at = cdp.eval("location.href")["value"]
    # Fresh album editor (no id yet) or navigate to blank new album
    if "edit_album" in at and "id=" not in at:
        return
    print("Opening new album editor...", flush=True)
    cdp.call("Page.navigate", {"url": EDIT_ALBUM})
    time.sleep(4)
    # Confirm logged in (title field present)
    ok = cdp.eval('!!document.querySelector(\'input[name="album.title"]\')')["value"]
    if not ok:
        raise SystemExit(
            "Album editor not available — log into Bandcamp in the debug Chrome window, then retry."
        )


def album_exists_on_bandcamp(cdp: Cdp, album_title: str) -> dict:
    """Best-effort: look for album title on the public music index before creating a new draft."""
    want = album_title.strip()
    cdp.call("Page.enable")
    cdp.call("Page.navigate", {"url": "https://ezixen.bandcamp.com/music"})
    time.sleep(2.5)
    js = f"""
(() => {{
  const want = {json.dumps(want)}.trim().toLowerCase();
  if (!want) return {{ exists: false, matches: [], url: location.href }};
  const links = Array.from(document.querySelectorAll('a'));
  const matches = [];
  for (const a of links) {{
    const t = (a.innerText || a.textContent || a.getAttribute('title') || '').trim();
    const href = a.href || '';
    if (!t) continue;
    const tl = t.toLowerCase();
    if (tl === want || tl.includes(want)) {{
      if (/\\/album\\//.test(href) || tl === want) matches.push(t.slice(0, 120));
    }}
  }}
  const body = (document.body && document.body.innerText || '').toLowerCase();
  if (!matches.length && body.includes(want)) matches.push({json.dumps(want)});
  return {{ exists: matches.length > 0, matches: [...new Set(matches)].slice(0, 10), url: location.href }};
}})()
"""
    try:
        raw = cdp.eval(js)
        val = raw.get("value") if isinstance(raw, dict) else raw
    except Exception as e:
        return {"exists": False, "matches": [], "url": "", "error": str(e)}
    return val if isinstance(val, dict) else {"exists": False, "matches": [], "url": ""}


def run_upload(folder: Path, album_price: str, track_price: str, *, force: bool = False):
    wavs = numbered_wavs(folder)
    if not wavs:
        raise SystemExit("No numbered .wav files found (names must start with a digit)")
    cover = largest_jpg(folder)
    album_title = album_title_from_folder(folder)

    print("Album title:", album_title, flush=True)
    print("Cover:", cover.name, cover.stat().st_size, flush=True)
    print("Prices file:", PRICES_FILE, flush=True)
    print("Album price:", album_price, "| Track price:", track_price, flush=True)
    print("Tracks:", len(wavs), flush=True)
    for w in wavs:
        print(" ", w.name, "->", title_from_filename(w.name), flush=True)

    cdp = connect()
    cdp.call("Page.enable")
    cdp.call("DOM.enable")
    cdp.call("Runtime.enable")

    print(f"Checking Bandcamp music page for existing album: {album_title!r}", flush=True)
    check = album_exists_on_bandcamp(cdp, album_title)
    if check.get("exists") and not force:
        print("WARNING: Album appears to ALREADY EXIST on Bandcamp — will NOT overwrite.", flush=True)
        print(f"  Checked via: {check.get('url')}", flush=True)
        for m in check.get("matches") or []:
            print(f"  match: {m}", flush=True)
        print("  Re-run with --force only if you intentionally want a new draft anyway.", flush=True)
        cdp.close()
        raise SystemExit(3)
    if check.get("exists") and force:
        print("WARNING: Album may already exist, but --force was set. Continuing…", flush=True)

    ensure_new_album_page(cdp)

    print("Set album title/price...", flush=True)
    print(set_input_value(cdp, 'input[name="album.title"]', album_title), flush=True)
    print(set_input_value(cdp, 'input[name="album.price"]', album_price), flush=True)

    print("Upload cover...", flush=True)
    set_file_on_indexed_input(cdp, 0, cover)
    wait_until(
        cdp,
        """
(() => {
  const art = document.querySelector('.art-upload img, .art-upload-wrapper img, dd.art-upload-wrapper img');
  if (art && art.src && !/blank|placeholder/i.test(art.src)) return art.src.slice(0,80);
  const hid = document.querySelector('input[name="album.art_id"]');
  if (hid && hid.value) return 'art_id=' + hid.value;
  return false;
})()
""",
        timeout=180,
        label="cover uploaded",
    )

    for i, wav in enumerate(wavs, start=1):
        title = title_from_filename(wav.name)
        before = track_row_count(cdp)
        print(f"\n[{i}/{len(wavs)}] Upload {wav.name}", flush=True)
        idx = cdp.eval(
            """
(() => {
  const files = [...document.querySelectorAll('input[type=file]')];
  files.forEach((el,i) => el.setAttribute('data-bc-idx', String(i)));
  const add = document.querySelector(
    'li.add-audio input[type=file], .add-audio input[type=file], .left-panel.audio-upload input[type=file]'
  );
  if (!add) return {ok:false};
  return {ok:true, idx: Number(add.getAttribute('data-bc-idx'))};
})()
"""
        )["value"]
        if not idx.get("ok"):
            raise RuntimeError("Could not find add-audio file input")
        set_file_on_indexed_input(cdp, int(idx["idx"]), wav)

        deadline = time.time() + 900
        while time.time() < deadline:
            rows = track_row_count(cdp)
            busy = upload_busy(cdp)
            if rows > before and not busy:
                print(f"  rows={rows}", flush=True)
                break
            if rows > before and busy:
                print(f"  uploading... rows={rows}", flush=True)
            time.sleep(3)
        else:
            raise RuntimeError(f"Timed out uploading {wav.name}")

        time.sleep(2)
        fields = set_last_track_fields(cdp, title, track_price)
        print("  fields:", fields, flush=True)
        wait_until(
            cdp,
            "!(/uploading/i.test(document.body.innerText))",
            timeout=120,
            label="uploader idle",
        )

    print("\nSaving draft (not publishing)...", flush=True)
    save = cdp.eval(
        """
(() => {
  const btns = [...document.querySelectorAll('button, input[type=submit], a')];
  const b = btns.find(el => /save album draft/i.test(el.innerText || el.value || ''));
  if (!b) return {ok:false};
  b.click();
  return {ok:true, text:(b.innerText||b.value||'').trim()};
})()
"""
    )["value"]
    print("save:", save, flush=True)
    time.sleep(5)
    summary = cdp.eval(
        """
(() => ({
  url: location.href,
  albumTitle: (document.querySelector('input[name="album.title"]')||{}).value,
  albumPrice: (document.querySelector('input[name="album.price"]')||{}).value,
  tracks: [...document.querySelectorAll('ol.tracks > li')]
    .filter(li => !li.classList.contains('add-audio')).length
}))()
"""
    )["value"]
    print("SUMMARY:", json.dumps(summary, indent=2), flush=True)
    cdp.close()
    print("DONE — draft only. Review in Chrome, then publish manually.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Upload one Bandcamp album draft via CDP (no AI).")
    parser.add_argument("album_folder", type=Path, help="Local album folder path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list derived album title / cover / track titles; do not touch the browser",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if album title seems to already exist on Bandcamp",
    )
    args = parser.parse_args()
    folder = args.album_folder
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    album_price, track_price = load_prices()
    wavs = numbered_wavs(folder)
    cover = largest_jpg(folder)
    print("Album title:", album_title_from_folder(folder), flush=True)
    print("Cover:", cover.name, flush=True)
    print("Prices:", PRICES_FILE, f"album={album_price}", f"track={track_price}", flush=True)
    print("Tracks:", len(wavs), flush=True)
    for w in wavs:
        print(" ", w.name, "->", title_from_filename(w.name), flush=True)

    if args.dry_run:
        print("Dry run only — no browser actions.", flush=True)
        return

    if not cdp_alive():
        raise SystemExit(
            "Chrome CDP not reachable at http://127.0.0.1:9222\n"
            "Start debug Chrome first (2_start_chrome.bat or BandCamp-Uploader.exe),\n"
            "log into Bandcamp in that window, then retry."
        )

    run_upload(folder, album_price, track_price, force=args.force)


if __name__ == "__main__":
    main()
