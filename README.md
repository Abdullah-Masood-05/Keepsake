<div align="center">

<img src="src/assets/logo.png" alt="Keepsake logo" width="128" height="128">

# Keepsake

**Downloads with a memory.**

A video, audio and thumbnail downloader for Windows, Linux and Android, built from one codebase.

[![Release](https://img.shields.io/badge/release-v2.1.0-blue)](#install)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20Android-informational)](#platforms)
[![CI](https://img.shields.io/github/actions/workflow/status/OWNER/REPO/build.yml?label=build)](.github/workflows/build.yml)
[![License](https://img.shields.io/badge/license-not%20yet%20chosen-lightgrey)](#license)

[![Tauri](https://img.shields.io/badge/Tauri-2-24C8D8?logo=tauri&logoColor=white)](https://v2.tauri.app)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Bun](https://img.shields.io/badge/Bun-1.4-000000?logo=bun&logoColor=white)](https://bun.sh)
[![Rust](https://img.shields.io/badge/Rust-1.90%2B-000000?logo=rust&logoColor=white)](https://www.rust-lang.org)

</div>

---

## Contents

- [Overview](#overview)
- [Features](#features)
- [Screens](#screens)
- [Platforms](#platforms)
- [Supported sites](#supported-sites)
- [Install](#install)
- [Build from source](#build-from-source)
- [Releasing](#releasing)
- [Settings](#settings)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Security and privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Credits](#credits)
- [Legal](#legal)
- [Contributing](#contributing)
- [License](#license)

## Overview

Paste a link, preview it, pick a format (a video quality, an audio format and bitrate, or the thumbnail) and download it. Finished downloads are kept in a searchable Library, so you can find and reopen them later.

Keepsake is a [Tauri 2](https://v2.tauri.app) app. The interface is React 19 with Tailwind CSS 4, and all extraction, download and conversion logic is TypeScript in [`src/engine`](src/engine). The Rust code in [`src-tauri`](src-tauri) is a thin shell: it registers plugins, shows the window and launches the bundled yt-dlp on desktop.

## Features

- **Video, audio or thumbnail.** One format picker with three modes:
  - **Video:** Best, or a specific height (for example 1080p60), with an optional "Prefer H.264" switch for maximum compatibility.
  - **Audio:** MP3, M4A, OPUS, WAV or FLAC. MP3 offers 128, 192, 256 or 320 kbps; the other formats keep the source quality or are lossless.
  - **Thumbnail:** original format, PNG or JPG.
- **Link preview.** Title, channel, duration and thumbnail before you download, plus an Advanced table of the raw streams (desktop).
- **Playlists** on desktop, with per-item progress.
- **Download queue** with 1 to 10 parallel downloads, live speed, ETA and cancel.
- **Library** of finished, failed and cancelled downloads, with search (title, channel or site), filters by kind and status, and sorting by newest, oldest or title.
- **Cover art and metadata** embedded into the file (optional).
- **Clipboard detection** that offers a copied link when the app gets focus (optional).
- **Cookies from your browser** for age-gated, private or members-only content you can already view (desktop, optional).
- **In-app notifications** when a download finishes or fails, with friendly error messages and a "Show details" disclosure.
- **Dark and light themes**, or follow the system setting.
- **Keyboard shortcuts** for every page and the main actions.
- **Responsive layout:** sidebar on desktop, bottom tab bar on phones.

## Screens

| Page | What it does |
|---|---|
| **Home** | Paste a link, see the preview, choose a format and start the download. Also shows active downloads, recent activity and the save folder. |
| **Downloads** | The queue: every running and finished job with progress, speed and ETA. Filter by All, Active, Done or Failed, cancel jobs, or clear finished ones. |
| **Library** | Everything you have downloaded. Search, filter by kind (video, audio, thumbnail) and status, sort, and open a file or its folder. |
| **Settings** | Save folder, parallel downloads, cookies, thumbnail embedding, H.264 preference, clipboard detection, theme, and the installed yt-dlp and ffmpeg versions. |

## Platforms

| Platform | Packages | How downloads work |
|---|---|---|
| Windows 10 / 11 (x64) | NSIS `.exe`, `.msi` | Bundled yt-dlp sidecar, with ffmpeg for merging and conversion |
| Linux (x64) | `.deb`, `.rpm`, `.AppImage` | Bundled yt-dlp sidecar, with ffmpeg for merging and conversion |
| Android 7.0+ (API 24) | `.apk` | youtubei.js in the app, ffmpeg.wasm for audio conversion. YouTube only, single-file formats |

## Supported sites

| | Desktop (Windows, Linux) | Android |
|---|---|---|
| YouTube | Yes, all qualities | Yes, single-file formats only (see below) |
| Other sites | 1,000+ sites supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) | No |
| Playlists | Yes | No |
| DRM-protected content | No | No |

On Android, video is limited to formats YouTube serves as one file with audio inside (progressive MP4, usually 360p), or audio only. Higher resolutions need separate video and audio streams merged with ffmpeg, which only the desktop app does.

DRM-protected streams (most paid streaming services) cannot be downloaded on any platform.

## Install

Download the latest installer for your platform from the **Releases** page of this repository.

| Platform | File | Notes |
|---|---|---|
| Windows | `Keepsake_<version>_x64-setup.exe` (NSIS) | Installs for the current user, no admin rights needed |
| Windows | `Keepsake_<version>_x64_en-US.msi` | For managed or per-machine installs |
| Linux | `.deb` (Debian, Ubuntu) / `.rpm` (Fedora, openSUSE) | Installs system-wide |
| Linux | `.AppImage` | Self-contained. `chmod +x` it and run |
| Android | `.apk` | Sideload; see below |

The exact file names come from the Tauri bundler and may differ slightly.

**Builds are not code-signed yet.**

- **Windows:** SmartScreen may show "Windows protected your PC". Choose **More info**, then **Run anyway**.
- **Android:** allow **Install unknown apps** for your browser or file manager when Android asks. CI builds a debug-signed APK; a newer build may refuse to install over an older one ("App not installed"). Uninstall the old one first, and note that uninstalling deletes files in the app's private folder.

**Desktop runtime requirement: Node.js 22 or later on `PATH`.** yt-dlp is started with `--js-runtimes node` and uses Node to solve YouTube's JavaScript challenges. Without it, some YouTube downloads fail. Windows also needs WebView2, which Windows 10 and 11 already include (the installer downloads it if missing).

## Build from source

### Prerequisites

All platforms:

- [Rust](https://rustup.rs) stable, 1.90 or newer (`tauri-plugin-http` 2.8 and `tauri-plugin-fs` 2.7 require it)
- [Bun](https://bun.sh) 1.4 or newer (CI uses 1.4.4)
- Tauri's [prerequisites](https://v2.tauri.app/start/prerequisites/) for your OS

<details>
<summary><b>Windows</b></summary>

- **Visual Studio Build Tools** with the "Desktop development with C++" workload (MSVC linker and Windows SDK).
- Rust with the MSVC toolchain (`stable-x86_64-pc-windows-msvc`), which is the rustup default on Windows.
- WebView2 (included in Windows 10 and 11).

</details>

<details>
<summary><b>Linux (Debian / Ubuntu)</b></summary>

The same packages CI installs:

```bash
sudo apt-get update
sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev patchelf xz-utils
```

The fetch script also needs `curl`, `tar` with xz, `sha256sum` and `python3`. Linux packages must be built on Linux.

</details>

<details>
<summary><b>Android</b></summary>

- **JDK 17** (Android Studio's bundled `jbr` works).
- **Android SDK** with Platform-Tools, Build-Tools, Command-line Tools and **NDK (Side by side)**. CI uses NDK `27.2.12479018` and installs `platforms;android-37` and `build-tools;37.0.0`, matching the Gradle project Tauri CLI 2.12 generates.
- Environment variables `JAVA_HOME`, `ANDROID_HOME` and `NDK_HOME`.
- The four Rust Android targets.

Windows (cmd), then open a new terminal:

```cmd
setx JAVA_HOME "C:\Program Files\Android\Android Studio\jbr"
setx ANDROID_HOME "%LOCALAPPDATA%\Android\Sdk"
dir /b "%LOCALAPPDATA%\Android\Sdk\ndk"
setx NDK_HOME "%LOCALAPPDATA%\Android\Sdk\ndk\<version printed above>"
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
```

Linux:

```bash
export JAVA_HOME=/opt/android-studio/jbr
export ANDROID_HOME="$HOME/Android/Sdk"
export NDK_HOME="$ANDROID_HOME/ndk/$(ls -1 "$ANDROID_HOME/ndk")"
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
```

You need about 10 GB of disk space for Android Studio, the SDK and the NDK.

</details>

### 1. Fetch the sidecar binaries (desktop only)

yt-dlp, ffmpeg and ffprobe are **not committed** (ffmpeg alone is over GitHub's 100 MB file limit). The fetch scripts download them into `src-tauri/binaries`, named for your Rust host triple, and check SHA-256 hashes against [`scripts/binaries.lock.json`](scripts/binaries.lock.json). CI runs the same scripts.

```bash
# Windows (writes *-x86_64-pc-windows-msvc.exe)
bun run binaries

# Linux (writes *-x86_64-unknown-linux-gnu)
bash scripts/fetch-binaries.sh
```

`bun run binaries` runs [`scripts/fetch-binaries.ps1`](scripts/fetch-binaries.ps1). Pass `-Triple <triple>` to that script directly if your host triple differs (check it with `rustc --print host-tuple`). Android needs no sidecars: [`tauri.android.conf.json`](src-tauri/tauri.android.conf.json) sets `"externalBin": []`.

| Binary | Source | Hash |
|---|---|---|
| yt-dlp 2026.08.19 | Official yt-dlp GitHub release | Pinned |
| ffmpeg, ffprobe | [BtbN FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds), `master-latest` **LGPL** build | Not pinned yet (the `latest` URL changes daily; the script prints the computed hash and continues) |

### 2. Install, check and run

```bash
bun install
bun run typecheck
bun run lint
bun run dev          # starts the app in development mode
```

Rust unit tests: `cd src-tauri && cargo test`.

`bun run dev:web` starts only the Vite front end in a browser. It is for UI work: the browser's CORS rules block real fetches, so links fail with a "browser preview" error.

### 3. Build installers

| Command | Output |
|---|---|
| `bun run build:windows` | `src-tauri/target/release/bundle/nsis/*.exe`, `bundle/msi/*.msi` |
| `bun run build:linux` | `src-tauri/target/release/bundle/{deb,rpm,appimage}/` |
| `bun run build:desktop` | All bundle targets for the current OS |

### 4. Build the Android APK

```bash
bun run android:init     # once; generates src-tauri/gen/android (git-ignored)
bun run build:android    # universal APK for all four ABIs
```

| Command | What it does |
|---|---|
| `bun run android:dev` | Run on a connected device or emulator with live reload |
| `bun run build:android` | Universal APK (`tauri android build --apk`) |
| `bun run build:android:split` | One APK per ABI |
| `bun run build:android:arm64` | 64-bit ARM only |

Output lands under `src-tauri/gen/android/app/build/outputs/apk/`. Add `--debug` (for example `bun run build:android --debug`) for a debug-signed APK that installs directly; install it over USB with `adb install -r <file.apk>`.

Release APKs must be signed before Android installs them. Follow [Tauri's Android signing guide](https://v2.tauri.app/distribute/sign/android/): create a keystore, write `src-tauri/gen/android/keystore.properties`, and add a `release` signing config to `src-tauri/gen/android/app/build.gradle.kts`. Because `gen/` is regenerated in CI, either commit it after the edits or script them in CI.

### Continuous integration

[`.github/workflows/build.yml`](.github/workflows/build.yml) runs on pushes to `main`, on pull requests, on `v*` tags and by hand.

| Job | Runner | Builds | Artifacts |
|---|---|---|---|
| `windows` | `windows-latest` (MSVC) | `bun run build:windows` | `keepsake-windows-nsis`, `keepsake-windows-msi` |
| `linux` | `ubuntu-22.04` | `bun run build:linux` | `keepsake-linux-deb`, `keepsake-linux-rpm`, `keepsake-linux-appimage` |
| `android` | `ubuntu-latest` (JDK 17, SDK, NDK) | `bun run android:init --ci`, then `bun run build:android --debug --ci` | `keepsake-android-apk` |
| `release` | `ubuntu-latest` | Runs on `v*` tags only, after the three builds | Draft GitHub Release with every installer |

You can build the APK entirely in GitHub Actions without installing the Android toolchain: push, open the **Actions** tab, and download `keepsake-android-apk` from the run's **Artifacts**.

The workflow assumes this folder is the repository root. If it is a subfolder, move `.github` to the repository root and set `KEEPSAKE_DIR` at the top of `build.yml`.

## Releasing

1. Bump the version in [`src-tauri/tauri.conf.json`](src-tauri/tauri.conf.json) (and keep [`package.json`](package.json) and [`src-tauri/Cargo.toml`](src-tauri/Cargo.toml) in step). The current version is **2.1.0**.
2. Tag the commit with the same version and push the tag:

   ```bash
   git tag v2.1.0
   git push origin v2.1.0
   ```

3. CI builds every platform, then the `release` job collects all installers into a **draft** GitHub Release with generated release notes.
4. Review the draft on GitHub and publish it.

## Settings

Settings save automatically; there is no Save button. **Reset** restores the defaults.

| Setting | Default | Notes |
|---|---|---|
| Save folder | System Downloads folder | On Android, files go to the app's private files folder |
| Parallel downloads | 3 | 1 to 10 |
| Cookies from browser | Off | Firefox, Chrome, Edge, Brave, Opera, Vivaldi or Chromium. Desktop only. Firefox works best on Windows; close Chromium-based browsers before fetching |
| Embed thumbnail as cover art | On | Video, MP3 and M4A |
| Prefer H.264 | Off | Best compatibility. YouTube offers H.264 up to 1080p only |
| Detect links in clipboard | Off | Offers a copied link on Home |
| Theme | System | System, Light or Dark |

## Keyboard shortcuts

On Windows and Linux, `Ctrl` is the modifier.

| Shortcut | Action |
|---|---|
| `Ctrl` + `1` / `2` / `3` / `4` | Go to Home / Downloads / Library / Settings |
| `Ctrl` + `L` | Focus the link field on Home |
| `Ctrl` + `V` | On Home (outside a text field): paste the clipboard link and fetch it |
| `Ctrl` + `Enter` | On Home: start the download |
| `Ctrl` + `F` | Focus the Library search |
| `Ctrl` + `B` | Collapse or expand the sidebar (desktop) |
| `Ctrl` + `Shift` + `L` | Switch between dark and light theme |

## Architecture

```text
+-----------------------------------------------------------------+
|  UI: React 19 + Tailwind CSS 4 + motion   (src/pages, components)|
|  State: settings, downloads queue, library (src/state)          |
+--------------------------------+--------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------+
|  Engine (TypeScript, src/engine)                                |
|  fetchInfo / listFormats / startDownload / binaryStatus         |
+----------------+-------------------------------+----------------+
                 |  Windows / Linux              |  Android
                 v                               v
+-------------------------------+   +-----------------------------+
| Tauri command run_ytdlp (Rust)|   | youtubei.js (YouTube only)  |
|   -> yt-dlp sidecar           |   |   via plugin-http           |
|   -> ffmpeg / ffprobe sidecar |   | ffmpeg.wasm for conversion  |
| YouTube info: youtubei.js,    |   | files written via plugin-fs |
|   falling back to yt-dlp -J   |   |                             |
+-------------------------------+   +-----------------------------+

Rust (src-tauri) is a thin Tauri shell: plugins (dialog, fs, http,
opener), window, and the validated yt-dlp launcher on desktop.
```

The engine API and the yt-dlp argument contract are documented in [`src/engine/CONTRACT.md`](src/engine/CONTRACT.md).

## Project structure

```text
.
├── .github/workflows/build.yml   CI: Windows, Linux, Android builds and draft releases
├── scripts/                      Sidecar fetch scripts and binaries.lock.json
├── public/                       Static assets
├── src/
│   ├── App.tsx                   App shell, splash, shortcuts
│   ├── pages/                    Home, Downloads, Library, Settings
│   ├── components/
│   │   ├── layout/               Sidebar, tab bar, titlebar, splash
│   │   ├── features/             Format picker, preview card, download rows, library list
│   │   └── ui/                   Buttons, dialogs, fields, toasts and other primitives
│   ├── engine/                   Extraction, download and conversion logic
│   ├── state/                    Stores for settings, downloads, library, theme
│   ├── lib/types.ts              Shared engine types
│   └── styles/                   Theme CSS
└── src-tauri/
    ├── src/                      lib.rs, main.rs, ytdlp.rs (yt-dlp launcher)
    ├── capabilities/             desktop.json, mobile.json
    ├── binaries/                 Sidecars (downloaded, not committed)
    ├── icons/
    └── tauri*.conf.json          Base config plus Windows, Linux and Android overrides
```

## Security and privacy

- **No accounts, no telemetry.** Keepsake talks only to the sites you download from (and jsDelivr once, on Android, to load ffmpeg.wasm).
- **No shell access from the webview.** The shell plugin is not used; the capabilities grant no `shell:*` permission. yt-dlp runs only through the `run_ytdlp` Rust command.
- **Fixed, validated yt-dlp arguments.** Rust always prepends `--ignore-config --no-plugin-dirs --no-js-runtimes --js-runtimes node`, so no user or system yt-dlp config is loaded. Every option must be on an allow-list; options that run programs or load code (`--exec`, `--downloader`, `--postprocessor-args`, `--plugin-dirs`, `--config-location`, `--batch-file`, `--ffmpeg-location` and others) are rejected, and the URL must be a single `http(s)://` link after `--`.
- **Content Security Policy.** Scripts load only from the app itself (`'unsafe-eval'` and `'wasm-unsafe-eval'` are allowed because youtubei.js and ffmpeg.wasm need them), and images may load from `https:` for thumbnails. See [`tauri.conf.json`](src-tauri/tauri.conf.json).
- **Scoped network and file access.** The HTTP plugin may only reach YouTube, Google video and image hosts, and the pinned ffmpeg.wasm core on jsDelivr. File access is limited to the Downloads, Video, Audio, app data and app cache folders, plus a folder you pick. Opening files from the app is limited to the download folders.
- **Cookies stay with you.** Cookies are read only from the browser you choose in Settings, and only when you turn that on. They are passed to yt-dlp for the request and not stored by Keepsake.

## Troubleshooting

<details>
<summary><b>"yt-dlp is missing or damaged"</b></summary>

The sidecar was not bundled or was removed. Reinstall Keepsake. When building from source, run the fetch script (step 1 of [Build from source](#build-from-source)) before `bun run dev`.

</details>

<details>
<summary><b>"ffmpeg is missing"</b></summary>

Merging high-resolution video and audio conversion need ffmpeg. Reinstall Keepsake, or re-run the fetch script when building from source. Settings > Components shows the detected yt-dlp and ffmpeg versions.

</details>

<details>
<summary><b>YouTube downloads fail on desktop</b></summary>

Make sure Node.js 22 or later is installed and on `PATH`; yt-dlp uses it to solve YouTube's JavaScript challenges.

</details>

<details>
<summary><b>Age-restricted, private or members-only videos</b></summary>

Choose your browser under **Settings > Cookies from browser** (desktop only). Sign in to the site in that browser first. Firefox works best on Windows; close Chromium-based browsers before fetching, because they lock their cookie database.

</details>

<details>
<summary><b>Android: where are my files?</b></summary>

Files are saved to the app's private folder, `/storage/emulated/0/Android/data/com.keepsake.app/files/Download`. Many file managers hide `Android/data`; open files from Keepsake's Library instead. **Android deletes this folder when you uninstall Keepsake**, so copy anything you want to keep first.

</details>

<details>
<summary><b>Android: "Only YouTube links can be downloaded on this device" or playlist errors</b></summary>

Expected. Other sites and playlists need the Windows or Linux app.

</details>

<details>
<summary><b>Android: "Can't save to ..."</b></summary>

Folder access from the picker lasts for one session. Pick the folder again in Settings, or clear it to use the default.

</details>

<details>
<summary><b>Android: the first MP3 conversion is slow</b></summary>

On first use the app downloads ffmpeg.wasm (about 30 MB) from jsDelivr, then converts on the phone's CPU.

</details>

<details>
<summary><b>Windows dev build: "resource path binaries\yt-dlp-x86_64-pc-windows-gnu.exe doesn't exist"</b></summary>

Your Rust default toolchain is the GNU one, so Tauri looks for `-gnu` sidecar names. Either switch to MSVC (`rustup default stable-x86_64-pc-windows-msvc`), or fetch the binaries under the GNU names:

```cmd
powershell -ExecutionPolicy Bypass -File scripts\fetch-binaries.ps1 -Triple x86_64-pc-windows-gnu
```

</details>

<details>
<summary><b>Linux: <code>.deb</code> / <code>.rpm</code> conflicts with a system yt-dlp</b></summary>

These packages install the sidecars next to the app in `/usr/bin`, which can clash with a distribution `yt-dlp` package. Use the self-contained AppImage instead.

</details>

## Roadmap

- [ ] Android: download higher resolutions by merging separate video and audio streams
- [ ] Android: save to the public Downloads folder (MediaStore)
- [ ] System tray
- [ ] Code signing for Windows installers and release-signed Android APKs
- [ ] Pin the ffmpeg download hash to a dated BtbN build

## Credits

Keepsake is built on these projects:

- [Tauri](https://tauri.app): the app shell and plugins
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): extraction and downloads on desktop (Unlicense)
- [FFmpeg](https://ffmpeg.org): merging and conversion on desktop. The bundled builds are the **LGPL** variants from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds)
- [youtubei.js](https://github.com/LuanRT/YouTube.js): YouTube info and Android downloads
- [ffmpeg.wasm](https://github.com/ffmpegwasm/ffmpeg.wasm): in-app audio conversion on Android
- [React](https://react.dev), [motion](https://motion.dev), [Tailwind CSS](https://tailwindcss.com), [Vite](https://vite.dev) and [Bun](https://bun.sh)

## Legal

Keepsake is a tool. It does not host, store or distribute any media. Only download content you have the right to download, such as your own uploads, content in the public domain or under a permissive license, or content the owner allows you to save. Respect each site's terms of service and copyright law in your country. The authors are not responsible for how the software is used.

## Contributing

Issues and pull requests are welcome.

1. Fork the repository and create a branch.
2. Run `bun install`, then make your change.
3. Before opening a pull request, run `bun run typecheck`, `bun run lint` and `cd src-tauri && cargo test`.
4. Keep download logic in `src/engine` and keep the Rust side thin.

## License

No license has been chosen yet. Until one is added, all rights are reserved by the authors.
