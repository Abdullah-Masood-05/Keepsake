/**
 * FormatPicker options (UI_CONTENT.md section 2).
 * Desktop: every height the link offers (yt-dlp merges). Android/web: only single-file formats are enabled
 * (progressive MP4 with audio, or audio-only); taller heights are listed with `disabledReason`.
 */
import type { AudioFormat, FormatOption, Platform, ThumbnailFormat, VideoInfo } from "../lib/types";
import { platform } from "./platform";

/** Heights offered when the link gives none (playlists): 2160 down to 360 per spec. */
const PLAYLIST_HEIGHTS = [2160, 1440, 1080, 720, 480, 360];
const STANDARD_HEIGHTS = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144];

function heightName(h: number): string {
  if (h >= 4320) return "8K";
  if (h >= 2160) return "4K";
  if (h >= 1440) return "QHD";
  if (h >= 1080) return "Full HD";
  if (h >= 720) return "HD";
  return "";
}

export function qualityLabel(h: number, fps?: number): string {
  const f = fps && fps > 30 ? String(Math.round(fps)) : "";
  const name = heightName(h);
  return `${h}p${f}${name ? ` ${name}` : ""}`;
}

const AUDIO: { f: AudioFormat; label: string }[] = [
  { f: "mp3", label: "MP3" },
  { f: "m4a", label: "M4A" },
  { f: "opus", label: "OPUS" },
  { f: "wav", label: "WAV" },
  { f: "flac", label: "FLAC" },
];

const THUMBS: { f: ThumbnailFormat; label: string; ext: string }[] = [
  { f: "original", label: "Original (WebP/JPG)", ext: "webp" },
  { f: "png", label: "PNG", ext: "png" },
  { f: "jpg", label: "JPG", ext: "jpg" },
];

function videoOptions(info: VideoInfo | null | undefined, p: Platform): FormatOption[] {
  const desktop = p === "windows" || p === "linux";
  if (!info) {
    return PLAYLIST_HEIGHTS.map((h) => ({
      id: `video:${h}`,
      mode: "video" as const,
      label: qualityLabel(h),
      height: h,
      ext: "mp4",
      isDefault: false,
      needsMerge: desktop,
      needsConversion: false,
      disabledReason: "Fetch a video first",
    }));
  }
  if (!info.hasVideo) return [];

  let heights = info.heights.length ? info.heights : info.kind === "playlist" ? PLAYLIST_HEIGHTS : [];
  // Keep standard steps plus any odd heights the link really has (e.g. 1920 portrait shorts stay as-is).
  heights = [...new Set(heights)].sort((a, b) => b - a);
  const progressive = new Set(info.streams.filter((s) => s.kind === "progressive" && s.height).map((s) => s.height!));

  const opts: FormatOption[] = heights
    .filter((h) => desktop || STANDARD_HEIGHTS.includes(h) || progressive.has(h))
    .map((h) => {
      const single = progressive.has(h);
      const usable = desktop || single;
      return {
        id: `video:${h}`,
        mode: "video" as const,
        label: qualityLabel(h, info.fpsByHeight[h]),
        height: h,
        fps: info.fpsByHeight[h] || undefined,
        ext: "mp4",
        isDefault: false,
        needsMerge: desktop && !single,
        needsConversion: false,
        disabledReason: usable
          ? undefined
          : p === "web"
            ? "Not available in the browser preview"
            : "Needs merging, which only the desktop app can do",
      };
    });

  const enabled = opts.filter((o) => !o.disabledReason);
  const best: FormatOption = {
    id: "video:best",
    mode: "video",
    label: "Best available",
    ext: "mp4",
    isDefault: false,
    needsMerge: desktop,
    needsConversion: false,
    disabledReason: enabled.length || desktop ? undefined : "No single-file video for this link",
  };
  // Default: highest <= 1080 among usable options, else Best available.
  const def = enabled.find((o) => (o.height ?? 0) <= 1080);
  if (def) def.isDefault = true;
  else best.isDefault = true;
  return [best, ...opts];
}

function audioOptions(): FormatOption[] {
  return AUDIO.map(({ f, label }) => ({
    id: `audio:${f}`,
    mode: "audio" as const,
    label,
    audioFormat: f,
    ext: f,
    isDefault: f === "mp3",
    needsMerge: false,
    // M4A is the native AAC stream. Others: yt-dlp + ffmpeg on desktop, ffmpeg.wasm on Android/web.
    needsConversion: f !== "m4a",
  }));
}

function thumbOptions(): FormatOption[] {
  return THUMBS.map(({ f, label, ext }) => ({
    id: `thumb:${f}`,
    mode: "thumbnail" as const,
    label,
    thumbnailFormat: f,
    ext,
    isDefault: f === "original",
    needsMerge: false,
    needsConversion: f !== "original",
  }));
}

/** All picker options for a fetched link (or the pre-fetch placeholders when `info` is null). */
export function listFormats(info: VideoInfo | null | undefined): FormatOption[] {
  const p = platform();
  return [...videoOptions(info, p), ...audioOptions(), ...thumbOptions()];
}
