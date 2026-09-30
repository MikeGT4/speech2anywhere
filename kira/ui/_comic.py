# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import ctypes
import logging
import sys

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QEasingCurve, QEvent, QObject, QPointF, QRectF, QSize, Qt, QUrl, QVariantAnimation
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QFontDatabase, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QAbstractButton, QButtonGroup, QComboBox, QHBoxLayout, QLabel, QMenu, QSizePolicy, QSlider,
    QStyledItemDelegate, QVBoxLayout, QWidget, QWidgetAction,
)

from kira._resources import assets_dir

log = logging.getLogger(__name__)

INK = "#111111"
YELLOW = "#FFC400"
YELLOW_HOVER = "#FFD23F"
CREAM = "#FFFBF0"
TINT = "#FFF3C7"
HOVER = "#FFF8DC"
OPTION_ACTIVE = "#FFF1B8"
TRACK = "#EFE9D6"
LABEL = "#555555"
RED = "#E5484D"
RED_TEXT = "#C2262B"

_FONT_FILES = {600: "Baloo2-SemiBold.ttf", 700: "Baloo2-Bold.ttf", 800: "Baloo2-ExtraBold.ttf"}
_WEIGHTS = {600: QFont.Weight.DemiBold, 700: QFont.Weight.Bold, 800: QFont.Weight.ExtraBold}
_families: dict[int, str] = {}


def load_fonts() -> dict[int, str]:
    if _families:
        return _families
    for weight, name in _FONT_FILES.items():
        path = assets_dir() / "fonts" / name
        font_id = QFontDatabase.addApplicationFont(str(path)) if path.exists() else -1
        found = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        _families[weight] = found[0] if found else "Segoe UI"
    return _families


def baloo(weight: int, px: int) -> QFont:
    font = QFont(load_fonts()[weight])
    font.setPixelSize(px)
    font.setWeight(_WEIGHTS[weight])
    return font


def dark_titlebar(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.c_void_p(int(widget.winId()))
        dwm = ctypes.windll.dwmapi
        for attribute, value in ((20, 1), (35, 0x00111111), (36, 0x00FFFFFF), (34, 0x00111111)):
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, ctypes.c_uint(attribute), ctypes.byref(data), ctypes.sizeof(data))
    except Exception:
        log.debug("DWM-Titelleiste nicht gesetzt", exc_info=True)


class _InkTitlebar(QObject):
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and obj.isWindow():
            obj.removeEventFilter(self)
            dark_titlebar(obj)
        return False


def ink_titlebar_on_show(widget: QWidget) -> None:
    widget.installEventFilter(_InkTitlebar(widget))


_DWM_PLAIN = ((2, 1), (33, 1), (34, 0xFFFFFFFE))


