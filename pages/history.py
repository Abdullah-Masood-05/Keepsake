"""History page: searchable list of completed downloads."""

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

import theme
from pages.common import PAGE_PAD, centered, empty_state, page_header
from widgets.common import ElidedLabel

_MAX_ROWS = 300


def parse_history(content):
    """Parse the history log into [(timestamp, title, url, format)], oldest first."""
    entries = []
    for block in content.split("-" * 80):
        lines = [l.rstrip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        head = lines[0]
        ts, title = "", head
        if head.startswith("[") and "]" in head:
            ts, title = head[1:head.index("]")], head[head.index("]") + 1:].strip()
        url = fmt = ""
        for l in lines[1:]:
            l = l.strip()
            if l.startswith("URL:"):
                url = l[4:].strip()
            elif l.startswith("Format:"):
                fmt = l[7:].strip()
        entries.append((ts, title, url, fmt))
    return entries


class HistoryRow(QFrame):
    def __init__(self, ts, title, url, fmt, parent=None):
        super().__init__(parent)
        self.setObjectName("HistoryRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.haystack = f"{title}\n{url}\n{fmt}".lower()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = ElidedLabel(title)
        t.setObjectName("HistoryTitle")
        col.addWidget(t)
        self.url_btn = QPushButton(url or "No link")
        self.url_btn.setObjectName("LinkButton")
        self.url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.url_btn.setToolTip("Open in browser")
        self.url_btn.setStyleSheet("text-align:left; padding-left:0px;")
        self.url_btn.setEnabled(bool(url))
        self.url_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        self.url_btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        col.addWidget(self.url_btn)
        lay.addLayout(col, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        if fmt and fmt != "N/A":
            chip = QLabel(fmt if len(fmt) < 28 else fmt[:26] + "...")
            chip.setObjectName("HistoryChip")
            chip.setToolTip(fmt)
            right.addWidget(chip, 0, Qt.AlignmentFlag.AlignRight)
        when = QLabel(ts)
        when.setObjectName("HistoryMeta")
        when.setFont(theme.tabular(when.font()))
        right.addWidget(when, 0, Qt.AlignmentFlag.AlignRight)
        lay.addLayout(right)


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Workspace")
        self._rows = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(PAGE_PAD, 28, PAGE_PAD, 24)
        outer.setSpacing(0)
        inner = QWidget()
        inner.setObjectName("Workspace")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        head, _t, self.subtitle, actions = page_header("History", "")
        self.search = QLineEdit()
        self.search.setObjectName("SearchInput")
        self.search.setPlaceholderText("Search history")
        self.search.setFixedWidth(240)
        self._search_action = self.search.addAction(
            theme.icon("search", "text3"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._apply_filter)
        actions.addWidget(self.search)
        lay.addLayout(head)

        self.stack = QStackedWidget()
        self.empty, self.empty_icon, _ = empty_state(
            "history", "No history yet", "Completed downloads are listed here.")
        self.no_match, self.no_match_icon, _ = empty_state(
            "search", "No matches", "Nothing in your history matches that search.")

        self.scroll = QScrollArea()
        self.scroll.setObjectName("DownloadsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.container.setObjectName("DownloadsContainer")
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.container)
        frame = QFrame()
        frame.setObjectName("HistoryList")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.addWidget(self.scroll)

        self.stack.addWidget(self.empty)      # 0
        self.stack.addWidget(frame)           # 1
        self.stack.addWidget(self.no_match)   # 2
        lay.addWidget(self.stack, 1)
        outer.addWidget(centered(inner), 1)

    def set_entries(self, entries):
        """entries: [(ts, title, url, fmt)], oldest first."""
        for r in self._rows:
            self.list_layout.removeWidget(r)
            r.deleteLater()
        self._rows = []
        for ts, title, url, fmt in reversed(entries[-_MAX_ROWS:]):
            row = HistoryRow(ts, title, url, fmt)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            self._rows.append(row)
        n = len(entries)
        self.subtitle.setText(f"{n} download{'s' if n != 1 else ''}" if n
                              else "Completed downloads appear here")
        self.search.setEnabled(bool(n))
        self._apply_filter()

    def _apply_filter(self, *_):
        q = self.search.text().strip().lower()
        shown = 0
        for r in self._rows:
            vis = (not q) or q in r.haystack
            r.setVisible(vis)
            shown += vis
        if not self._rows:
            self.stack.setCurrentIndex(0)
        elif shown == 0:
            self.stack.setCurrentIndex(2)
        else:
            self.stack.setCurrentIndex(1)

    def retheme(self):
        self._search_action.setIcon(theme.icon("search", "text3"))
        self.empty_icon.retint()
        self.no_match_icon.retint()
