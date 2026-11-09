# Engine contract

## 1. TypeScript API (`src/engine/index.ts`)

| Export | Signature | Notes |
|---|---|---|
| `fetchInfo` | `(url: string, opts?: { signal?: AbortSignal; cookiesBrowser?: string }) => Promise<VideoInfo>` | Rejects with `EngineError` (an `Error` that is also an `AppError`). |
| `listFormats` | `(info: VideoInfo \| null \| undefined) => FormatOption[]` | `null` gives disabled "Fetch a video first" video rows plus audio/thumbnail rows. Respect `disabledReason` and `isDefault`. |
| `startDownload` | `(req: DownloadRequest, onProgress: (p: DownloadProgress) => void) => DownloadHandle` | Starts at once; the caller owns queueing and the 1-10 parallel limit. `handle.done` never rejects. Final `onProgress` call has status `done`, `failed` or `cancelled`. |
| `binaryStatus` | `() => Promise<BinaryStatus>` | Desktop: from `binary_status`. Android/web: `"unsupported"`. |
| `platform` | `() => "windows" \| "linux" \| "android" \| "web"` | |
| `toAppError`, `friendlyError`, `qualityLabel` | helpers | |

`DownloadRequest.formatId` is a `FormatOption.id`: `video:best`, `video:<height>`, `audio:<mp3|m4a|opus|wav|flac>`, `thumb:<original|png|jpg>`.

Per platform:
- Windows/Linux: YouTube info via youtubei.js, falling back to yt-dlp `-J`; other sites via yt-dlp. All downloads via yt-dlp.
- Android: YouTube only. Single-file formats only (progressive MP4 with audio, or audio-only). MP3/WAV/FLAC/OPUS conversion via ffmpeg.wasm (core loaded from jsDelivr on first use). No merging. Playlists rejected.
- Web (`vite` dev without Tauri): window.fetch is CORS-blocked by YouTube, so fetches fail with code `web_cors`. Dev/UI preview only.

## 2. Tauri commands the PLATFORM agent must provide (Rust)

### `run_ytdlp`
```ts
invoke<number>("run_ytdlp", { jobId: string, args: string[], tempDir: string | null, onEvent: Channel<YtdlpEvent> })
type YtdlpEvent = { event: "stdout"; line: string } | { event: "stderr"; line: string };
```
- Spawn the `yt-dlp` sidecar with `["--ffmpeg-location", <sidecar dir>, ...args]`. Rust prepends `--ffmpeg-location`; TS never sends it.
- Env `PYTHONIOENCODING=utf-8`. Windows: `CREATE_NO_WINDOW` + Job Object (kill on close). Unix: `process_group(0)`.
- Send every stdout/stderr line (no trailing newline, UTF-8, lossy decode) on `onEvent` as it arrives.
- Resolve with the exit code when the process exits (after both pipes are drained). Reject only if spawning fails; include "yt-dlp" and "not found" in the message when the binary is missing.
- Validation Rust should do (the webview builds the args): the last two args are `--` and an `http(s)://` URL; reject `--exec`, `--exec-before-download`, `--config-location(s)`, `--batch-file`/`-a`, `--load-info-json`, `--netrc-cmd`, `--external-downloader`/`--downloader`, `--downloader-args`, `--postprocessor-args`/`--ppa`, `--plugin-dirs`, `--use-postprocessor`.
- `tempDir` (download jobs only) is `<outDir>/.keepsake-tmp/<jobId>`: create it with a `.keepsake-job` marker before spawning, and delete it after exit (success, failure or cancel). Never touch anything else in `outDir`.
- `jobId` is a UUID (downloads) or `info-<UUID>` (fetchInfo).

### `cancel_ytdlp`
```ts
invoke<void>("cancel_ytdlp", { jobId: string })
```
Kill the process tree for `jobId` (Unix: SIGTERM group, SIGKILL after 2 s), wait for exit, then clean `tempDir`. No-op if unknown. The pending `run_ytdlp` call then resolves with the exit code; TS reports `cancelled`.

### `binary_status`
```ts
invoke<{ ytdlp: string | null; ffmpeg: string | null; node: string | null }>("binary_status")
```
Version strings from `yt-dlp --version`, the first line of `ffmpeg -version` and `node --version` (the Node found by the lookup below), or `null` when missing or failing. `BinaryStatus` gains optional `node` ("ok" | "missing") and `nodeVersion`.