def without_window_border(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.c_void_p(int(widget.winId()))
        for attribute, value in _DWM_PLAIN:
            data = ctypes.c_uint(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, ctypes.c_uint(attribute), ctypes.byref(data),
                                                      ctypes.sizeof(data))
    except Exception:
        log.debug("Fensterrand nicht abgeschaltet", exc_info=True)


class _BorderOff(QObject):
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and obj.isWindow():
            obj.removeEventFilter(self)
            without_window_border(obj)
        return False


def border_off_on_show(widget: QWidget) -> None:
    widget.installEventFilter(_BorderOff(widget))


def mascot_pixmap(size: int) -> QPixmap | None:
    src = assets_dir() / "icon-branded.ico"
    if not src.exists():
        return None
    try:
        img = Image.open(src)
        ico = getattr(img, "ico", None)
        if ico is not None:
            sizes = sorted(ico.sizes(), key=lambda s: s[0] * s[1])
            if sizes:
                img.size = sizes[-1]  # type: ignore[misc]
                img.load()
        img = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        return QPixmap.fromImage(ImageQt(img))
    except Exception:
        log.exception("icon-branded.ico nicht geladen")
        return None


DIGITALROOTS_URL = "https://www.digitalroots.de/"


def _open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


class _LogoLink(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("www.digitalroots.de")
        self.setAccessibleName("digitalroots, Webseite öffnen")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            _open_url(DIGITALROOTS_URL)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            _open_url(DIGITALROOTS_URL)
            event.accept()
            return
        super().keyPressEvent(event)


def brand_logo(height: int) -> QLabel:
    label = _LogoLink()
    try:
        img = Image.open(assets_dir() / "digitalroots-logo.png").convert("RGBA")
        img = img.crop(img.getbbox())
        ratio = 2
        img = img.resize((round(img.width * height * ratio / img.height), height * ratio), Image.Resampling.LANCZOS)
        pix = QPixmap.fromImage(ImageQt(img))
        pix.setDevicePixelRatio(ratio)
        label.setPixmap(pix)
    except OSError:
        log.warning("digitalroots-Logo nicht geladen, Text statt Bild")
        label.setText("digitalroots")
    return label


def alert_pixmap(kind: str, size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    shadow = 3.0
    if kind == "warning":
        shape = QPainterPath()
        shape.addPolygon(QPolygonF([QPointF(s * 0.47, s * 0.06), QPointF(s * 0.9, s * 0.86),
                                    QPointF(s * 0.04, s * 0.86)]))
        shape.closeSubpath()
        fill, mark, mark_box = QColor(YELLOW), QColor(INK), QRectF(0, s * 0.24, s * 0.94, s * 0.62)
    else:
        shape = QPainterPath()
        shape.addEllipse(QRectF(s * 0.05, s * 0.05, s * 0.84, s * 0.84))
        fill, mark, mark_box = QColor(RED), QColor("#FFFFFF"), QRectF(0, 0, s * 0.94, s * 0.94)
    pen = QPen(QColor(INK), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(INK))
    p.drawPath(shape.translated(shadow, shadow))
    p.setPen(pen)
    p.setBrush(fill)
    p.drawPath(shape)
    p.setPen(mark)
    p.setFont(baloo(800, round(s * 0.5)))
    p.drawText(mark_box, Qt.AlignmentFlag.AlignCenter, "!")
    p.end()
    return pix


def style_combo(combo: QComboBox) -> QComboBox:
    combo.setItemDelegate(QStyledItemDelegate(combo))
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    return combo


def dialog_qss() -> str:
    fam = load_fonts()
    chevron = (assets_dir() / "ui" / "chevron-down.svg").as_posix()
    check = (assets_dir() / "ui" / "check.svg").as_posix()
    field = f"""
        background: #FFFFFF; color: {INK};
        border: 2px solid {INK}; border-bottom: 5px solid {INK}; border-radius: 12px;
        padding: 0 14px; min-height: 36px;
        font-family: "Segoe UI"; font-size: 16px;
        selection-background-color: {YELLOW}; selection-color: {INK};
    """
    return f"""
        QDialog {{ background: {CREAM}; }}
        QLabel {{ color: {INK}; background: transparent; }}
        QLabel#comicSub {{ color: {LABEL}; font-family: "Segoe UI"; font-size: 13px; }}
        QLabel#comicWarn {{ color: {RED_TEXT}; font-family: "Segoe UI"; font-size: 13px; font-weight: 600; }}
        QLabel#comicNote {{ color: {LABEL}; font-family: "Segoe UI"; font-size: 13px; }}
        QLabel#comicValue {{ color: {INK}; font-family: "Segoe UI"; font-size: 16px; }}
        QLabel#comicBadge {{
            color: #FFFFFF; background: {RED}; border: 2px solid {INK}; border-radius: 9px;
            padding: 1px 7px 0 7px; font-family: "{fam[800]}"; font-size: 13px; font-weight: 800;
        }}
        QToolTip {{
            color: #FFFFFF; background: {INK}; border: 2px solid {YELLOW};
            padding: 6px 8px; font-family: "Segoe UI"; font-size: 13px;
        }}
        QComboBox, QLineEdit, QAbstractSpinBox {{ {field} }}
        QComboBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {{ background: {HOVER}; }}
        QComboBox:focus, QLineEdit:focus, QAbstractSpinBox:focus {{ background: #FFFDF2; border-color: {INK}; }}
        QComboBox:disabled, QLineEdit:disabled, QAbstractSpinBox:disabled {{
            color: #9A9486; border-color: #B8B2A4; background: #F4F0E4;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding; subcontrol-position: center right; width: 34px; border: none;
        }}
        QComboBox::down-arrow {{ image: url("{chevron}"); width: 18px; height: 18px; }}
        QComboBox QAbstractItemView {{
            background: #FFFFFF; color: {INK}; border: 2px solid {INK}; outline: 0; padding: 4px;
            font-family: "Segoe UI"; font-size: 15px;
            selection-background-color: {YELLOW}; selection-color: {INK};
        }}
        QComboBox QAbstractItemView::item {{ min-height: 34px; padding: 0 10px; border-radius: 8px; }}
        QComboBox QAbstractItemView::item:hover {{ background: {OPTION_ACTIVE}; color: {INK}; }}
        QComboBox QAbstractItemView::item:selected {{ background: {YELLOW}; color: {INK}; }}
        QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
        QLineEdit#comicKey {{ font-family: "{fam[800]}"; font-size: 17px; font-weight: 800; padding: 0 10px; }}
        QDoubleSpinBox#comicChip {{
            background: {TINT}; border-radius: 14px; padding: 0 8px; font-size: 18px;
        }}
        QDoubleSpinBox#comicChip:hover {{ background: #FFEDAE; }}
        QPushButton {{
            background: #FFFFFF; color: {INK};
            border: 2px solid {INK}; border-bottom: 5px solid {INK}; border-radius: 12px;
            padding: 5px 16px 3px 16px; min-height: 28px;
            font-family: "{fam[700]}"; font-size: 15px; font-weight: 700;
        }}
        QPushButton:hover {{ background: {HOVER}; }}
        QPushButton:pressed {{ border-bottom-width: 2px; padding-top: 8px; }}
        QPushButton:focus {{ background: #FFFDF2; }}
        QPushButton:disabled {{ color: #9A9486; border-color: #B8B2A4; }}
        QPushButton#comicPrimary {{ background: {YELLOW}; }}
        QPushButton#comicPrimary:hover {{ background: {YELLOW_HOVER}; }}
        QPushButton#comicPrimary:disabled {{ background: #F4F0E4; }}
        QPushButton#comicLink {{
            background: transparent; border: none; padding: 0; min-height: 0;
            font-family: "Segoe UI"; font-size: 13px; font-weight: 400; color: {LABEL};
            text-decoration: underline;
        }}
        QPushButton#comicLink:hover {{ color: {INK}; }}
        QCheckBox {{ color: {INK}; font-family: "Segoe UI"; font-size: 14px; spacing: 10px; }}
        QCheckBox::indicator {{
            width: 18px; height: 18px; border: 2px solid {INK}; border-radius: 6px; background: #FFFFFF;
        }}
        QCheckBox::indicator:hover {{ background: {HOVER}; }}
        QCheckBox::indicator:checked {{ background: {YELLOW}; image: url("{check}"); }}
        QProgressBar {{
            background: {TRACK}; border: 2px solid {INK}; border-radius: 8px;
            min-height: 12px; max-height: 12px; color: transparent;
        }}
        QProgressBar::chunk {{ background: {YELLOW}; border-radius: 6px; }}
        QProgressDialog {{ min-width: 440px; }}
        QProgressDialog QLabel {{ font-family: "{fam[700]}"; font-size: 16px; font-weight: 700; }}
        QLabel#qt_msgbox_label {{ font-family: "{fam[700]}"; font-size: 18px; font-weight: 700; }}
        QLabel#qt_msgbox_informativelabel {{ color: {LABEL}; font-family: "Segoe UI"; font-size: 16px; }}
        QWizardPage QLabel {{ font-family: "Segoe UI"; font-size: 16px; }}
        QTextEdit, QPlainTextEdit {{
            background: #FFFFFF; color: {INK}; border: 2px solid {INK}; border-radius: 12px;
            padding: 4px; font-family: "Segoe UI"; font-size: 16px;
        }}
        QTableView {{
            background: #FFFFFF; color: {INK}; border: none; gridline-color: {TRACK}; outline: 0;
            font-family: "Segoe UI"; font-size: 14px;
            selection-background-color: {YELLOW}; selection-color: {INK};
        }}
        QTableView::item {{ padding: 0 8px; border-bottom: 1px solid {TRACK}; }}
        QTableView::item:hover {{ background: {HOVER}; }}
        QTableView::item:selected {{ background: {YELLOW}; color: {INK}; }}
        QHeaderView::section {{
            background: #FFFFFF; color: {LABEL}; border: none; border-bottom: 2px solid {INK};
            padding: 4px 8px 5px 8px; font-family: "{fam[700]}"; font-size: 15px; font-weight: 700;
        }}
        QTableCornerButton::section {{ background: #FFFFFF; border: none; }}
        QScrollBar:vertical {{ background: {TRACK}; width: 14px; border: none; border-radius: 7px; margin: 0; }}
        QScrollBar:horizontal {{ background: {TRACK}; height: 14px; border: none; border-radius: 7px; margin: 0; }}
        QScrollBar::handle:vertical {{
            background: {YELLOW}; border: 2px solid {INK}; border-radius: 7px; min-height: 36px;
        }}
        QScrollBar::handle:horizontal {{
            background: {YELLOW}; border: 2px solid {INK}; border-radius: 7px; min-width: 36px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; background: none; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    """


def _rounded_path(rect: QRectF, tl: float, tr: float, br: float, bl: float) -> QPainterPath:
    path = QPainterPath()
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    path.moveTo(x + tl, y)
    path.lineTo(x + w - tr, y)
    path.arcTo(QRectF(x + w - 2 * tr, y, 2 * tr, 2 * tr), 90, -90)
    path.lineTo(x + w, y + h - br)
    path.arcTo(QRectF(x + w - 2 * br, y + h - 2 * br, 2 * br, 2 * br), 0, -90)
    path.lineTo(x + bl, y + h)
    path.arcTo(QRectF(x, y + h - 2 * bl, 2 * bl, 2 * bl), 270, -90)
    path.lineTo(x, y + tl)
    path.arcTo(QRectF(x, y, 2 * tl, 2 * tl), 180, -90)
    path.closeSubpath()
    return path


class DarkHeader(QWidget):
    LINE = 4

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(INK))
        p.fillRect(0, self.height() - self.LINE, self.width(), self.LINE, QColor(YELLOW))


class DotBackground(QWidget):
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(CREAM))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        dot = QColor(INK)
        dot.setAlphaF(0.035)
        p.setBrush(dot)
        for y in range(7, self.height(), 14):
            for x in range(7, self.width(), 14):
                p.drawEllipse(QPointF(x, y), 0.9, 0.9)


class BubbleTab(QAbstractButton):
    PILL = 44
    LIFT = 2
    TAIL = 13

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setFont(baloo(700, 16))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = QFontMetrics(self.font()).horizontalAdvance(self.text()) + 46
        return QSize(width, self.LIFT + self.PILL + self.TAIL)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        hovered = self.underMouse() and not self.isChecked()
        top = 0 if hovered else self.LIFT
        pill = QRectF(0, top, w, self.PILL)
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(YELLOW))
            p.drawPath(_rounded_path(pill, 20, 20, 4, 4))
            cx = w / 2
            base = top + self.PILL - 1
            tail = QPainterPath()
            tail.moveTo(cx - 11, base)
            tail.lineTo(cx - 2, self.height() - 1.5)
            tail.quadTo(cx, self.height(), cx + 2, self.height() - 1.5)
            tail.lineTo(cx + 11, base)
            tail.closeSubpath()
            p.drawPath(tail)
            text_color = QColor(INK)
        else:
            border = QColor("#FFFFFF")
            border.setAlphaF(0.7 if hovered else 0.22)
            if hovered:
                fill = QColor("#FFFFFF")
                fill.setAlphaF(0.12)
                p.setBrush(fill)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(border, 3))
            p.drawRoundedRect(pill.adjusted(1.5, 1.5, -1.5, -1.5), 19, 19)
            text_color = QColor("#FFFFFF")
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(YELLOW), 2, Qt.PenStyle.DashLine))
            p.drawRoundedRect(pill.adjusted(4, 4, -4, -4), 15, 15)
        p.setPen(text_color)
        p.setFont(self.font())
        p.drawText(pill.adjusted(0, 1, 0, 0), Qt.AlignmentFlag.AlignCenter, self.text())


