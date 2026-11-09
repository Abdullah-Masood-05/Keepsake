/**
 * The only UI module that imports the engine (src/engine/index.ts).
 * Everything else talks to the engine through this file or the stores.
 */
import * as engine from "../engine";
import type { AppError, BinaryStatus, Platform } from "../lib/types";
import { createStore, useStore } from "./store";

export const fetchInfo = engine.fetchInfo;
export const listFormats = engine.listFormats;
export const startDownload = engine.startDownload;

let cachedPlatform: Platform | null = null;
export function getPlatform(): Platform {
  if (!cachedPlatform) {
    try {
      cachedPlatform = engine.platform();
    } catch {
      cachedPlatform = "web";
    }
  }
  return cachedPlatform;
}

/** Normalise anything thrown by the engine into a plain AppError for display (engine's shared toAppError). */
export function asAppError(e: unknown): AppError {
  try {
    return engine.toAppError(e);
  } catch {
    // toAppError can only throw on JSON.stringify of odd values; still route through the friendly-error table.
    return engine.friendlyError(String(e));
  }
}

// ---- Binary status (Splash, sidebar dot, Settings > Tools) ----

export type BinaryLoad =
  | { state: "loading" }
  | { state: "ready"; status: BinaryStatus }
  | { state: "error"; error: AppError };

export const binaryStore = createStore<BinaryLoad>({ state: "loading" });

export async function refreshBinaries(): Promise<BinaryLoad> {
  binaryStore.set({ state: "loading" });
  try {
    const status = await engine.binaryStatus();
    const next: BinaryLoad = { state: "ready", status };
    binaryStore.set(next);
    return next;
  } catch (e) {
    const next: BinaryLoad = { state: "error", error: asAppError(e) };
    binaryStore.set(next);
    return next;
  }
}

export function useBinaries(): BinaryLoad {
  return useStore(binaryStore, (s) => s);
}

export type Health = "ready" | "ffmpeg" | "ytdlp" | "unsupported" | "loading";

/** Sidebar dot: green Ready, amber ffmpeg missing, red yt-dlp missing. */
export function healthOf(b: BinaryLoad): Health {
  if (b.state === "loading") return "loading";
  if (b.state === "error") return "ytdlp";
  const s = b.status;
  if (s.ytdlp === "unsupported" && s.ffmpeg === "unsupported") return "unsupported";
  if (s.ytdlp === "missing") return "ytdlp";
  if (s.ffmpeg === "missing") return "ffmpeg";
  return "ready";
}

export function versionsLine(s: BinaryStatus): string {
  const parts: string[] = [];
  if (s.ytdlpVersion) parts.push(`yt-dlp ${s.ytdlpVersion}`);
  if (s.ffmpegVersion) parts.push(`ffmpeg ${s.ffmpegVersion}`);
  if (s.nodeVersion) parts.push(`Node.js ${s.nodeVersion}`);
  else if (s.node === "missing") parts.push("Node.js missing (YouTube needs it)");
  if (parts.length === 0) {
    return s.ytdlp === "unsupported" ? "Built-in engine" : "Versions unavailable";
  }
  return parts.join(" · ");
}
