"""
DK-BC dual uploader â€” same album folder â†’ Bandcamp draft + DistroKid form fill
IN PARALLEL (two Chrome tabs).

Starts DistroKid first (fast form queue), Bandcamp runs at the same time
(longer wav waits). User can review DistroKid while Bandcamp finishes, then
check Bandcamp during DistroKid's quieter end / before the next album.

Settings: upload-settings.txt (full DistroKid options).
Bandcamp only uses album= / track= prices (synced to prices.txt).

Never final-publishes on either store.
"""
from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from album_media import (
    album_title_from_folder,
    app_dir,
    largest_jpg,
    numbered_wavs,
    title_from_filename,
)
from upload_settings import load_upload_settings

import bandcamp_upload_album as bc
import distrokid_upload_album as dk

CDP = "http://127.0.0.1:9222"
_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def sync_prices_from_settings() -> tuple[str, str]:
    """Write prices.txt from upload-settings so Bandcamp's load_prices() works."""
    s = load_upload_settings(app_dir())
    album, track = s.album_price, s.track_price
    path = app_dir() / "prices.txt"
    path.write_text(
        "# Synced from upload-settings.txt (album= / track=) â€” Bandcamp reads this file\n"
        f"album={album}\n"
        f"track={track}\n",
        encoding="utf-8",
    )
    return album, track


def preview_folder(folder: Path) -> None:
    s = load_upload_settings(app_dir())
    album, track = sync_prices_from_settings()
    wavs = numbered_wavs(folder)
    cover = largest_jpg(folder)
    print("Album title:", album_title_from_folder(folder), flush=True)
    print("Cover:", cover.name, flush=True)
    print(f"Prices (from upload-settings): album={album}  track={track}", flush=True)
    print(f"Artist/settings: artist={s.artist!r} instrumental={s.instrumental} ai={s.ai}", flush=True)
    print("Tracks:", len(wavs), flush=True)
    for w in wavs:
        print(" ", w.name, "->", title_from_filename(w.name), flush=True)


def ensure_dual_tabs() -> None:
    """Claim DistroKid + Bandcamp tabs for this process (open new on first use).

    Later connect()/Cdp() reuse these target ids — never steal another
    instance's tabs by URL matching.
    """
    from cdp_owned_tab import claim_tab, owned_tab_ids

    before = set(owned_tab_ids())
    if "distrokid" not in before:
        _log("Opening owned DistroKid tab for this instance…")
    dk_page = claim_tab("distrokid", "https://distrokid.com/new/", cdp=CDP)
    if "bandcamp" not in before:
        _log("Opening owned Bandcamp tab for this instance…")
    bc_page = claim_tab("bandcamp", "https://bandcamp.com/", cdp=CDP)
    time.sleep(0.2)
    _log(f"Owned tabs: DistroKid={dk_page.get('id')}  Bandcamp={bc_page.get('id')}")


def smoke_open_pages() -> int:
    """Open / refresh both tabs â€” no album upload."""
    if not bc.cdp_alive():
        print("ERROR: Chrome CDP not on 9222. Run 2_start_chrome.bat and log into BOTH sites.", flush=True)
        return 1
    ensure_dual_tabs()
    # Touch each site on its own tab connection
    dk_ok = bc_ok = False
    try:
        cdp_dk = dk.Cdp()
        cdp_dk.navigate("https://distrokid.com/new/")
        snap_dk = cdp_dk.evaluate("({href: location.href, title: document.title})") or {}
        cdp_dk.close()
        _log(f"DistroKid: {snap_dk}")
        dk_ok = "distrokid.com" in str((snap_dk or {}).get("href") or "")
    except Exception as e:
        _log(f"DistroKid smoke error: {e}")
    try:
        cdp_bc = bc.connect()
        cdp_bc.call("Page.enable")
        cdp_bc.call("Page.navigate", {"url": "https://bandcamp.com/"})
        time.sleep(2)
        snap_bc = cdp_bc.eval("({href: location.href, title: document.title})")["value"]
        cdp_bc.close()
        _log(f"Bandcamp: {snap_bc}")
        bc_ok = "bandcamp.com" in str((snap_bc or {}).get("href") or "")
    except Exception as e:
        _log(f"Bandcamp smoke error: {e}")
    print("Smoke done â€” no album was uploaded.", flush=True)
    return 0 if (dk_ok and bc_ok) else 2


