"""Downloads page: live list of queued / running / finished downloads."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from widgets import motion
from pages.common import (
    PAGE_PAD, centered, empty_state, page_button, page_header,
)


class DownloadsPage(QWidget):
    go_home = pyqtSignal()
    clear_finished = pyqtSignal()
    cancel_all = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Workspace")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(PAGE_PAD, 28, PAGE_PAD, 24)
        outer.setSpacing(0)

        inner = QWidget()
        inner.setObjectName("Workspace")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        head, _t, self.subtitle, actions = page_header("Downloads", "No downloads yet")
        self.clear_btn = page_button("Clear finished", "clear")
        self.clear_btn.clicked.connect(self.clear_finished)
        self.cancel_btn = page_button("Cancel all", "x_circle", danger=True)
        self.cancel_btn.clicked.connect(self.cancel_all)
        actions.addWidget(self.clear_btn)
        actions.addWidget(self.cancel_btn)
        lay.addLayout(head)

        self.stack = QStackedWidget()
        self._removing = 0
        self._total = 0

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
        list_frame = QFrame()
        list_frame.setObjectName("HistoryList")
        fl = QVBoxLayout(list_frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.addWidget(self.scroll)

        self.empty, self.empty_icon, self.empty_btn = empty_state(
            "downloads", "No downloads yet",
            "Fetch a video, choose a quality and press Download.\n"
            "Progress shows up here.", "Go to Home")
        self.empty_btn.clicked.connect(self.go_home)

        self.stack.addWidget(self.empty)
        self.stack.addWidget(list_frame)
        lay.addWidget(self.stack, 1)
        outer.addWidget(centered(inner), 1)

    def add_widget(self, w):
        # Newest first; the trailing stretch keeps rows packed at the top.
        self.list_layout.insertWidget(0, w)
        if not self.isVisible() or motion.REDUCED:
            return
        # Grow the row open while it fades in so the rows below glide down.
        target = w.sizeHint().height()
        w.setMaximumHeight(0)

        def grow(v):
            w.setMaximumHeight(int(v))

        def grown():
            w.setMaximumHeight(16777215)

        motion.tween(w, 0, target, grow, ms=motion.BASE, finished=grown,
                     key="_anim_height")
        motion.fade_in(w, ms=motion.BASE)

    def remove_widget(self, w):
        if not self.isVisible() or motion.REDUCED:
            self._drop(w)
            return
        self._removing += 1
        w.setEnabled(False)

        def collapse():
            start = max(1, w.height())
            motion.tween(w, start, 0, lambda v: w.setMaximumHeight(int(v)),
                         ms=motion.FAST, curve=motion.EASE_IN_OUT,
                         finished=gone, key="_anim_height")

        def gone():
            self._removing -= 1
            self._drop(w)
            self._apply_stack()

        motion.fade_out(w, ms=motion.FAST, finished=collapse)

    def _drop(self, w):
        self.list_layout.removeWidget(w)
        w.hide()
        w.deleteLater()

    def _apply_stack(self):
        want = 1 if (self._total or self._removing) else 0
        if want == self.stack.currentIndex():
            return
        self.stack.setCurrentIndex(want)
        if want == 0 and self.isVisible() and not motion.REDUCED:
            motion.fade_in(self.empty, ms=motion.BASE, rise=0)

    def update_state(self, total, active, finished):
        self._total = total
        self._apply_stack()
        self.clear_btn.setEnabled(finished > 0)
        self.cancel_btn.setEnabled(active > 0)
        self.clear_btn.setVisible(total > 0)
        self.cancel_btn.setVisible(total > 0)
        if not total:
            self.subtitle.setText("No downloads yet")
        else:
            self.subtitle.setText(f"{active} active, {finished} finished")

    def retheme(self):
        self.empty_icon.retint()
