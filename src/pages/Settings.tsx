import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Badge, Dot } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, type Span } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/Dialog";
import { FieldRow, Select, Skeleton, Stepper } from "../components/ui/Fields";
import { Icon } from "../components/ui/Icon";
import { listItem } from "../components/ui/motion";
import { Collapsible } from "../components/ui/Collapsible";
import { RadioGroup } from "../components/ui/RadioGroup";
import { Switch } from "../components/ui/Switch";
import { getPlatform, healthOf, refreshBinaries, useBinaries, versionsLine } from "../state/engine";
import { collectDiagnostics } from "../engine/diagnostics";
import { androidYtdlpStatus, type YtdlpStatus } from "../engine/android-ytdlp";
import { pickAndroidFolder } from "../engine/android-folder";
import { DOWNLOADS_SAVE, GALLERY_SAVE } from "../engine/android-gallery";
import { openAppSettings, requestStoragePermission, storagePermissionStatus } from "../engine/android-storage";
import { useWidth } from "../state/hooks";
import { notify } from "../state/toast";
import { PAGE_BOTTOM } from "../components/layout/page";
import { copyText, openFile, pickFolder } from "../state/native";
import {
  clampParallel,
  COOKIE_BROWSERS,
  resetSettings,
  updateSettings,
  useSettings,
  type EditSaveTarget,
  type ThemePref,
} from "../state/settings";

const SPANS: Record<string, Span> = {
  downloads: { wide: [6, 4], narrow: [12, 4] },
  storage: { wide: [12, 3], narrow: [12, 4] },
  appearance: { wide: [6, 2], narrow: [12, 3] },
  tools: { wide: [6, 2], narrow: [12, 2] },
  reset: { wide: [12, 1], narrow: [12, 1] },
};

const copyDiagnostics = async () => {
  await copyText(await collectDiagnostics());
  notify({ tone: "success", title: "Diagnostics copied", body: "Paste them into your bug report." });
};

/** Pick an Android folder (SAF tree) and hand its URI and name to `apply`. */
const chooseFolder = async (current: string, apply: (uri: string, name: string) => void) => {
  try {
    const r = (await pickAndroidFolder(current || undefined)) as { uri?: string | null; name?: string | null } | null;
    if (r?.uri) apply(r.uri, r.name ?? "");
  } catch (e) {
    notify({ tone: "error", title: "Couldn't choose folder", body: e instanceof Error ? e.message : String(e) });
  }
};