class ToggleSwitch(QAbstractButton):
    TRACK_W = 52
    TRACK_H = 28
    KNOB = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._pos = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.TRACK_W + 8, self.TRACK_H + 9)

    def _set_pos(self, value) -> None:
        self._pos = float(value)
        self.update()

    def _animate(self, checked: bool) -> None:
        end = 1.0 if checked else 0.0
        if not self.isVisible():
            self._set_pos(end)
            return
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(end)
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        track = QRectF(4, 3, self.TRACK_W, self.TRACK_H)
        radius = self.TRACK_H / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRoundedRect(track.translated(0, 3), radius, radius)
        off, on = QColor(TRACK), QColor(YELLOW)
        t = max(0.0, min(1.0, self._pos))
        fill = QColor(
            round(off.red() + (on.red() - off.red()) * t),
            round(off.green() + (on.green() - off.green()) * t),
            round(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setBrush(fill)
        p.setPen(QPen(QColor(INK), 2))
        p.drawRoundedRect(track.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        travel = self.TRACK_W - self.KNOB - 8
        knob = QRectF(track.x() + 4 + travel * self._pos, track.y() + (self.TRACK_H - self.KNOB) / 2,
                      self.KNOB, self.KNOB)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(INK), 2))
        p.drawEllipse(knob)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(INK), 1.5, Qt.PenStyle.DashLine))
            p.drawRoundedRect(QRectF(1, 0.5, self.TRACK_W + 6, self.TRACK_H + 8), radius + 3, radius + 3)


