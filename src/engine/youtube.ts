/**
 * youtubei.js wrapper (v18.3.0, MIT). Used for YouTube on Android and web; desktop downloads go through yt-dlp.
 *
 * What the package says (read from node_modules/youtubei.js; its README only shows
 * `Innertube.create(/* options *\/)` and links to https://ytjs.dev, so the .d.ts files are the source):
 * - VERIFIED Innertube.d.ts: `static create(config?: InnerTubeConfig)`, `getBasicInfo(video_id, options?: GetVideoInfoOptions)`,
 *   `getPlaylist(id)`, `get session(): Session`. GetVideoInfoOptions has `client?: InnerTubeClient`
 *   ('IOS' | 'WEB' | 'MWEB' | 'ANDROID' | 'ANDROID_VR' | 'TV' | ...; types/Misc.d.ts).
 * - VERIFIED core/Session.d.ts InnerTubeConfig: `fetch?: FetchFunction` (typeof fetch), `retrieve_player?: boolean`
 *   ("Deciphering formats is not possible without the JS player"), `generate_session_locally?`. `session.player?: Player`.
 * - VERIFIED core/mixins/MediaInfo.d.ts: `basic_info` (title, author, duration, view_count, thumbnail[],
 *   short_description, is_live...), `streaming_data?: IStreamingData`, `playability_status?`.
 *   parser/types/ParsedResponse.d.ts: IStreamingData = { formats: Format[]; adaptive_formats: Format[]; ... }.
 *   `formats` are progressive (video+audio), `adaptive_formats` are video-only or audio-only.
 * - VERIFIED parser/classes/misc/Format.d.ts: itag, url?, signature_cipher?, cipher?, width?, height?, fps?,
 *   content_length?, bitrate, mime_type, has_audio, has_video, quality_label?, audio_track?, is_drc?,
 *   and `decipher(player?: Player): Promise<string>` ("If no player is provided, returns the original URL").
 * - VERIFIED decipher internals (core/Player.js `decipher`): builds a script from the player JS and calls
 *   `Platform.shim.eval(data, env)`; the default evaluator for the web build (platform/jsruntime/default.js)
 *   throws "To decipher URLs, you must provide your own JavaScript evaluator. See
 *   https://ytjs.dev/guide/getting-started.html#providing-a-custom-javascript-interpreter". The script in
 *   `data.output` ends with `return process(n, sp, s)` (utils/Utils.js getNsigProcessorFn) and returns
 *   `{ sig, n }`. So the evaluator is `new Function(data.output)()`. This needs CSP `script-src 'unsafe-eval'`.
 * - VERIFIED utils/Utils.js: `Platform.load(shim)` replaces the shim; `Platform.shim` is getter-only.
 * INFERRED: client order ANDROID_VR -> TV -> WEB (yt-dlp's no-PO-token choices in 2025/26); not run against YouTube here.
 */
import { Innertube, Platform } from "youtubei.js/web";
import type { Types } from "youtubei.js/web";
import type { StreamInfo, Thumbnail, VideoInfo } from "../lib/types";
import { fail, friendlyError, EngineError } from "./errors";
import { ytFetch } from "./http";

type YTInfo = Awaited<ReturnType<Innertube["getBasicInfo"]>>;
type YTFormat = NonNullable<YTInfo["streaming_data"]>["formats"][number];

const CLIENTS: Types.InnerTubeClient[] = ["ANDROID_VR", "TV", "WEB"];

let clientPromise: Promise<Innertube> | undefined;
let evalInstalled = false;

function installEvaluator() {
  if (evalInstalled) return;
  const shim = Platform.shim;
  Platform.load({
    ...shim,
    // data.output is a self-contained script ending in `return process(...)` (see header).
    // eslint-disable-next-line no-new-func
    eval: (data: Types.BuildScriptResult) => new Function(data.output)() as Record<string, unknown>,
  });
  evalInstalled = true;
}

/** Create the Innertube client once (with the player, so formats can be deciphered). */
export function getClient(): Promise<Innertube> {
  if (!clientPromise) {
    installEvaluator();
    clientPromise = Innertube.create({ fetch: ytFetch, retrieve_player: true }).catch((e: unknown) => {
      clientPromise = undefined; // allow retry after a network failure
      throw e;
    });
  }
  return clientPromise;
}