### `list_installed_browsers`
```ts
invoke<string[]>("list_installed_browsers")
```
yt-dlp browser names (`edge chrome firefox brave chromium opera vivaldi`) whose profile folder exists (Windows: `%LOCALAPPDATA%` / `%APPDATA%`; Linux: `~/.config`, `~/.mozilla`, snap Firefox). Used by the cookie fallback.

### JS runtime and cookie fallback
- Rust looks for Node: PATH, then `%ProgramFiles%\nodejs`, `C:\Program Files\nodejs`, `%LOCALAPPDATA%\Programs\nodejs`, `%NVM_SYMLINK%` (Windows) or `/usr/local/bin`, `/usr/bin` (Linux), and prepends `--no-js-runtimes --js-runtimes node:<absolute path>`. No Node + YouTube URL: `run_ytdlp` rejects with `js_runtime_missing: ...` (TS code `js_runtime_missing`). No Node + other site: runs with no JS runtime.
- The validator accepts `--js-runtimes node` or `node:<absolute path>` only.
- Bot check (`bot_check`) with Settings > Cookies "off": TS retries once per installed browser in the order edge, chrome, firefox, brave, chromium, opera, vivaldi with `--cookies-from-browser <b>`, stops at the first success (download result `note: "Retried with cookies from <Browser>"`), else returns `bot_check` (cookiesHint true). An explicit browser choice is never overridden. Applies to downloads and to yt-dlp info fetches.

## 3. Arguments TS sends (for reference and Rust tests)

Every call: `--encoding utf-8 --no-warnings [--cookies-from-browser <b>]`. Rust prepends `--ignore-config --no-plugin-dirs --no-js-runtimes [--js-runtimes node:<path>] --ffmpeg-location <dir>`, so TS does not repeat them.

- Info: `... -J -i --flat-playlist -- <url>`. JSON is the first stdout line starting with `{`.
- Download (all modes): `--windows-filenames --trim-filenames <60..200> -P home:<outDir> -P temp:<tempDir> --newline --progress --progress-template "download:KEEPSAKE|status|downloaded|total|estimate|speed|eta|playlist_index|n_entries|filename" --progress-template "postprocess:KEEPSAKE_PP|status|postprocessor" --print "after_move:KEEPSAKE_DONE|%(filepath)s" -i`
  - Video: `-o "%(title)s.%(ext)s" -f "bestvideo[height<=N]+bestaudio/best[height<=N]/best" [-S res,fps,vcodec:h264,acodec:aac] --merge-output-format mp4/mkv [--embed-thumbnail --convert-thumbnails jpg] --embed-metadata`. Picked video-only stream: `-f "<id>+bestaudio[ext=m4a]/<id>+bestaudio"`.
  - Audio: `-o "%(title)s.%(ext)s" -f bestaudio/best -x --audio-format <fmt> [--audio-quality <kbps>K] [--embed-thumbnail --convert-thumbnails jpg (mp3/m4a only)] --embed-metadata`.
  - Thumbnail: `--skip-download --write-thumbnail -o "thumbnail:%(title)s_thumb.%(ext)s" [--convert-thumbnails png|jpg] --print "after_video:KEEPSAKE_DONE|%(thumbnails.-1.filepath)s"`.
- Last: `-- <url>`.

## 4. Config the PLATFORM agent must add

- `@tauri-apps/plugin-http` (npm 2.8.3 installed) + `tauri-plugin-http` crate; capability `http:default` with allow scope: `https://*.youtube.com/*`, `https://youtube.com/*`, `https://*.googlevideo.com/*`, `https://*.ytimg.com/*`, `https://*.ggpht.com/*`, `https://cdn.jsdelivr.net/*`, and for desktop thumbnails of other sites `https://*/*` (or desktop-only capability).
- `@tauri-apps/plugin-fs` (npm 2.7.1 installed) + `tauri-plugin-fs` crate, Android capability: `fs:allow-open`, `fs:allow-write`, `fs:allow-write-file`, `fs:allow-mkdir`, `fs:allow-exists`, `fs:allow-remove`, scope `$DOWNLOAD/**` (plus any user-picked folder).
- CSP `script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' blob:` (youtubei.js decipher uses `new Function`; ffmpeg.wasm), `worker-src 'self' blob:`, `connect-src 'self' ipc: http://ipc.localhost blob:`.
- `vite.config.ts`: `optimizeDeps: { exclude: ["@ffmpeg/ffmpeg"] }` and `worker: { format: "es" }` (ffmpeg.wasm spawns a module worker).
- Desktop yt-dlp needs Node.js for YouTube; Rust passes `--js-runtimes node:<path>` (see section 2).