class ComicSlider(QSlider):
    KNOB = 30
    TRACK = 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setMinimumHeight(self.KNOB + 8)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._grab = 0.0

    def _span(self) -> float:
        return max(1.0, self.width() - self.KNOB)

    def _knob_x(self) -> float:
        rng = self.maximum() - self.minimum()
        return (self.value() - self.minimum()) / rng * self._span() if rng else 0.0

    def _value_at(self, x: float) -> int:
        t = max(0.0, min(1.0, (x - self.KNOB / 2) / self._span()))
        return round(self.minimum() + t * (self.maximum() - self.minimum()))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        x = event.position().x()
        knob_x = self._knob_x()
        self.setSliderDown(True)
        if knob_x <= x <= knob_x + self.KNOB:
            self._grab = x - (knob_x + self.KNOB / 2)
        else:
            self._grab = 0.0
            self.setValue(self._value_at(x))
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.isSliderDown():
            self.setValue(self._value_at(event.position().x() - self._grab))
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self.isSliderDown():
            self.setSliderDown(False)
            event.accept()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        cy = (self.height() - 3) / 2
        track = QRectF(self.KNOB / 2 - 8, cy - self.TRACK / 2, self.width() - self.KNOB + 16, self.TRACK)
        radius = self.TRACK / 2 - 1
        p.setPen(QPen(QColor(INK), 2))
        p.setBrush(QColor(TRACK))
        p.drawRoundedRect(track.adjusted(1, 1, -1, -1), radius, radius)
        kx = self._knob_x()
        filled = QRectF(track.x(), track.y(), kx + self.KNOB / 2 - track.x(), self.TRACK)
        p.setBrush(QColor(YELLOW))
        p.drawRoundedRect(filled.adjusted(1, 1, -1, -1), radius, radius)
        knob = QRectF(kx, cy - self.KNOB / 2, self.KNOB, self.KNOB)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawEllipse(knob.translated(0, 3))
        p.setBrush(QColor(YELLOW_HOVER if self.underMouse() or self.isSliderDown() else YELLOW))
        p.setPen(QPen(QColor(INK), 3))
        p.drawEllipse(knob.adjusted(1.5, 1.5, -1.5, -1.5))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(INK), 1.5, Qt.PenStyle.DashLine))
            p.drawEllipse(knob.adjusted(-3, -3, 3, 3))