def _run_distrokid(folder: Path, force: bool) -> tuple[str, int, str]:
    try:
        _log("[DistroKid] starting form fill (parallel)â€¦")
        code = int(dk.run_upload(folder, force=force, dry_run=False) or 0)
        _log("[DistroKid] finished â€” review DistroKid in Chrome while Bandcamp may still run.")
        return ("distrokid", code, "")
    except SystemExit as e:
        return ("distrokid", 1, str(e))
    except Exception as e:
        return ("distrokid", 1, str(e))


def _run_bandcamp(folder: Path, album: str, track: str, force: bool) -> tuple[str, int, str]:
    try:
        _log("[Bandcamp] starting draft upload (parallel)â€¦")
        bc.run_upload(folder, album, track, force=force)
        _log("[Bandcamp] finished â€” review Bandcamp draft in Chrome.")
        return ("bandcamp", 0, "")
    except SystemExit as e:
        return ("bandcamp", 1, str(e))
    except Exception as e:
        return ("bandcamp", 1, str(e))


def run_both(folder: Path, *, force: bool = False, dry_run: bool = False) -> int:
    folder = folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    album, track = sync_prices_from_settings()
    preview_folder(folder)

    if dry_run:
        print("Dry run only â€” no browser actions.", flush=True)
        return 0

    if not bc.cdp_alive():
        raise SystemExit(
            "Chrome CDP not reachable at http://127.0.0.1:9222\n"
            "Start 2_start_chrome.bat, log into Bandcamp AND DistroKid, then retry."
        )

    ensure_dual_tabs()

    print("", flush=True)
    print("=" * 60, flush=True)
    print("PARALLEL â€” DistroKid + Bandcamp (same album, two tabs)", flush=True)
    print("DistroKid starts first (fast). Check it while Bandcamp uploads.", flush=True)
    print("When Bandcamp finishes, check that draft too â€” then next album if both OK.", flush=True)
    print("=" * 60, flush=True)

    results: dict[str, tuple[int, str]] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        # DistroKid first so its form is filling ASAP
        fut_dk = pool.submit(_run_distrokid, folder, force)
        time.sleep(0.4)  # tiny head-start only
        fut_bc = pool.submit(_run_bandcamp, folder, album, track, force)
        for fut in as_completed([fut_dk, fut_bc]):
            name, code, err = fut.result()
            results[name] = (code, err)
            if err:
                _log(f"[{name}] error: {err}")

    dk_code, dk_err = results.get("distrokid", (1, "missing"))
    bc_code, bc_err = results.get("bandcamp", (1, "missing"))

    print("", flush=True)
    print("=" * 60, flush=True)
    print(f"DistroKid: {'OK' if dk_code == 0 else 'ISSUE'}  Bandcamp: {'OK' if bc_code == 0 else 'ISSUE'}", flush=True)
    print("Review BOTH tabs in Chrome. If both look good â†’ next album.", flush=True)
    print("This tool does NOT publish on either site.", flush=True)
    print("=" * 60, flush=True)

    if dk_code != 0 or bc_code != 0:
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="DK-BC dual uploader (Bandcamp + DistroKid in parallel)")
    p.add_argument("folder", nargs="?", help="Album folder path")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="Bypass album-exists safeguards where supported")
    p.add_argument("--smoke", action="store_true", help="Only open Bandcamp + DistroKid tabs (no upload)")
    args = p.parse_args()

    if args.smoke:
        return smoke_open_pages()

    if not args.folder:
        raise SystemExit("Usage: dk_bc_upload_album.py <album-folder> [--dry-run] [--force] | --smoke")

    return run_both(Path(args.folder), force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
