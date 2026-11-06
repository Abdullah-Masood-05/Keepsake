# Third-party notices

Fetchly is licensed under the GNU General Public License v3.0 (see `LICENSE`).
It uses or ships the following components.

| Component | License | Source |
|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) / Qt 6 | GPL-3.0 (PyQt6), LGPL-3.0 (Qt) | https://pypi.org/project/PyQt6/ |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | https://github.com/yt-dlp/yt-dlp |
| [requests](https://github.com/psf/requests) | Apache-2.0 | https://github.com/psf/requests |
| [mutagen](https://github.com/quodlibet/mutagen) (yt-dlp optional dependency) | GPL-2.0-or-later | https://pypi.org/project/mutagen/ |
| [pycryptodomex](https://www.pycryptodome.org) | BSD-2-Clause / Public Domain | https://pypi.org/project/pycryptodomex/ |
| [brotli](https://github.com/google/brotli) | MIT | https://pypi.org/project/Brotli/ |
| [websockets](https://github.com/python-websockets/websockets) | BSD-3-Clause | https://pypi.org/project/websockets/ |
| [certifi](https://github.com/certifi/python-certifi) | MPL-2.0 | https://pypi.org/project/certifi/ |
| [curl_cffi](https://github.com/lexiforest/curl_cffi) (bundles curl-impersonate / libcurl) | MIT (libcurl: curl license) | https://pypi.org/project/curl-cffi/ |
| [cffi](https://cffi.readthedocs.io) / [pycparser](https://github.com/eliben/pycparser) (curl_cffi dependencies) | MIT / BSD-3-Clause | https://pypi.org/project/cffi/ |
| [yt-dlp-ejs](https://github.com/yt-dlp/ejs) (YouTube challenge solver scripts) | Unlicense | https://pypi.org/project/yt-dlp-ejs/ |
| [secretstorage](https://github.com/mitya57/secretstorage) (Linux builds only) | BSD-3-Clause | https://pypi.org/project/SecretStorage/ |
| [cryptography](https://github.com/pyca/cryptography), [jeepney](https://gitlab.com/takluyver/jeepney) (secretstorage dependencies, Linux only) | Apache-2.0 or BSD-3-Clause / MIT | https://pypi.org/project/cryptography/ |
| [FFmpeg](https://ffmpeg.org) 7.1.1 (minimal build, bundled on all platforms) | LGPL-2.1-or-later | https://github.com/FFmpeg/FFmpeg/tree/n7.1.1 |
| [LAME](https://lame.sourceforge.io) (linked into FFmpeg) | LGPL-2.0-or-later | https://lame.sourceforge.io |
| [libopus](https://opus-codec.org) (linked into FFmpeg) | BSD-3-Clause | https://github.com/xiph/opus |

## FFmpeg build

The bundled `ffmpeg` / `ffprobe` are built from the unmodified FFmpeg `n7.1.1` tag with the
LGPL configuration in `build.sh` of
[ffmpeg-ytdl-minimal-build](https://github.com/Abdullah-Masood-05/ffmpeg-ytdl-minimal-build).
Running that script reproduces the binaries, and the prebuilt binaries (with SHA-256 checksums)
are published on its [releases page](https://github.com/Abdullah-Masood-05/ffmpeg-ytdl-minimal-build/releases).
`--enable-gpl` and `--enable-nonfree` are not used.
