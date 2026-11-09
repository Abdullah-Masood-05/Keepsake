import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";
import { useActiveCount } from "../../state/downloads";
import { MOD } from "../../state/format";
import { navigate, PAGE_TITLES, usePage } from "../../state/nav";
import { cycleTheme, useSettings, type ThemePref } from "../../state/settings";
import { IconButton } from "../ui/Button";
import { Logo, type IconName } from "../ui/Icon";
import { press, t } from "../ui/motion";
import { WindowControls } from "./WindowControls";

const THEME_ICON: Record<ThemePref, IconName> = { system: "monitor", light: "sun", dark: "moon" };
const NEXT_LABEL: Record<ThemePref, string> = {
  system: "Switch to light",
  light: "Switch to dark",
  dark: "Use system theme",
};

/**
 * In-app header (56px). Native decorations stay on (UI_LAYOUT.md), so the
 * header is also a drag region on desktop via data-tauri-drag-region.
 */
export function Titlebar({ action, compact }: { action?: ReactNode; compact?: boolean }) {
  const page = usePage();
  const theme = useSettings((s) => s.theme);
  const active = useActiveCount();
  return (
    <header
      data-tauri-drag-region
      className={`flex shrink-0 items-center justify-between gap-3 ${compact ? "safe-top h-14 px-4" : "h-14 px-6"}`}
    >
      <div data-tauri-drag-region className="flex min-w-0 items-center gap-2.5">
        {compact && <Logo size={28} />}
        <h1 data-tauri-drag-region className="truncate text-[20px] leading-7 font-semibold tracking-[-0.01em]">
          {PAGE_TITLES[page]}
        </h1>
      </div>
      <div className="flex items-center gap-2">
        {action}
        <IconButton
          icon={THEME_ICON[theme]}
          label={`${NEXT_LABEL[theme]} (${MOD}+Shift+L)`}
          size={compact ? 48 : 36}
          onClick={cycleTheme}
        />
        <AnimatePresence initial={false}>
          {active > 0 && (
            <motion.button
              type="button"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              whileTap={press}
              transition={t.fast}
              onClick={() => navigate("downloads")}
              className="tabular flex h-8 items-center gap-1.5 rounded-full bg-accent-soft px-3 text-[12px] font-medium text-accent transition-[box-shadow] duration-150 hover:shadow-[inset_0_0_0_1px_var(--accent-border)]"
              title="Active downloads"
            >
              <span className="spinner size-3" aria-hidden="true" />
              {active} active
            </motion.button>
          )}
        </AnimatePresence>
        {!compact && <WindowControls />}
      </div>
    </header>
  );
}
