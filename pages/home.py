"""Home page: paste a link, preview it, choose options and download."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

import theme
from pages.common import PAGE_MAX_W, PAGE_PAD, centered
from widgets.common import ElidedLabel
from widgets.format_selector import FormatSelector
from widgets.video_card import VideoCard


class HomePage(QWidget):
    fetch_requested = pyqtSignal()
    download_requested = pyqtSignal()

    def __init__(self, config, parent=None):
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

        # --- URL bar: input with the Fetch button attached -------------
        url_row = QHBoxLayout()
        url_row.setContentsMargins(0, 0, 0, 0)
        url_row.setSpacing(0)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText(
            "Paste a video, playlist or audio link (YouTube and 1,000+ other sites)")
        self.url_input.setFixedHeight(40)
        self.url_action = self.url_input.addAction(
            theme.icon("link", "text3"), QLineEdit.ActionPosition.LeadingPosition)
        # Square clear action instead of Fusion's round clear button.
        self.clear_action = self.url_input.addAction(
            theme.icon("close", "text3"), QLineEdit.ActionPosition.TrailingPosition)
        self.clear_action.setToolTip("Clear")
        self.clear_action.setVisible(False)
        self.clear_action.triggered.connect(self.url_input.clear)
        self.url_input.textChanged.connect(
            lambda t: self.clear_action.setVisible(bool(t)))
        self.url_input.returnPressed.connect(self.fetch_requested)
        url_row.addWidget(self.url_input, 1)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.setObjectName("Fetch")
        self.fetch_btn.setFixedHeight(40)
        self.fetch_btn.setMinimumWidth(104)
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.clicked.connect(self.fetch_requested)
        url_row.addWidget(self.fetch_btn)
        lay.addLayout(url_row)

        # --- Video card --------------------------------------------------
        self.video_card = VideoCard()
        lay.addWidget(self.video_card)

        # --- Output options + stream table -------------------------------
        fmt_card = QFrame()
        fmt_card.setObjectName("Card")
        fmt_lay = QVBoxLayout(fmt_card)
        fmt_lay.setContentsMargins(16, 16, 16, 16)
        self.format_selector = FormatSelector()
        self.format_selector.apply_preferences(config)
        fmt_lay.addWidget(self.format_selector)
        lay.addWidget(fmt_card)
        # The card only grows while the stream table is open; otherwise the
        # free space goes below it instead of an empty area inside the card.
        self._filler = QWidget()
        self._filler.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._filler, 1)

        def _streams_toggled(opened, card=fmt_card, layout=lay):
            layout.setStretchFactor(card, 1 if opened else 0)
            self._filler.setVisible(not opened)

        self.format_selector.streams_head.toggled.connect(_streams_toggled)

        # --- Action row ----------------------------------------------------
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(16)
        self.embed_thumb_check = QCheckBox("Embed thumbnail as cover art")
        self.embed_thumb_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.embed_thumb_check.setChecked(config.get("embed_thumbnail", True))
        actions.addWidget(self.embed_thumb_check)

        self.status_label = ElidedLabel("Ready", mode=Qt.TextElideMode.ElideRight)
        self.status_label.setObjectName("StatusText")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        actions.addWidget(self.status_label, 1)

        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("Primary")
        self.download_btn.setFixedHeight(40)
        self.download_btn.setMinimumWidth(168)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.bind_icon(self.download_btn, "download", "on_accent", 16)
        self.download_btn.clicked.connect(self.download_requested)
        actions.addWidget(self.download_btn)
        lay.addLayout(actions)

        outer.addWidget(centered(inner, PAGE_MAX_W), 1)

    def retheme(self):
        self.url_action.setIcon(theme.icon("link", "text3"))
        self.clear_action.setIcon(theme.icon("close", "text3"))
        self.video_card.retheme()
