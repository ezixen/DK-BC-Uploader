<div align="center">
  <img src="images/uploader-logo.png" alt="uploader logo" width="420"/>
</div>

# DK-BC Uploader (DistroKid + Bandcamp)

**GitHub (latest always):** https://github.com/ezixen/DK-BC-Uploader  
**[Latest release](https://github.com/ezixen/DK-BC-Uploader/releases/latest)** · **[ZIP (scripts + EXE)](https://github.com/ezixen/DK-BC-Uploader/releases/latest/download/DK-BC-uploader.zip)** · **[EXE only](https://github.com/ezixen/DK-BC-Uploader/releases/latest/download/DK-BC-Uploader-exe.zip)**  

Unpack either ZIP → you get a **`DK-BC-uploader/`** folder (no need to create one).

---

One tool for **one album folder** → fills **both at the same time** (two Chrome tabs):

1. **DistroKid** — starts first (fast form / parallel track queue). Check this tab while Bandcamp is still working.  
2. **Bandcamp** — draft upload in parallel (wavs take longer). When it finishes, check that draft too.

Then, if **both** look OK → paste the next album.  
**Never** final-publishes on either store.

Same folder / filename rules as [DistroKid-uploader](https://github.com/ezixen/DistroKid-uploader) and [BandCamp-uploader](https://github.com/ezixen/BandCamp-uploader).

## Settings

Edit **`upload-settings.txt`** once (same format as DistroKid-uploader).

| Consumer | What it reads |
|---|---|
| **DistroKid** | Full file (prices, releaser, real name, AI, credits, Audiomack, mandatory boxes, …) |
| **Bandcamp** | Only **`album=`** / **`track=`** prices (synced into `prices.txt` each run) |

## Option A — EXE (easiest, no install)

1. Unpack → open **`DK-BC-uploader/app/DK-BC-Uploader/`**  
2. Edit **`upload-settings.txt`** beside the exe  
3. Double-click **`DK-BC-Uploader.exe`**  
4. Log into **DistroKid and Bandcamp** in the Chrome window (once per PC; DistroKid 2FA if asked)  
5. Paste one album folder path — **DistroKid + Bandcamp run in parallel** (DistroKid starts first)  
6. Review DistroKid when it finishes (Bandcamp may still be uploading), then review Bandcamp — if both OK, next album  

**Several instances at once:** start debug Chrome once, then run multiple EXE/script
processes — each opens its **own DistroKid + Bandcamp tabs** and keeps those.

Chrome profile: **`%LOCALAPPDATA%\DK-BC-Uploader\`** (not inside the app folder).

Rebuild: `app/build_exe.ps1`

## Option B — PowerShell scripts

| Step | File | Purpose |
|---|---|---|
| 0 | `0_associate_ps1.bat` | Bind `.ps1` to Windows PowerShell |
| 1 | `1_install.bat` | Python + deps (first time) |
| 2 | `2_start_chrome.bat` | Debug Chrome; log into **both** sites |
| 3 | `3_check_titles.bat` | Optional preview (`--dry-run`) |
| 4 | `4_dk_bc_uploader.bat` | Dual fill for album folder(s) |

Smoke (open pages only, no upload):

```text
.\4_dk_bc_uploader.bat --smoke
```

Prefer **`.bat`** step files. Short guide: [`how2use.txt`](how2use.txt)

## What each step does

**DistroKid (starts first):** song count, free stores, identity, songwriters, cover, parallel track file queue, titles/flags, AI modal, Apple credits, Audiomack, optional mandatory boxes — **no final submit**.

**Bandcamp (same time):** album title, prices, cover, numbered wavs (title-only, keeps `...`), **Save draft** only.

**Timing:** DistroKid is usually ready to review sooner. Use that time while Bandcamp finishes; then check Bandcamp before the next album.

Album-exists safeguard on both sides when possible (warn / skip; `--force` to override).

## File naming

```text
01. ezixen - intro.wav
07. ezixen - yes, and....wav   → title: yes, and...
```

## Safety

No publish · no passwords in repo · respect DistroKid + Bandcamp terms  

Siblings: https://github.com/ezixen/DistroKid-uploader · https://github.com/ezixen/BandCamp-uploader

## Stuck Chrome / Temp

See [`docs/DEV_REMOVE_STUCK_BROWSER_PROFILES.md`](docs/DEV_REMOVE_STUCK_BROWSER_PROFILES.md) and [`docs/SAFE_MODE_DELETE_STUCK_CHROME.bat`](docs/SAFE_MODE_DELETE_STUCK_CHROME.bat).
