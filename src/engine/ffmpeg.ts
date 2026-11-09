/**
 * ffmpeg.wasm for Android/web audio conversion (MP3/WAV/FLAC encode, Opus remux). Never used for merging.
 *
 * VERIFIED (node_modules/@ffmpeg/ffmpeg/dist/esm/classes.d.ts + types.d.ts, v0.12.15, MIT):
 *   `new FFmpeg()`, `load({ coreURL, wasmURL, classWorkerURL })`, `writeFile(path, data)`, `exec(args)`,
 *   `readFile(path)`, `deleteFile`, `terminate()`, `on("progress", ({ progress }) => ...)`.
 * VERIFIED (npm view @ffmpeg/core): 0.12.10 published 2025-01-07, licence GPL-2.0-or-later, unpacked 64.7 MB
 *   (ffmpeg-core.wasm is about 31 MB of that). Single-threaded core: no SharedArrayBuffer needed.
 * Decision: the core is NOT bundled (GPL + size). It is fetched on first use from jsDelivr through httpFetch
 *   (plugin-http in Tauri, so no CORS), turned into blob: URLs and kept for the session.
 *   Needs CSP: script-src blob: 'wasm-unsafe-eval'; worker-src 'self' blob:. Needs plugin-http scope https://cdn.jsdelivr.net/*.
 * INFERRED: Android WebView memory is enough for converting a typical song (whole file held in memory).
 */
import { FFmpeg } from "@ffmpeg/ffmpeg";
import type { AudioFormat } from "../lib/types";
import { httpFetch } from "./http";

const CORE_BASE = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/esm";

let loading: Promise<FFmpeg> | undefined;

async function blobUrl(url: string, type: string): Promise<string> {
  const res = await httpFetch(url, { timeoutMs: 120_000 });
  if (!res.ok) throw new Error(`HTTP error ${res.status} loading ffmpeg core`);
  return URL.createObjectURL(new Blob([await res.arrayBuffer()], { type }));
}

function getFFmpeg(): Promise<FFmpeg> {
  if (!loading) {
    loading = (async () => {
      const ff = new FFmpeg();
      const [coreURL, wasmURL] = await Promise.all([
        blobUrl(`${CORE_BASE}/ffmpeg-core.js`, "text/javascript"),
        blobUrl(`${CORE_BASE}/ffmpeg-core.wasm`, "application/wasm"),
      ]);
      await ff.load({ coreURL, wasmURL });
      return ff;
    })().catch((e: unknown) => {
      loading = undefined;
      throw e;
    });
  }
  return loading;
}

function audioArgs(format: AudioFormat, bitrate: number): string[] {
  switch (format) {
    case "mp3":
      return ["-vn", "-c:a", "libmp3lame", "-b:a", `${bitrate}k`];
    case "flac":
      return ["-vn", "-c:a", "flac"];
    case "wav":
      return ["-vn", "-c:a", "pcm_s16le"];
    case "opus":
      return ["-vn", "-c:a", "copy"]; // WebM/Opus -> Ogg/Opus remux
    case "m4a":
      return ["-vn", "-c:a", "copy"];
  }
}

/** Convert an audio buffer. `onProgress` gets 0..1. Abort terminates the worker (reloaded on next use). */
export async function convertAudio(
  input: Uint8Array,
  inExt: string,
  format: AudioFormat,
  bitrate: number,
  onProgress?: (ratio: number) => void,
  signal?: AbortSignal,
): Promise<Uint8Array> {
  const ff = await getFFmpeg();
  const inName = `in.${inExt}`;
  const outName = `out.${format}`;
  const onProg = ({ progress }: { progress: number }) => onProgress?.(Math.max(0, Math.min(1, progress)));
  const onAbort = () => {
    ff.terminate();
    loading = undefined;
  };
  signal?.addEventListener("abort", onAbort, { once: true });
  ff.on("progress", onProg);
  try {
    await ff.writeFile(inName, input);
    const code = await ff.exec(["-i", inName, ...audioArgs(format, bitrate), outName]);
    if (code !== 0) throw new Error(`ffmpeg exited with code ${code}`);
    const out = await ff.readFile(outName);
    if (typeof out === "string") throw new Error("ffmpeg returned text instead of audio");
    return out;
  } finally {
    signal?.removeEventListener("abort", onAbort);
    if (!signal?.aborted) {
      ff.off("progress", onProg);
      await ff.deleteFile(inName).catch(() => undefined);
      await ff.deleteFile(outName).catch(() => undefined);
    }
  }
}
