import type { LibraryItem } from "./models";
import { loadLibrary, saveLibrary } from "./persist";
import { createStore, useStore } from "./store";

export const libraryStore = createStore<LibraryItem[]>([]);

let ready = false;
libraryStore.subscribe(() => {
  if (ready) void saveLibrary(libraryStore.get());
});

export async function initLibrary(): Promise<void> {
  const items = await loadLibrary();
  const sorted = items.slice();
  sorted.sort((a, b) => b.date - a.date);
  libraryStore.set(sorted);
  ready = true;
}

export function addLibraryItem(item: LibraryItem) {
  libraryStore.set((prev) => [item, ...prev.filter((i) => i.id !== item.id)]);
}

export function removeLibraryItem(id: string) {
  libraryStore.set((prev) => prev.filter((i) => i.id !== id));
}

export function useLibrary(): LibraryItem[] {
  return useStore(libraryStore, (s) => s);
}

export interface LibraryStats {
  today: number;
  totalBytes: number;
  successRate: number | null;
  items: number;
}

export function computeStats(items: LibraryItem[]): LibraryStats {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  let today = 0;
  let totalBytes = 0;
  let done = 0;
  for (const i of items) {
    if (i.status === "done") {
      done++;
      totalBytes += i.sizeBytes ?? 0;
      if (i.date >= start.getTime()) today++;
    }
  }
  const finished = items.filter((i) => i.status !== "cancelled").length;
  return {
    today,
    totalBytes,
    successRate: finished ? Math.round((done / finished) * 100) : null,
    items: done,
  };
}