export function SettingsPage({ phone, onSupportedSites }: { phone: boolean; onSupportedSites: () => void }) {
  const s = useSettings((x) => x);
  const bins = useBinaries();
  const health = healthOf(bins);
  const platform = getPlatform();
  const desktop = platform === "windows" || platform === "linux";
  const [confirmReset, setConfirmReset] = useState(false);
  const [storage, setStorage] = useState<{ granted: boolean; permanentlyDenied: boolean } | null | undefined>(undefined);
  useEffect(() => {
    if (platform !== "android") return;
    let alive = true;
    const check = () =>
      void storagePermissionStatus().then(
        (st) => alive && setStorage((prev) => ({ granted: st.granted, permanentlyDenied: st.permanentlyDenied || (!st.granted && !!prev?.permanentlyDenied) })),
        () => alive && setStorage(null),
      );
    check();
    // Back from the system settings screen: re-read the status.
    window.addEventListener("focus", check);
    return () => {
      alive = false;
      window.removeEventListener("focus", check);
    };
  }, [platform]);
  const grantStorage = async () => {
    if (storage?.permanentlyDenied) {
      await openAppSettings().catch(() => undefined);
      return;
    }
    try {
      const r = await requestStoragePermission();
      setStorage({ granted: r.granted, permanentlyDenied: r.permanentlyDenied });
    } catch (e) {
      notify({ tone: "error", title: "Couldn't ask for storage access", body: e instanceof Error ? e.message : String(e) });
    }
  };
  const [ytdlp, setYtdlp] = useState<YtdlpStatus | null | undefined>(undefined);
  useEffect(() => {
    if (platform !== "android") return;
    let alive = true;
    void androidYtdlpStatus().then((st) => {
      if (alive) setYtdlp(st);
    });
    return () => {
      alive = false;
    };
  }, [platform]);
  const recheckYtdlp = () => {
    setYtdlp(undefined);
    void androidYtdlpStatus({ refresh: true }).then(setYtdlp);
  };
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const width = useWidth(ref);
  const narrow = phone || (width > 0 && width < 760);
  const cardPad = phone ? "!p-4" : "";

  const btn = phone ? "h-11 shrink-0" : "shrink-0";
  const dlTarget: "downloads" | "gallery" | "folder" | "other" = s.saveTreeUri
    ? "folder"
    : s.saveDir === GALLERY_SAVE
      ? "gallery"
      : s.saveDir === DOWNLOADS_SAVE
        ? "downloads"
        : "other";
  const dlLabel =
    dlTarget === "folder"
      ? s.saveTreeName || "Chosen folder"
      : dlTarget === "gallery"
        ? "Gallery"
        : dlTarget === "downloads"
          ? "Download/Keepsake"
          : s.saveDir || "Keepsake's private folder";
  const editLabel: Record<EditSaveTarget, string> = {
    source: "Same folder as the original",
    downloads: "Download/Keepsake",
    gallery: "Gallery",
    folder: s.editTreeName || "Chosen folder",
  };
  const saveLabel = platform === "android" ? dlLabel : s.saveDir || "System Downloads";

  const downloads = (
    <>
      {platform !== "android" && (
        <FieldRow label="Save folder">
          <span
            className="selectable max-w-[min(220px,36vw)] min-w-0 truncate font-mono text-[11px] text-fg-2"
            title={saveLabel}
          >
            {saveLabel}
          </span>
          <Button
            size="sm"
            icon="folder"
            className={btn}
            onClick={async () => {
              const dir = await pickFolder(s.saveDir);
              if (dir) updateSettings({ saveDir: dir });
            }}
          >
            Change...
          </Button>
          {desktop && s.saveDir && (
            <Button size="sm" variant="ghost" icon="open" onClick={() => void openFile(s.saveDir)}>
              Open
            </Button>
          )}
        </FieldRow>
      )}
      <FieldRow label="Parallel downloads" hint="Choose a number from 1 to 10.">
        <Stepper
          label="Parallel downloads"
          value={s.parallelDownloads}
          min={1}
          max={10}
          onChange={(v) => updateSettings({ parallelDownloads: clampParallel(v) })}
        />
      </FieldRow>
      <FieldRow label="Embed cover art in audio">
        <Switch
          label="Embed cover art in audio"
          title="Adds cover art to MP3 and M4A files"
          checked={s.embedThumbnail}
          onChange={(v) => updateSettings({ embedThumbnail: v })}
        />
      </FieldRow>
      {desktop && (
        <FieldRow label="Embed thumbnail and metadata in videos" hint="Slower: rewrites the whole video file">
          <Switch
            label="Embed thumbnail and metadata in videos"
            title="Adds cover art and tags to video files"
            checked={s.embedVideoMeta}
            onChange={(v) => updateSettings({ embedVideoMeta: v })}
          />
        </FieldRow>
      )}
      <div className="pt-1">
        <Collapsible title="Advanced" subtitle="Sign-in cookies, codecs and clipboard" icon="bolt">
          {desktop && (
            <FieldRow label="Cookies from browser" hint="Firefox works best on Windows. Close Chromium browsers before fetching.">
              <Select
                label="Cookies from browser"
                title="Use your browser's sign-in for private or members-only content"
                className="w-[200px] max-w-full"
                value={s.cookiesBrowser}
                onChange={(v) => updateSettings({ cookiesBrowser: v })}
                options={COOKIE_BROWSERS}
              />
            </FieldRow>
          )}
          <FieldRow label="Prefer H.264">
            <Switch
              label="Prefer H.264"
              title="Best compatibility. YouTube offers H.264 up to 1080p only"
              checked={s.preferH264}
              onChange={(v) => updateSettings({ preferH264: v })}
            />
          </FieldRow>
          <FieldRow label="Detect links in clipboard">
            <Switch
              label="Detect links in clipboard"
              checked={s.clipboardDetect}
              onChange={(v) => updateSettings({ clipboardDetect: v })}
            />
          </FieldRow>
        </Collapsible>
      </div>
    </>
  );

  const choice = (active: boolean, label: string, onClick: () => void, icon?: "folder") => (
    <Button size="sm" icon={icon} variant={active ? "primary" : "ghost"} className={btn} aria-pressed={active} onClick={onClick}>
      {label}
    </Button>
  );
  const storageCard = (
    <>
      <FieldRow
        label="Storage access"
        hint={
          storage?.granted
            ? "Keepsake can save to your Downloads folder and next to your originals."
            : "Allow it so Keepsake can save to Downloads and keep edits next to the originals."
        }
      >
        {storage === undefined ? (
          <Skeleton className="h-6 w-20 rounded-md" />
        ) : storage?.granted ? (
          <Badge tone="success">
            <Dot tone="success" /> Allowed
          </Badge>
        ) : (
          <>
            <Badge tone="warning">Not allowed</Badge>
            <Button size="sm" variant="primary" className={btn} onClick={() => void grantStorage()}>
              {storage?.permanentlyDenied ? "Open settings" : "Grant"}
            </Button>
          </>
        )}
      </FieldRow>
      <FieldRow label="Downloads save to" hint={dlLabel}>
        {choice(dlTarget === "downloads", "Downloads", () => updateSettings({ saveTreeUri: "", saveTreeName: "", saveDir: DOWNLOADS_SAVE }))}
        {choice(dlTarget === "gallery", "Gallery", () => updateSettings({ saveTreeUri: "", saveTreeName: "", saveDir: GALLERY_SAVE }))}
        {choice(dlTarget === "folder", "Choose folder...", () => void chooseFolder(s.saveTreeUri, (uri, name) => updateSettings({ saveTreeUri: uri, saveTreeName: name, saveDir: "" })), "folder")}
      </FieldRow>
      <FieldRow label="Edited files save to" hint={editLabel[s.editSaveTarget]}>
        {choice(s.editSaveTarget === "source", "Same folder", () => updateSettings({ editSaveTarget: "source" }))}
        {choice(s.editSaveTarget === "downloads", "Downloads", () => updateSettings({ editSaveTarget: "downloads" }))}
        {choice(s.editSaveTarget === "gallery", "Gallery", () => updateSettings({ editSaveTarget: "gallery" }))}
        {choice(
          s.editSaveTarget === "folder",
          "Choose folder...",
          () => void chooseFolder(s.editTreeUri, (uri, name) => updateSettings({ editTreeUri: uri, editTreeName: name, editSaveTarget: "folder" })),
          "folder",
        )}
      </FieldRow>
    </>
  );

  const tone = health === "ready" || health === "unsupported" ? "success" : health === "ffmpeg" ? "warning" : health === "ytdlp" ? "danger" : "neutral";
  const healthText =
    health === "ready"
      ? "Ready"
      : health === "unsupported"
        ? "Built-in engine"
        : health === "ffmpeg"
          ? "ffmpeg missing"
          : health === "ytdlp"
            ? "yt-dlp missing"
            : "Checking";

  return (
    <div
      ref={ref}
      className={phone ? `flex min-w-0 flex-col gap-3 ${PAGE_BOTTOM}` : `bento ${PAGE_BOTTOM}`}
      style={phone ? undefined : { gridAutoRows: "minmax(88px, auto)" }}
    >
      <Card span={phone ? undefined : SPANS.downloads} {...listItem(reduced, 0)} narrow={narrow} className={cardPad} title="Downloads">
        {downloads}
      </Card>
      {platform === "android" && (
        <Card span={phone ? undefined : SPANS.storage} {...listItem(reduced, 1)} narrow={narrow} className={cardPad} title="Android storage">
          {storageCard}
        </Card>
      )}
      <Card span={phone ? undefined : SPANS.appearance} {...listItem(reduced, 1)} narrow={narrow} className={cardPad} title="Appearance">
        <RadioGroup<ThemePref>
          label="Theme"
          value={s.theme}
          onChange={(v) => updateSettings({ theme: v })}
          columns={3}
          compact={phone}
          options={[
            { value: "system", label: "System", description: "Follow the OS", art: <ThemeArt mode="system" /> },
            { value: "dark", label: "Dark", description: "Warm charcoal", art: <ThemeArt mode="dark" /> },
            { value: "light", label: "Light", description: "Soft paper", art: <ThemeArt mode="light" /> },
          ]}
        />
      </Card>
      <Card
        {...listItem(reduced, 2)}
        span={phone ? undefined : SPANS.tools}
        narrow={narrow}
        className={cardPad}
        title="Components"
        wrapHeader={phone}
        action={
          <div className="flex max-w-full min-w-0 flex-wrap items-center gap-1">
            <Button size="sm" variant="ghost" icon="copy" className="shrink-0" onClick={() => void copyDiagnostics()}>
              Copy diagnostics
            </Button>
            <Button size="sm" variant="ghost" icon="retry" className="shrink-0" onClick={() => {
                void refreshBinaries();
                if (platform === "android") recheckYtdlp();
              }}>
              Check
            </Button>
          </div>
        }
      >
        <div className="flex min-w-0 items-center gap-2">
          <Dot tone={tone} />
          {bins.state === "loading" ? (
            <Skeleton className="h-3 w-48 max-w-[50%]" />
          ) : bins.state === "error" ? (
            <span className="min-w-0 truncate text-danger" title={bins.error.message}>
              {bins.error.message}
            </span>
          ) : (
            <span className="min-w-0 truncate font-mono text-[12px] text-fg-2" title={versionsLine(bins.status)}>
              {versionsLine(bins.status)}
            </span>
          )}
          <Badge tone={tone} className="ml-auto shrink-0">
            {healthText}
          </Badge>
        </div>
        {platform === "android" && (
          <dl className="mt-3 flex min-w-0 flex-col gap-1.5">
            {ytdlp === undefined ? (
              <Skeleton className="h-3 w-40" />
            ) : ytdlp === null ? (
              <span className="text-fg-2">Status unavailable</span>
            ) : (
              <>
                {(
                  [
                    ["yt-dlp", ytdlp.ytdlp],
                    ["EJS solver", ytdlp.ejs],
                    ["JS runtime", ytdlp.jsRuntime],
                    ["ffmpeg", ytdlp.ffmpeg],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} className="flex min-w-0 items-baseline gap-2">
                    <dt className="w-24 max-w-[45%] shrink-0 truncate text-fg-2" title={label}>
                      {label}
                    </dt>
                    <dd
                      className={`min-w-0 truncate font-mono text-[12px] ${value ? "text-fg-2" : "text-danger"}`}
                      title={value ?? "missing"}
                    >
                      {value ?? "missing"}
                    </dd>
                  </div>
                ))}
                <div className="flex min-w-0 items-baseline gap-2">
                  <dt className="w-24 max-w-[45%] shrink-0 truncate text-fg-2" title="Self-contained">
                    Self-contained
                  </dt>
                  <dd
                    className={`min-w-0 truncate font-mono text-[12px] ${ytdlp.ready ? "text-fg-2" : "text-danger"}`}
                    title={ytdlp.problems.join(", ")}
                  >
                    {ytdlp.ready ? "Ready" : "Not ready"}
                    {ytdlp.problems.length > 0 ? ` (${ytdlp.problems.join(", ")})` : ""}
                  </dd>
                </div>
              </>
            )}
          </dl>
        )}
        <button
          type="button"
          onClick={onSupportedSites}
          className={`icon-host mt-3 inline-flex items-center gap-1.5 self-start text-[12px] font-medium text-accent hover:underline ${phone ? "min-h-11 pr-2" : ""}`}
        >
          <Icon name="globe" size={14} animated />
          Supported sites
        </button>
      </Card>
      <Card span={phone ? undefined : SPANS.reset} {...listItem(reduced, 3)} narrow={narrow} bodyClassName="justify-center" className={`justify-center ${cardPad}`}>
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-fg-2">Restore every setting to its default. Your library is kept.</span>
          <Button
            variant="danger-outline"
            icon="retry"
            size={phone ? "lg" : "md"}
            className="shrink-0"
            onClick={() => setConfirmReset(true)}
          >
            Reset settings
          </Button>
        </div>
      </Card>
      <ConfirmDialog
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        onConfirm={resetSettings}
        title="Reset settings?"
        description="Reset all settings to defaults? Your library is kept."
        confirmLabel="Reset"
        danger
      />
    </div>
  );
}

