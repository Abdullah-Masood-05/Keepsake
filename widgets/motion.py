"""Shared animation timings and helpers so all motion feels the same.

Durations are short and use ease-out curves: things arrive quickly and
settle softly. Set KEEPSAKE_REDUCED_MOTION=1 to turn animations off.
"""

import os

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QParallelAnimationGroup, QPoint,
    QPropertyAnimation, QVariantAnimation,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect

FAST = 140      # hover/press feedback, small state changes
BASE = 220      # page transitions, toasts, expanding sections
SLOW = 320      # larger layout moves

EASE_OUT = QEasingCurve.Type.OutCubic
EASE_IN_OUT = QEasingCurve.Type.InOutCubic
EASE_SPRING = QEasingCurve.Type.OutBack  # tiny overshoot for "pop" moments

REDUCED = os.environ.get("KEEPSAKE_REDUCED_MOTION") == "1"


def duration(ms):
    return 0 if REDUCED else ms


def _keep(owner, anim, key):
    """Keep a reference so the animation isn't garbage-collected, and stop
    a previous animation of the same kind on the same widget."""
    old = getattr(owner, key, None)
    if old is not None and old.state() == QAbstractAnimation.State.Running:
        old.stop()
    setattr(owner, key, anim)
    return anim


def animate(target, prop, start, end, ms=BASE, curve=EASE_OUT, finished=None, key=None):
    """Animate a Qt property (bytes name, e.g. b"pos") from start to end."""
    anim = QPropertyAnimation(target, prop, target)
    anim.setDuration(duration(ms))
    if start is not None:
        anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(curve)
    if finished:
        anim.finished.connect(finished)
    _keep(target, anim, key or f"_anim_{prop.decode()}")
    anim.start()
    return anim


def tween(owner, start, end, on_value, ms=BASE, curve=EASE_OUT, finished=None, key="_anim_tween"):
    """Animate a plain value and call on_value(v) each frame."""
    anim = QVariantAnimation(owner)
    anim.setDuration(duration(ms))
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(curve)
    anim.valueChanged.connect(on_value)
    if finished:
        anim.finished.connect(finished)
    _keep(owner, anim, key)
    anim.start()
    return anim


def fade_in(widget, ms=BASE, rise=0, finished=None):
    """Fade a widget in (optionally rising `rise` px). The opacity effect is
    removed afterwards: graphics effects make every repaint slower."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    group = QParallelAnimationGroup(widget)
    fade = QPropertyAnimation(effect, b"opacity", group)
    fade.setDuration(duration(ms))
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(EASE_OUT)
    group.addAnimation(fade)
    if rise and widget.parentWidget() is not None and not _in_layout(widget):
        end = widget.pos()
        move = QPropertyAnimation(widget, b"pos", group)
        move.setDuration(duration(ms))
        move.setStartValue(end + QPoint(0, rise))
        move.setEndValue(end)
        move.setEasingCurve(EASE_OUT)
        group.addAnimation(move)

    def done():
        widget.setGraphicsEffect(None)
        if finished:
            finished()

    group.finished.connect(done)
    _keep(widget, group, "_anim_fade")
    group.start()
    return group


def fade_out(widget, ms=FAST, finished=None):
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(1.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration(ms))
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(EASE_IN_OUT)
    if finished:
        anim.finished.connect(finished)
    _keep(widget, anim, "_anim_fade")
    anim.start()
    return anim


def _in_layout(widget):
    parent = widget.parentWidget()
    lay = parent.layout() if parent is not None else None
    return lay is not None and lay.indexOf(widget) >= 0
