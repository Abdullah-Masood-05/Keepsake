/** Pure settings model: types, defaults, sanitising and migration (no store, no storage). */
import { DOWNLOADS_SAVE } from "../engine/android-gallery";

export type ThemePref = "system" | "dark" | "light";
export type CookiesBrowser =
  | "off"
  | "firefox"
  | "chrome"
  | "edge"
  | "brave"
  | "opera"
  | "vivaldi"
  | "chromium";
export type PickerMode = "video" | "audio" | "thumbnail";
/** Android: where an edited file is saved. "source" = next to the original. */
export type EditSaveTarget = "source" | "downloads" | "gallery" | "folder";
const EDIT_TARGETS: readonly EditSaveTarget[] = ["source", "downloads", "gallery", "folder"];

/** Bump when a stored setting needs a one-time migration (see migrateSettings). */
export const SETTINGS_VERSION = 2;

export interface Settings {
  theme: ThemePref;
  parallelDownloads: number;
  /** Empty string means "system Downloads folder" (resolved by the engine). */
  saveDir: string;
  /** Android: persisted SAF tree URI (content://) chosen by the user. Empty = not set. */
  saveTreeUri: string;
  /** Android: display name of the chosen tree folder. */
  saveTreeName: string;
  cookiesBrowser: CookiesBrowser;
  /** Audio: embed cover art (MP3/M4A). Default on. */
  embedThumbnail: boolean;
  /** Video: embed thumbnail and metadata. Default off (each pass rewrites the whole file). */
  embedVideoMeta: boolean;
  preferH264: boolean;
  clipboardDetect: boolean;
  sidebarCollapsed: boolean;
  lastMode: PickerMode;
  /** Version of the stored settings; drives one-time migrations. */
  settingsVersion: number;
  /** Android: the storage-access prompt was shown once (whatever the answer). */
  storagePromptShown: boolean;
  /** Android: where edited files are saved. */
  editSaveTarget: EditSaveTarget;
  /** Android: SAF tree URI used when editSaveTarget is "folder". */
  editTreeUri: string;
  editTreeName: string;
}

export const DEFAULT_SETTINGS: Settings = {
  theme: "system",
  parallelDownloads: 3,
  saveDir: "",
  saveTreeUri: "",
  saveTreeName: "",
  cookiesBrowser: "off",
  embedThumbnail: true,
  embedVideoMeta: false,
  preferH264: false,
  clipboardDetect: false,
  sidebarCollapsed: false,
  lastMode: "video",
  settingsVersion: SETTINGS_VERSION,
  storagePromptShown: false,
  editSaveTarget: "source",
  editTreeUri: "",
  editTreeName: "",
};

export const COOKIE_BROWSERS: { value: CookiesBrowser; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "firefox", label: "Firefox" },
  { value: "chrome", label: "Chrome" },
  { value: "edge", label: "Edge" },
  { value: "brave", label: "Brave" },
  { value: "opera", label: "Opera" },
  { value: "vivaldi", label: "Vivaldi" },
  { value: "chromium", label: "Chromium" },
];

export function clampParallel(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_SETTINGS.parallelDownloads;
  return Math.min(10, Math.max(1, Math.round(n)));
}

/** Coerce anything loaded from storage into a valid Settings object. */
export function sanitizeSettings(raw: Partial<Settings> | null): Settings {
  const s = { ...DEFAULT_SETTINGS, ...raw };
  return {
    theme: ["system", "dark", "light"].includes(s.theme) ? s.theme : "system",
    parallelDownloads: clampParallel(Number(s.parallelDownloads)),
    // A content:// address (saved by an earlier build's folder picker) is not a folder: drop it so downloads use the app folder.
    saveDir: typeof s.saveDir === "string" && !/^content:/i.test(s.saveDir) ? s.saveDir : "",
    // Old stored settings lack these keys; the defaults spread above yields "" for them.
    saveTreeUri: typeof s.saveTreeUri === "string" ? s.saveTreeUri : "",
    saveTreeName: typeof s.saveTreeName === "string" ? s.saveTreeName : "",
    cookiesBrowser: COOKIE_BROWSERS.some((b) => b.value === s.cookiesBrowser)
      ? s.cookiesBrowser
      : "off",
    embedThumbnail: Boolean(s.embedThumbnail),
    embedVideoMeta: Boolean(s.embedVideoMeta),
    preferH264: Boolean(s.preferH264),
    clipboardDetect: Boolean(s.clipboardDetect),
    sidebarCollapsed: Boolean(s.sidebarCollapsed),
    lastMode: ["video", "audio", "thumbnail"].includes(s.lastMode) ? s.lastMode : "video",
    // A stored object without the field predates versioning (0). Defaults above would claim "current", so read raw.
    settingsVersion: Number.isFinite(Number(raw?.settingsVersion)) ? Number(raw?.settingsVersion) : 0,
    storagePromptShown: Boolean(s.storagePromptShown),
    editSaveTarget: EDIT_TARGETS.includes(s.editSaveTarget) ? s.editSaveTarget : "source",
    editTreeUri: typeof s.editTreeUri === "string" ? s.editTreeUri : "",
    editTreeName: typeof s.editTreeName === "string" ? s.editTreeName : "",
  };
}

/** True for an app-private location (empty = the old app folder, or a path inside /data or Android/data). */
function isAppPrivateDir(dir: string): boolean {
  return dir === "" || /(^|\/)(data\/(data|user)|Android\/data)(\/|$)/.test(dir);
}

/**
 * One-time upgrades of stored settings. `raw` is what was loaded (null on a fresh install).
 * Android: a fresh install saves downloads to Download/Keepsake; an existing install whose save target was the
 * app-private folder (the cause of files ending up in app data) is moved there once. Gallery, a chosen SAF
 * folder and public folders (Music, Movies, Downloads path) are left alone. Other platforms only get the version.
 */
export function migrateSettings(raw: Partial<Settings> | null, android: boolean): Settings {
  const s = sanitizeSettings(raw);
  if (s.settingsVersion >= SETTINGS_VERSION) return s;
  const out: Settings = { ...s, settingsVersion: SETTINGS_VERSION };
  if (android && !s.saveTreeUri && isAppPrivateDir(s.saveDir)) out.saveDir = DOWNLOADS_SAVE;
  return out;
}

