// @ts-nocheck -- bun:test types are not in tsconfig; bun runs this file, tsc does not need to.
/** Settings sanitising and the one-time Android save-target migration (settingsVersion). */
import { describe, expect, test } from "bun:test";
import { DOWNLOADS_SAVE, GALLERY_SAVE } from "../../engine/android-gallery";
import { DEFAULT_SETTINGS, migrateSettings, sanitizeSettings, SETTINGS_VERSION } from "../settings-core";

describe("migrateSettings", () => {
  test("a fresh Android install saves downloads to Download/Keepsake and edits next to the original", () => {
    const s = migrateSettings(null, true);
    expect(s.saveDir).toBe(DOWNLOADS_SAVE);
    expect(s.editSaveTarget).toBe("source");
    expect(s.settingsVersion).toBe(SETTINGS_VERSION);
    expect(s.storagePromptShown).toBe(false);
  });

  test("existing Android settings pointing at the app folder (empty or inside app data) move to Downloads once", () => {
    for (const dir of ["", "/data/user/0/app.keepsake/files", "/data/data/app.keepsake/files/dl", "/storage/emulated/0/Android/data/app.keepsake/files"]) {
      const s = migrateSettings({ saveDir: dir, saveTreeUri: "", settingsVersion: 1 }, true);
      expect(s.saveDir).toBe(DOWNLOADS_SAVE);
      expect(s.settingsVersion).toBe(SETTINGS_VERSION);
    }
    // Stored settings from before versioning (no field) migrate too.
    expect(migrateSettings({ saveDir: "" }, true).saveDir).toBe(DOWNLOADS_SAVE);
  });

  test("Gallery, a chosen folder and public folders are left alone", () => {
    expect(migrateSettings({ saveDir: GALLERY_SAVE }, true).saveDir).toBe(GALLERY_SAVE);
    const tree = migrateSettings({ saveDir: "", saveTreeUri: "content://tree/abc", saveTreeName: "Pics" }, true);
    expect(tree.saveDir).toBe("");
    expect(tree.saveTreeUri).toBe("content://tree/abc");
    expect(migrateSettings({ saveDir: "/storage/emulated/0/Movies" }, true).saveDir).toBe("/storage/emulated/0/Movies");
  });

  test("runs once: a stored current version is never touched, even with an empty saveDir", () => {
    const s = migrateSettings({ saveDir: "", settingsVersion: SETTINGS_VERSION }, true);
    expect(s.saveDir).toBe("");
  });

  test("desktop keeps its save folder and only gets the version", () => {
    const s = migrateSettings({ saveDir: "" }, false);
    expect(s.saveDir).toBe("");
    expect(s.settingsVersion).toBe(SETTINGS_VERSION);
    expect(migrateSettings({ saveDir: "D:\\Videos" }, false).saveDir).toBe("D:\\Videos");
  });

  test("other settings survive the migration", () => {
    const s = migrateSettings({ saveDir: "", parallelDownloads: 7, theme: "light" }, true);
    expect(s.parallelDownloads).toBe(7);
    expect(s.theme).toBe("light");
  });
});

describe("sanitizeSettings: new fields", () => {
  test("defaults and coercion", () => {
    const d = sanitizeSettings({ settingsVersion: SETTINGS_VERSION });
    expect(d.editSaveTarget).toBe("source");
    expect(d.editTreeUri).toBe("");
    expect(d.storagePromptShown).toBe(false);
    const bad = sanitizeSettings({ editSaveTarget: "nowhere", editTreeUri: 5, storagePromptShown: 1 });
    expect(bad.editSaveTarget).toBe("source");
    expect(bad.editTreeUri).toBe("");
    expect(bad.storagePromptShown).toBe(true);
    expect(sanitizeSettings({ editSaveTarget: "gallery" }).editSaveTarget).toBe("gallery");
  });

  test("DEFAULT_SETTINGS carries the current version", () => {
    expect(DEFAULT_SETTINGS.settingsVersion).toBe(SETTINGS_VERSION);
  });
});