class _DottedRule(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(2)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(INK)
        color.setAlphaF(0.18)
        pen = QPen(color, 2, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([0.01, 2.0])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(1, 1), QPointF(self.width() - 1, 1))


def _row_controls(control) -> list[QWidget]:
    if isinstance(control, QWidget):
        return [control]
    found = []
    for index in range(control.count()):
        item = control.itemAt(index)
        if item.widget() is not None and not isinstance(item.widget(), QLabel):
            found.append(item.widget())
        elif item.layout() is not None:
            found.extend(_row_controls(item.layout()))
    return found


class ComicCard(QWidget):
    BORDER = 3
    SHADOW = 5
    LABEL_W = 270

    def __init__(self, title: str, mascot=None, parent: QWidget | None = None, row_padding: int = 9) -> None:
        super().__init__(parent)
        self._row_padding = row_padding
        outer = QVBoxLayout(self)
        b, s = self.BORDER, self.SHADOW
        outer.setContentsMargins(b + 24, b + 14, b + s + 24, b + s + 8)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(12)
        if mascot is not None:
            icon = QLabel()
            icon.setPixmap(mascot)
            head.addWidget(icon)
        title_label = QLabel(title)
        title_label.setFont(baloo(800, 26))
        head.addWidget(title_label)
        head.addStretch()
        outer.addLayout(head)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        outer.addLayout(self._rows)
        self._row_count = 0

    def add_row(self, label: str, sub: str, control) -> QWidget:
        if self._row_count:
            self._rows.addWidget(_DottedRule())
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, self._row_padding, 0, self._row_padding)
        lay.setSpacing(20)
        text = QVBoxLayout()
        text.setSpacing(2)
        head = QLabel(label)
        head.setFont(baloo(700, 17))
        head.setStyleSheet(f"color: {LABEL};")
        text.addWidget(head)
        if sub:
            sub_label = QLabel(sub)
            sub_label.setObjectName("comicSub")
            sub_label.setWordWrap(True)
            text.addWidget(sub_label)
        text.addStretch()
        holder = QWidget()
        holder.setFixedWidth(self.LABEL_W)
        holder.setLayout(text)
        lay.addWidget(holder, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        if isinstance(control, QWidget):
            fixed = control.maximumWidth() < 16777215 or (
                control.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
            )
            lay.addWidget(control, 0 if fixed else 1, Qt.AlignmentFlag.AlignVCenter)
            if fixed:
                lay.addStretch(1)
        else:
            lay.addLayout(control, 1)
        for widget in _row_controls(control):
            if not widget.accessibleName():
                widget.setAccessibleName(label)
            if sub and not widget.accessibleDescription():
                widget.setAccessibleDescription(sub)
        self._rows.addWidget(row)
        self._row_count += 1
        return row

    def add_note(self, widget: QWidget) -> None:
        self._rows.addWidget(widget)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b, s = self.BORDER, self.SHADOW
        body = QRectF(b / 2, b / 2, self.width() - s - b, self.height() - s - b)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRoundedRect(body.translated(s, s), 16, 16)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(INK), b))
        p.drawRoundedRect(body, 16, 16)


