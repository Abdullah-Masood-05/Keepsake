# Nuitka build notes

How the "stuck" build was fixed, and what to watch for in future Nuitka builds.

## The problem

`build.bat` compiled `main.py` with `--onefile --lto=yes`. The build always appeared to freeze, and
the log stopped at:

```
Nuitka-Scons: Backend C linking with 1126 files (no progress information available for this stage).
```

The C compilation itself was fine. All 1124 `.c` files compiled in about 8 minutes.

## Root cause

- **yt-dlp is huge.** It has about 970 extractor modules (`yt_dlp.extractor.*`, one per website).
  By default Nuitka converts every followed module to C, so the build folder grew to **1.8 GB** of
  object files.
- **`--lto=yes` with MSVC** turns linking into whole-program optimisation (LTCG) across all of
  those objects. That is single-threaded, prints no progress, and on this many objects it runs
  for an extremely long time. It looks exactly like a hang. Memory was not the problem: 47 GB of
  RAM was still free.

## The fix

Two flags in `build.bat`:

| Flag | Effect |
|---|---|
| `--lto=no` | A normal link step. It now takes about 1 second. |
| `--noinclude-custom-mode=yt_dlp.extractor:bytecode` | Ships the extractors as Python bytecode instead of compiling them to C. Extractors are not speed-critical. |

Result: about 150 C files instead of about 1124, a 166 MB build folder instead of 1.8 GB, and a
build time of about 7 minutes cold or **about 2 minutes** with warm caches. The extractor test
inside the frozen exe still finds all 1751 extractors.

Other cleanups made at the same time:

- Added `--assume-yes-for-downloads`, so Nuitka never waits at an invisible prompt (for example to
  download a compiler or dependency tool).
- Removed `--enable-plugin=anti-bloat`, because that plugin is always on.
- Updated Nuitka from 4.2 to 4.2.2.

## General guide: avoiding Nuitka build problems

### 1. Know what you are compiling
- Run once with `--report=report.xml` and look at which modules were included. Large packages
  (yt-dlp, numpy, pandas, scipy, torch, transformers, matplotlib) are the usual reason a build is
  slow.
- Count the C files in `<name>.build\`. More than a few hundred means it is time to trim.

### 2. Do not compile what does not need to be fast
- `--noinclude-custom-mode=<package>:bytecode` keeps a package but ships it as bytecode.
  Use it for large pure-Python packages that are not performance-critical.
- `--nofollow-import-to=<package>` leaves a package out **completely**. Only use it for things
  that are never imported at runtime (tests, `setuptools`, `pip`, `unittest`, and so on).
  It is **not** a way to ship something as bytecode.
- Exclude test and dev packages:
  `--nofollow-import-to=unittest,test,pytest,_pytest,doctest,pdb,setuptools,pip,distutils`.

### 3. Be careful with LTO
- Leave `--lto` at its default, or set it to `no`, for large dependency trees. Whole-program
  optimisation over hundreds of MB of objects can take hours with no output.
- If you want LTO, try it only after the module count has been cut down, and compare the time
  and size against a build without it.

### 4. Make builds non-interactive and observable
- Always add `--assume-yes-for-downloads` in scripts and CI.
- Redirect output to a log file: `python -m nuitka ... > build.log 2>&1`.
- Use `--show-scons` when the C stage is slow.
- If the log goes quiet, check whether `cl.exe`/`link.exe` (or `gcc`/`ld`) is still using CPU
  in Task Manager. Busy means slow; idle means stuck or crashed.

### 5. Iterate fast, then package
- Debug with `--standalone`, which produces a folder, is quicker and makes errors easier to see.
  Switch to `--onefile` only when the standalone build works.
- Keep the caches (`%LOCALAPPDATA%\Nuitka\Nuitka\Cache`). Rebuilds go from minutes to seconds of
  C compilation.
- Use `--remove-output` only once things work; keeping `*.build` helps debugging.

### 6. Antivirus
- Warnings like `Failed to replace ... clcache ... Disable Anti-Virus` mean Windows Defender is
  scanning the build files. They slow builds down and can cause random failures. Consider
  excluding the project folder and the Nuitka cache folder from real-time scanning.
- Onefile exes are sometimes flagged as false positives. Code signing helps.

### 7. Runtime paths in onefile builds
- In onefile mode `__file__` points into a temporary extraction folder that is deleted on exit:
  - **Bundled data** (icons and similar): include it with `--include-data-files`/`--include-data-dir`
    and resolve it relative to `__file__`.
  - **Files next to the exe** (for example `ffmpeg.exe`): resolve them relative to
    `__compiled__.original_argv0` / `sys.argv[0]`.
  - **User data** (settings, history): put it in `%APPDATA%`, never next to the exe. Program Files
    is not writable.
- See `app_paths.py` for how this project does it.

### 8. Qt-specific
- Use the matching plugin: `--enable-plugin=pyqt6` or `--enable-plugin=pyside6`. The installed
  package must match; a stale `nuitka-crash-report.xml` here came from a PySide6 test on a
  machine with only PyQt6 installed.
- Never create `QPixmap` (or touch widgets) in a worker thread. Pass a `QImage` or raw bytes and
  convert on the GUI thread. This applies with or without Nuitka.
- `--include-qt-plugins=sensible,styles,platforms` is usually enough.

### 9. Smoke-test the exe
- Launch it and make sure it stays alive. In onefile mode this shows as two processes: the
  launcher and the app.
- Run one real operation (for example a yt-dlp `extract_info`) inside a frozen build. Missing
  modules or data files only show up at runtime.

## Current build command

See `build.bat`. The core of it is:

```bat
python -m nuitka --onefile --windows-console-mode=disable --lto=no ^
  --enable-plugin=pyqt6 ^
  --noinclude-custom-mode=yt_dlp.extractor:bytecode ^
  --nofollow-import-to=unittest,test,pytest,_pytest,doctest,pdb ^
  --nofollow-import-to=setuptools,pip,distutils,pkg_resources ^
  --include-qt-plugins=sensible,styles,platforms ^
  --windows-icon-from-ico=resources\icons\app.ico ^
  --assume-yes-for-downloads --output-dir=build_dist main.py
```

## Optional yt-dlp dependencies

`yt-dlp[default,curl-cffi]` (plus `secretstorage` on Linux) is a project dependency. A probe
compiled with the flags above (`--standalone`, no extra flags) finds brotli, certifi (with
`cacert.pem`), mutagen, Cryptodome, websockets, requests, urllib3 and curl_cffi (browser
impersonation works) automatically, because `yt_dlp.dependencies` is compiled normally.

The one exception is `yt_dlp_ejs` (YouTube JS challenge solver). It is only imported from inside
the extractors, which ship as bytecode, so Nuitka never sees the import. Hence
`--include-package=yt_dlp_ejs --include-package-data=yt_dlp_ejs` in every Nuitka build.
