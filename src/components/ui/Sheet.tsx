import type { ReactNode } from "react";
import { Dialog } from "./Dialog";
import { Icon, type IconName } from "./Icon";

/**
 * Phone overlay (UI_MOBILE.md). No bottom sheets: this is a centered modal with a
 * 16px gutter, max 85vh, internal scroll, spring entrance, Esc / backdrop close.
 * Name kept so existing imports (Home, DownloadRow, LibraryList) stay valid.
 */
export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title ?? "Options"} phone bodyClassName="flex flex-col">
      {children}
    </Dialog>
  );
}

export interface SheetAction {
  label: string;
  icon: IconName;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
}

/** Centered list of actions: 48px rows with 20px icons. */
export function ActionSheet({
  open,
  onClose,
  title,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  actions: SheetAction[];
}) {
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <div className="-mx-2 flex flex-col gap-1" role="menu">
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            role="menuitem"
            disabled={a.disabled}
            onClick={() => {
              onClose();
              a.onSelect();
            }}
            className={`flex min-h-12 w-full shrink-0 items-center gap-3 rounded-md px-3 text-left text-[14px] font-medium transition-colors duration-150 outline-offset-[-2px] disabled:opacity-45 ${
              a.danger ? "text-danger active:bg-danger/10" : "text-fg active:bg-accent-soft"
            } hover:bg-card-hover`}
          >
            <Icon name={a.icon} size={20} className={a.danger ? "" : "text-fg-2"} />
            {a.label}
          </button>
        ))}
      </div>
    </Sheet>
  );
}
