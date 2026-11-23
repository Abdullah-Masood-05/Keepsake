/**
 * Android storage permission and shared-folder saving through the native keepsake-media plugin.
 *   storage_permission_status -> { granted, sdk, permanentlyDenied }
 *   request_storage_permission -> { granted, permanentlyDenied }   (resolves after the user answers)
 *   open_app_settings -> {}
 *   source_folder { uri } -> { relativePath, displayPath, writable }
 *   save_to_relative_path { source, relativePath, displayName, mime? } -> { uri, displayPath }
 *     (source must be a staged file under cacheDir/gallery-<id>/; it is deleted after a successful save)
 * save_to_relative_path rejects with "storage:<code>: <message>"; code is one of STORAGE_ERROR_CODES.
 * Non-Android: permission calls report granted, source_folder reports nothing, saving throws StorageError("unsupported").
 * Needs the matching keepsake-media:allow-* entries in src-tauri/capabilities/mobile.json.
 */
import { invoke } from "@tauri-apps/api/core";
import { platform } from "./platform";

export const STORAGE_ERROR_CODES: readonly string[] = [
  "not_writable",
  "source_missing",
  "permission",
  "no_space",
  "bad_args",
  "unknown",
];

export interface StoragePermissionStatus {
  granted: boolean;
  sdk: number;
  permanentlyDenied: boolean;
}

export interface StoragePermissionResult {
  granted: boolean;
  permanentlyDenied: boolean;
}

export interface SourceFolder {
  /** MediaStore RELATIVE_PATH style with trailing slash, e.g. "DCIM/Camera/", or null when unknown. */
  relativePath: string | null;
  /** Friendly form without the trailing slash, e.g. "DCIM/Camera". */
  displayPath: string | null;
  /** True when Keepsake can save into relativePath without extra permission on this Android version. */
  writable: boolean;
}

export interface SaveToRelativePathArgs {
  source: string;
  relativePath: string;
  displayName: string;
  mime?: string;
}

export interface SaveToRelativePathResult {
  uri: string;
  displayPath: string;
}

/** Error from save_to_relative_path. `storageCode` is one of STORAGE_ERROR_CODES or "unsupported". */
export class StorageError extends Error {
  storageCode: string;
  constructor(storageCode: string, message: string) {
    super(message);
    this.name = "StorageError";
    this.storageCode = storageCode;
  }
}

function isAndroid(): boolean {
  try {
    return platform() === "android";
  } catch {
    return false;
  }
}

function rawText(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  try {
    return JSON.stringify(e);
  } catch {
    return String(e);
  }
}

function mapStorageError(e: unknown): StorageError {
  const text = rawText(e);
  const m = /^storage:([a-z_]+):\s*([\s\S]*)$/.exec(text);
  if (m) return new StorageError(STORAGE_ERROR_CODES.includes(m[1]) ? m[1] : "unknown", m[2] || "Couldn't save the file.");
  return new StorageError("unknown", text || "Couldn't save the file.");
}

/** Current storage permission state without prompting. Non-Android (or an old build): granted. */
export async function storagePermissionStatus(): Promise<StoragePermissionStatus> {
  if (!isAndroid()) return { granted: true, sdk: 0, permanentlyDenied: false };
  try {
    const r = await invoke<Partial<StoragePermissionStatus> | null>("plugin:keepsake-media|storage_permission_status");
    return {
      granted: r?.granted === true,
      sdk: typeof r?.sdk === "number" ? r.sdk : 0,
      permanentlyDenied: r?.permanentlyDenied === true,
    };
  } catch {
    return { granted: false, sdk: 0, permanentlyDenied: false };
  }
}

/** Shows the system permission prompt and resolves after the answer. Non-Android: granted. Never throws. */
export async function requestStoragePermission(): Promise<StoragePermissionResult> {
  if (!isAndroid()) return { granted: true, permanentlyDenied: false };
  try {
    const r = await invoke<Partial<StoragePermissionResult> | null>("plugin:keepsake-media|request_storage_permission");
    return { granted: r?.granted === true, permanentlyDenied: r?.permanentlyDenied === true };
  } catch {
    return { granted: false, permanentlyDenied: false };
  }
}

/** Opens Keepsake's page in the Android settings (for a permanently denied permission). No-op elsewhere. */
export async function openAppSettings(): Promise<void> {
  if (!isAndroid()) return;
  try {
    await invoke("plugin:keepsake-media|open_app_settings");
  } catch {
    /* nothing to do: the user can open Settings by hand */
  }
}

/** Folder an editor input came from. Never throws; unknown folders give { null, null, false }. */
export async function sourceFolder(uri: string): Promise<SourceFolder> {
  const none: SourceFolder = { relativePath: null, displayPath: null, writable: false };
  if (!isAndroid() || !uri) return none;
  try {
    const r = await invoke<Partial<SourceFolder> | null>("plugin:keepsake-media|source_folder", { uri });
    const relativePath = typeof r?.relativePath === "string" && r.relativePath !== "" ? r.relativePath : null;
    if (relativePath === null) return none;
    return {
      relativePath,
      displayPath: typeof r?.displayPath === "string" && r.displayPath !== "" ? r.displayPath : relativePath.replace(/\/+$/, ""),
      writable: r?.writable === true,
    };
  } catch {
    return none;
  }
}

/** Copies a staged file into a shared folder via MediaStore. Rejects with StorageError. */
export async function saveToRelativePath(args: SaveToRelativePathArgs): Promise<SaveToRelativePathResult> {
  if (!isAndroid()) throw new StorageError("unsupported", "Saving to a shared folder is only available on Android.");
  let res: unknown;
  try {
    res = await invoke<unknown>("plugin:keepsake-media|save_to_relative_path", {
      source: args.source,
      relativePath: args.relativePath,
      displayName: args.displayName,
      ...(args.mime ? { mime: args.mime } : {}),
    });
  } catch (e) {
    throw mapStorageError(e);
  }
  const r = res as { uri?: unknown; displayPath?: unknown } | null;
  if (!r || typeof r.uri !== "string" || r.uri === "") {
    throw new StorageError("unknown", "Couldn't save the file.");
  }
  return { uri: r.uri, displayPath: typeof r.displayPath === "string" ? r.displayPath : "" };
}