const YT_HOSTS = /(^|\.)((youtube|youtube-nocookie)\.com|youtu\.be)$/i;

export function isYouTubeUrl(url: string): boolean {
  try {
    return YT_HOSTS.test(new URL(url).hostname);
  } catch {
    return false;
  }
}

/** Extract { videoId, playlistId } from any YouTube URL form. */
export function parseYouTubeUrl(url: string): { videoId?: string; playlistId?: string } {
  const u = new URL(url);
  const playlistId = u.searchParams.get("list") ?? undefined;
  let videoId: string | undefined;
  if (/youtu\.be$/i.test(u.hostname)) videoId = u.pathname.split("/")[1];
  else if (u.searchParams.get("v")) videoId = u.searchParams.get("v") ?? undefined;
  else {
    const m = u.pathname.match(/^\/(?:shorts|live|embed|v)\/([\w-]{11})/);
    if (m) videoId = m[1];
  }
  if (videoId && !/^[\w-]{11}$/.test(videoId)) videoId = undefined;
  return { videoId, playlistId };
}

/** Raw youtubei.js info by video id, so a download can resolve streams without refetching. */
const rawCache = new Map<string, YTInfo>();

function codecs(mime: string): { container: string; codecs: string[] } {
  const [type, params = ""] = mime.split(";");
  const container = type.split("/")[1] ?? "bin";
  const m = params.match(/codecs="([^"]*)"/);
  return { container, codecs: m ? m[1].split(",").map((c) => c.trim()) : [] };
}

function toStream(f: YTFormat): StreamInfo {
  const { container, codecs: cs } = codecs(f.mime_type);
  const kind = f.has_video && f.has_audio ? "progressive" : f.has_video ? "video-only" : "audio-only";
  return {
    id: String(f.itag),
    kind,
    ext: kind === "audio-only" && container === "mp4" ? "m4a" : container,
    height: f.height,
    fps: f.fps,
    vcodec: f.has_video ? cs[0] : undefined,
    acodec: f.has_audio ? cs[cs.length - 1] : undefined,
    bitrate: f.bitrate,
    sizeBytes: f.content_length,
  };
}

/** Usable formats: skip DRM, OTF, dubbed/secondary audio tracks and DRC duplicates. */
function usableFormats(info: YTInfo): YTFormat[] {
  const sd = info.streaming_data;
  if (!sd) return [];
  return [...sd.formats, ...sd.adaptive_formats].filter(
    (f) =>
      !f.drm_families?.length &&
      !f.is_type_otf &&
      !f.is_drc &&
      (!f.audio_track || f.audio_track.audio_is_default) &&
      (f.url || f.signature_cipher || f.cipher),
  );
}

async function getBasicInfoAnyClient(yt: Innertube, videoId: string): Promise<YTInfo> {
  let lastReason = "";
  for (const client of CLIENTS) {
    try {
      const info = await yt.getBasicInfo(videoId, { client });
      const status = info.playability_status?.status;
      if (status === "OK" && usableFormats(info).length > 0) return info;
      lastReason = info.playability_status?.reason ?? `Playability status ${status ?? "unknown"}`;
    } catch (e) {
      lastReason = e instanceof Error ? e.message : String(e);
    }
  }
  throw new EngineError(friendlyError(lastReason || "No formats found"));
}

function thumbs(list: { url: string; width?: number; height?: number }[] | undefined): Thumbnail[] {
  return [...(list ?? [])]
    .sort((a, b) => (b.width ?? 0) * (b.height ?? 0) - (a.width ?? 0) * (a.height ?? 0))
    .map((t) => ({ url: t.url, width: t.width, height: t.height }));
}

