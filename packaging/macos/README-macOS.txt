Keepsake for macOS (Apple Silicon) - EXPERIMENTAL
=================================================================

Install
-------
Drag "Keepsake.app" onto the Applications folder.

First launch: the app is not signed or notarized
-------------------------------------------------
This build is not signed with an Apple Developer ID, so Gatekeeper will
refuse to open it with a double-click ("cannot be opened because the
developer cannot be verified" or "is damaged").

Option 1: In Finder, right-click (or Control-click) the app, choose Open,
          then click Open in the dialog. On macOS 15 and later, if there is
          no Open button, go to System Settings > Privacy & Security and
          click "Open Anyway".

Option 2: Remove the quarantine flag in Terminal:

    xattr -dr com.apple.quarantine "/Applications/Keepsake.app"

Notes
-----
- Requires a Mac with Apple Silicon (M1 or newer). Intel Macs are not supported
  by this build.
- FFmpeg and FFprobe (minimal LGPL build) are bundled inside the app.
- Settings are stored in ~/.config/Keepsake.
- License: GPL-3.0. Source: https://github.com/Abdullah-Masood-05/Keepsake
