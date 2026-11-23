import { platform } from "../engine/platform";
import { DOWNLOADS_SAVE } from "../engine/android-gallery";
import { loadSettings, saveSettings } from "./persist";
import { createStore, useStore } from "./store";
import {
  DEFAULT_SETTINGS,
  migrateSettings,
  sanitizeSettings,
  type Settings,
  type ThemePref,
} from "./settings-core";

export * from "./settings-core";

export const settingsStore = createStore<Settings>(DEFAULT_SETTINGS);

let saveTimer: ReturnType<typeof setTimeout> | undefined;
settingsStore.subscribe(() => {
  applyTheme(settingsStore.get().theme);
  // Debounced 300ms per UI_LAYOUT.md; no Save button.
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => void saveSettings(settingsStore.get()), 300);
});

export async function initSettings(): Promise<Settings> {
  const loaded = migrateSettings(await loadSettings(), platform() === "android");
  settingsStore.set(loaded);
  applyTheme(loaded.theme);
  return loaded;
}

export function updateSettings(patch: Partial<Settings>) {
  settingsStore.set((prev) => sanitizeSettings({ ...prev, ...patch }));
}

export function resetSettings() {
  settingsStore.set((prev) => ({
    ...DEFAULT_SETTINGS,
    saveDir: platform() === "android" ? DOWNLOADS_SAVE : "",
    storagePromptShown: prev.storagePromptShown,
  }));
}

export function useSettings<S>(select: (s: Settings) => S): S {
  return useStore(settingsStore, select);
}

// ---- Theme ----

const media =
  typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;

export function resolveTheme(pref: ThemePref): "dark" | "light" {
  if (pref !== "system") return pref;
  return media && !media.matches ? "light" : "dark";
}

function applyTheme(pref: ThemePref) {
  document.documentElement.dataset.theme = resolveTheme(pref);
}

media?.addEventListener("change", () => {
  if (settingsStore.get().theme === "system") applyTheme("system");
});

/** Mod+Shift+L and the titlebar button: cycle system -> light -> dark. */
export function cycleTheme() {
  const order: ThemePref[] = ["system", "light", "dark"];
  const cur = settingsStore.get().theme;
  updateSettings({ theme: order[(order.indexOf(cur) + 1) % order.length] });
}

/** Flip between dark and light based on what is showing now. */
export function toggleDarkLight() {
  const shown = resolveTheme(settingsStore.get().theme);
  updateSettings({ theme: shown === "dark" ? "light" : "dark" });
}