export async function fetchYouTubeInfo(url: string): Promise<VideoInfo> {
  const { videoId, playlistId } = parseYouTubeUrl(url);
  const yt = await getClient();

  if (!videoId && playlistId) {
    const pl = await yt.getPlaylist(playlistId);
    const first = pl.info.thumbnails?.[0];
    return {
      id: playlistId,
      url,
      site: "youtube",
      kind: "playlist",
      title: pl.info.title ?? "Playlist",
      channel: pl.info.author?.name,
      thumbnails: first ? [{ url: first.url, width: first.width, height: first.height }] : [],
      hasVideo: true,
      heights: [],
      fpsByHeight: {},
      streams: [],
      previewOnly: false,
      playlistCount: Number.parseInt(String(pl.info.total_items).replace(/\D/g, ""), 10) || undefined,
      source: "youtubei",
    };
  }
  if (!videoId) fail("unsupported_url", url);

  const info = await getBasicInfoAnyClient(yt, videoId);
  rawCache.set(videoId, info);
  const b = info.basic_info;
  const streams = usableFormats(info).map(toStream);
  const fpsByHeight: Record<number, number> = {};
  for (const s of streams) {
    if (s.height) fpsByHeight[s.height] = Math.max(fpsByHeight[s.height] ?? 0, s.fps ?? 0);
  }
  const heights = Object.keys(fpsByHeight)
    .map(Number)
    .sort((a, b2) => b2 - a);
  const hasVideo = streams.some((s) => s.kind !== "audio-only");
  return {
    id: videoId,
    url: `https://www.youtube.com/watch?v=${videoId}`,
    site: "youtube",
    kind: hasVideo ? "video" : "audio",
    title: b.title ?? "Untitled",
    channel: b.author ?? b.channel?.name ?? undefined,
    durationSec: b.duration,
    viewCount: b.view_count,
    uploadDate: (b.publish_date ?? b.upload_date ?? undefined)?.slice(0, 10),
    description: b.short_description?.split("\n").find((l) => l.trim()),
    thumbnails: thumbs(b.thumbnail),
    hasVideo,
    heights,
    fpsByHeight,
    streams,
    previewOnly: false,
    source: "youtubei",
  };
}

export interface ResolvedStream {
  url: string;
  sizeBytes?: number;
  ext: string;
  stream: StreamInfo;
}

async function rawInfo(videoId: string): Promise<YTInfo> {
  const hit = rawCache.get(videoId);
  // googlevideo URLs expire (streaming_data.expires); refetch when close to expiry.
  const exp = hit?.streaming_data?.expires;
  if (hit && exp && exp.getTime() - Date.now() > 5 * 60_000) return hit;
  const yt = await getClient();
  const info = await getBasicInfoAnyClient(yt, videoId);
  rawCache.set(videoId, info);
  return info;
}

/**
 * Pick a single-file stream (progressive with audio, or audio-only) and return a playable, deciphered URL.
 * - kind "progressive": best progressive at or below `maxHeight` (MP4 preferred).
 * - kind "audio": `container` "m4a" (AAC, itag 140 family) or "webm" (Opus), highest bitrate.
 */
export async function resolveSingleFile(
  videoId: string,
  want: { kind: "progressive"; maxHeight?: number } | { kind: "audio"; container: "m4a" | "webm" | "any" },
): Promise<ResolvedStream> {
  const info = await rawInfo(videoId);
  const formats = usableFormats(info);
  let pick: YTFormat | undefined;
  if (want.kind === "progressive") {
    const prog = formats
      .filter((f) => f.has_video && f.has_audio && (!want.maxHeight || (f.height ?? 0) <= want.maxHeight))
      .sort(
        (a, b) =>
          (b.height ?? 0) - (a.height ?? 0) ||
          Number(b.mime_type.startsWith("video/mp4")) - Number(a.mime_type.startsWith("video/mp4")) ||
          b.bitrate - a.bitrate,
      );
    pick = prog[0];
  } else {
    const audio = formats
      .filter((f) => f.has_audio && !f.has_video)
      .filter((f) => {
        if (want.container === "any") return true;
        const c = codecs(f.mime_type).container;
        return want.container === "m4a" ? c === "mp4" : c === "webm";
      })
      .sort((a, b) => b.bitrate - a.bitrate);
    pick = audio[0];
  }
  if (!pick) fail("format_unavailable");
  const yt = await getClient();
  const url = await pick.decipher(yt.session.player);
  if (!url) fail("no_formats", "Empty stream URL after decipher");
  const stream = toStream(pick);
  return { url, sizeBytes: pick.content_length, ext: stream.ext, stream };
}