/** Tiny window preview drawn with the app's own palette (no new colours). */
function ThemeArt({ mode }: { mode: ThemePref }) {
  const dark = { bg: "#0b0908", side: "#0f0e0d", card: "#151413", line: "#262322" };
  const light = { bg: "#f6f6f7", side: "#eeedec", card: "#ffffff", line: "#e4e1df" };
  const pane = (p: typeof dark, clip?: string) => (
    <g clipPath={clip}>
      <rect width="96" height="56" fill={p.bg} />
      <rect width="22" height="56" fill={p.side} />
      <rect x="28" y="8" width="60" height="16" rx="5" fill={p.card} stroke={p.line} />
      <rect x="28" y="30" width="28" height="18" rx="5" fill={p.card} stroke={p.line} />
      <rect x="60" y="30" width="28" height="18" rx="5" fill="#e0634c" />
      <rect x="6" y="9" width="10" height="3" rx="1.5" fill="#e0634c" />
      <rect x="6" y="16" width="10" height="3" rx="1.5" fill={p.line} />
      <rect x="6" y="23" width="10" height="3" rx="1.5" fill={p.line} />
    </g>
  );
  const id = `theme-art-${mode}`;
  return (
    <svg viewBox="0 0 96 56" className="h-auto w-full overflow-hidden rounded-[10px_10px_10px_4px] border border-line" aria-hidden="true">
      {mode === "system" ? (
        <>
          <defs>
            <clipPath id={id}>
              <path d="M60 0H96V56H24z" />
            </clipPath>
          </defs>
          {pane(dark)}
          {pane(light, `url(#${id})`)}
        </>
      ) : (
        pane(mode === "dark" ? dark : light)
      )}
    </svg>
  );
}