class Keycap(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFont(baloo(800, 15))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(32)
        self.setStyleSheet(
            f"background: #FFFFFF; color: {INK}; border: 2px solid {INK}; border-bottom: 5px solid {INK};"
            " border-radius: 8px; padding: 2px 8px 0 8px;"
        )


class HintBubble(QWidget):
    TAIL = 10

    def __init__(self, parts, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 14 + self.TAIL, 20, 14)
        lay.setSpacing(8)
        for part in parts:
            if isinstance(part, QWidget):
                lay.addWidget(part, 0, Qt.AlignmentFlag.AlignVCenter)
            else:
                label = QLabel(part)
                label.setFont(baloo(600, 16))
                label.setWordWrap(len(parts) == 1)
                lay.addWidget(label, 1 if len(parts) == 1 else 0, Qt.AlignmentFlag.AlignVCenter)
        if len(parts) > 1:
            lay.addStretch()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(1, self.TAIL + 1, self.width() - 2, self.height() - self.TAIL - 2)
        shape = QPainterPath()
        shape.addRoundedRect(body, 18, 18)
        tail = QPainterPath()
        tail.moveTo(30, self.TAIL + 2)
        tail.lineTo(40, 1.5)
        tail.lineTo(50, self.TAIL + 2)
        tail.closeSubpath()
        p.setBrush(QColor(TINT))
        p.setPen(QPen(QColor(INK), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(shape.united(tail).simplified())


class Wordmark(QWidget):
    def __init__(self, variant: str = "dunkel", height: int = 54, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(str(assets_dir() / "brand" / f"speech2anywhere-wortmarke-{variant}.svg"))
        box = self._renderer.viewBoxF()
        ratio = box.width() / box.height() if self._renderer.isValid() and box.height() else 5.7
        self.setFixedSize(round(height * ratio), height)

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._renderer.isValid():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(p, QRectF(0, 0, self.width(), self.height()))


def dialog_header(title: str) -> DarkHeader:
    header = DarkHeader()
    lay = QVBoxLayout(header)
    lay.setContentsMargins(28, 14, 28, 0)
    lay.setSpacing(12)
    top = QHBoxLayout()
    top.setSpacing(16)
    logo = QLabel()
    pix = mascot_pixmap(64)
    if pix is not None:
        logo.setPixmap(pix)
    top.addWidget(logo)
    top.addWidget(Wordmark("dunkel", 54), 0, Qt.AlignmentFlag.AlignVCenter)
    top.addStretch()
    lay.addLayout(top)
    tab = BubbleTab(title)
    tab.setChecked(True)
    tab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    tab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    QButtonGroup(header).addButton(tab)
    tabs = QHBoxLayout()
    tabs.addWidget(tab, 0, Qt.AlignmentFlag.AlignBottom)
    tabs.addStretch()
    lay.addLayout(tabs)
    return header


def dialog_frame(dialog: QWidget, title: str) -> QVBoxLayout:
    root = QVBoxLayout(dialog)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(dialog_header(title))
    body = DotBackground()
    lay = QVBoxLayout(body)
    lay.setContentsMargins(30, 26, 30, 18)
    lay.setSpacing(16)
    root.addWidget(body, 1)
    return lay


def footer_row(left: str | QWidget | None, *buttons: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    if isinstance(left, str):
        note = QLabel(left)
        note.setObjectName("comicNote")
        row.addWidget(note)
    elif left is not None:
        row.addWidget(left)
    row.addStretch()
    for button in buttons:
        row.addWidget(button)
    return row


class ComicMenu(QMenu):
    SHADOW = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        border_off_on_show(self)
        fam = load_fonts()
        s = self.SHADOW
        self.setStyleSheet(f"""
            QMenu {{ background: transparent; border: none; padding: 3px {3 + s}px {7 + s}px 3px; }}
            QMenu::item {{
                color: {INK}; padding: 7px 24px 7px 14px; margin: 1px 6px; border-radius: 10px;
                font-family: "{fam[700]}"; font-size: 15px; font-weight: 700;
            }}
            QMenu::item:selected {{ background: {YELLOW}; }}
            QMenu::item:disabled {{
                color: {LABEL}; font-family: "Segoe UI"; font-size: 13px; font-weight: 400;
            }}
            QMenu::separator {{ height: 2px; background: {TRACK}; margin: 5px 16px; }}
        """)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.SHADOW
        body = QRectF(1.5, 1.5, self.width() - s - 3, self.height() - s - 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRoundedRect(body.translated(s, s), 16, 16)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(INK), 3))
        p.drawRoundedRect(body, 16, 16)
        p.end()
        super().paintEvent(event)


class _MenuHeader(QWidget):
    LINE = 4

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        p.fillPath(_rounded_path(rect, 13, 13, 0, 0), QColor(INK))
        p.fillRect(QRectF(0, rect.height() - self.LINE, rect.width(), self.LINE), QColor(YELLOW))


def menu_header(parent: QWidget) -> QWidgetAction:
    head = _MenuHeader()
    lay = QHBoxLayout(head)
    lay.setContentsMargins(14, 10, 16, 10 + _MenuHeader.LINE)
    lay.setSpacing(10)
    logo = QLabel()
    pix = mascot_pixmap(36)
    if pix is not None:
        logo.setPixmap(pix)
    lay.addWidget(logo)
    lay.addWidget(Wordmark("dunkel", 28), 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addStretch()
    holder = QWidget()
    outer = QVBoxLayout(holder)
    outer.setContentsMargins(0, 0, 0, 6)
    outer.addWidget(head)
    action = QWidgetAction(parent)
    action.setDefaultWidget(holder)
    return action
