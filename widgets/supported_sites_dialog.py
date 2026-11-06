"""Dialog listing the sites yt-dlp can download from.

Usage from main.py:
    from widgets.supported_sites_dialog import SupportedSitesDialog
    SupportedSitesDialog(self).exec()

Standalone preview (run from the project root):
    python -m widgets.supported_sites_dialog [dark|light]
"""

import time

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableView, QVBoxLayout,
)

import theme
from widgets.common import hairline

GITHUB_LIST_URL = "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"
FOOTNOTE = (
    "Most sites work without signing in. Some need cookies from your browser "
    "for private or age-restricted content."
)

# Built once per process; gen_extractor_classes() walks every extractor module.
_SITES_CACHE = None


def _clean_desc(desc):
    """IE_DESC may be False/None (hidden extractor) or a string with stray
    whitespace; return a single-line string or ''."""
    if not isinstance(desc, str):
        return ""
    return " ".join(desc.split())


def _is_working(ie):
    working = getattr(ie, "working", None)
    if callable(working):
        try:
            return working() is not False
        except Exception:
            pass
    return getattr(ie, "_WORKING", True) is not False


def load_sites():
    """Return [(site, description, variants)] sorted by site name.

    'vimeo', 'vimeo:album', 'vimeo:channel' collapse into one row
    ('vimeo', desc, ('album', 'channel')). The generic extractor and
    extractors marked as not working are dropped.
    """
    global _SITES_CACHE
    if _SITES_CACHE is not None:
        return _SITES_CACHE

    from yt_dlp.extractor import gen_extractor_classes

    groups = {}  # lower-case base name -> {"name", "desc", "variants"}
    seen = set()
    for ie in gen_extractor_classes():
        name = getattr(ie, "IE_NAME", None)
        if not name or name in seen:
            continue
        seen.add(name)
        base, sep, sub = name.partition(":")
        # The generic extractor (and its generic:* helpers) is the fallback
        # for every URL, not a site, so it is not listed.
        if base == "generic" or not _is_working(ie):
            continue

        key = base.lower()
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"name": base, "desc": "", "variants": set()}
        if not sep:
            g["name"] = base
            g["desc"] = _clean_desc(getattr(ie, "IE_DESC", None))
        elif sub:
            g["variants"].add(sub)

    rows = []
    for key in sorted(groups):
        g = groups[key]
        rows.append((g["name"], g["desc"], tuple(sorted(g["variants"]))))
    _SITES_CACHE = rows
    return rows


def _rounded_count(n):
    """1857 -> '1,800+' so the headline never overstates the list."""
    return f"{(n // 100) * 100:,}+"


class _SitesModel(QAbstractTableModel):
    COL_SITE, COL_DESC = 0, 1
    HEADERS = ("Site", "Description")

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 2

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        name, desc, variants = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return name if col == self.COL_SITE else desc
        if role == Qt.ItemDataRole.ToolTipRole:
            if variants:
                return f"{name}: " + ", ".join(variants)
            return name
        if role == Qt.ItemDataRole.ForegroundRole and col == self.COL_DESC:
            return QColor(theme.color("text2"))
        return None


class SupportedSitesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Supported sites")
        self.resize(520, 600)
        self.setMinimumSize(420, 420)

        rows = load_sites()
        self._total = len(rows)

        self._model = _SitesModel(rows, self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)  # match site name and description
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Supported sites", self)
        title.setObjectName("AppName")
        root.addWidget(title)

        count = QLabel(f"{_rounded_count(self._total)} sites via yt-dlp", self)
        count.setObjectName("Muted")
        root.addWidget(count)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search sites")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        root.addWidget(self._search)

        self._table = QTableView(self)
        self._table.setModel(self._proxy)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setWordWrap(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        self._table.setColumnWidth(0, 200)
        self._table.setSortingEnabled(True)
        self._proxy.sort(0, Qt.SortOrder.AscendingOrder)
        root.addWidget(self._table, 1)

        self._status = QLabel(self)
        self._status.setObjectName("Faint")
        root.addWidget(self._status)

        root.addWidget(hairline(parent=self))

        note = QLabel(
            f'{FOOTNOTE} <a href="{GITHUB_LIST_URL}">Full list on GitHub</a>', self
        )
        note.setObjectName("Muted")
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setOpenExternalLinks(True)
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton("Close", self)
        close_btn.setMinimumWidth(96)
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

        self._update_status("")
        self._search.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        # Dark/light title bar to match the main window (Windows only).
        theme.apply_window_chrome(self)

    def _on_search(self, text):
        self._proxy.setFilterFixedString(text.strip())
        self._update_status(text.strip())

    def _update_status(self, text):
        shown = self._proxy.rowCount()
        if not text:
            self._status.setText(f"{self._total:,} sites")
        elif shown == 0:
            self._status.setText(f'No sites match "{text}"')
        else:
            self._status.setText(f"{shown:,} of {self._total:,} sites match")


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    theme.apply(app, sys.argv[1] if len(sys.argv) > 1 else "dark")
    dlg = SupportedSitesDialog()
    dlg.exec()
    theme.shutdown(app)
