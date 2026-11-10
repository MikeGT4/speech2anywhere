# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import ctypes
import functools
import logging
import sys

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QEasingCurve, QEvent, QObject, QPointF, QRectF, QSize, Qt, QUrl, QVariantAnimation
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QFontDatabase, QFontMetrics, QFontMetricsF, QIcon, QPainter, QPainterPath, QPalette,
    QPen, QPixmap, QPolygonF,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QAbstractButton, QAbstractSpinBox, QApplication, QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QProxyStyle, QPushButton, QSizePolicy, QSlider, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget, QWidgetAction,
)

from kira._resources import assets_dir
from kira.texte import tr
from kira.ui import update_badge

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
    return smooth_font(font)


def smooth_font(font: QFont) -> QFont:
    font.setStyleStrategy(QFont.StyleStrategy.NoSubpixelAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
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
        self.setAccessibleName(tr("digitalroots, Webseite öffnen"))

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


def credit_row() -> QWidget:
    credit = QWidget()
    row = QHBoxLayout(credit)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    note = QLabel("© 2026 Mike Pollow")
    note.setObjectName("comicNote")
    note.setStyleSheet(f"color: {LABEL}; font-family: 'Segoe UI'; font-size: 13px; font-weight: 400;")
    row.addWidget(note)
    row.addWidget(brand_logo(16))
    return credit


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
        background: transparent; color: {INK};
        border: 2px solid transparent; border-bottom: 5px solid transparent; border-radius: 12px;
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
        QComboBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {{ background: transparent; }}
        QComboBox:disabled, QLineEdit:disabled, QAbstractSpinBox:disabled {{ color: #9A9486; }}
        QComboBox::drop-down {{
            subcontrol-origin: padding; subcontrol-position: center right; width: 34px; border: none;
        }}
        QComboBox QLineEdit {{ padding: 0; min-height: 0; border: none; background: transparent; }}
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
            background: transparent; border-radius: 14px; padding: 0 8px; font-size: 18px;
        }}
        QDoubleSpinBox#comicChip:hover {{ background: transparent; }}
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
        QRadioButton {{ color: {INK}; font-family: "Segoe UI"; font-size: 14px; spacing: 10px; }}
        QRadioButton::indicator {{
            width: 18px; height: 18px; border: 2px solid {INK}; border-radius: 11px; background: #FFFFFF;
        }}
        QRadioButton::indicator:hover {{ background: {HOVER}; }}
        QRadioButton::indicator:checked {{
            background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.5, fx: 0.5, fy: 0.5,
                stop: 0 {INK}, stop: 0.4 {INK}, stop: 0.5 {YELLOW}, stop: 1 {YELLOW});
        }}
        QRadioButton:disabled {{ color: #9A9486; }}
        QRadioButton::indicator:disabled {{ border-color: #B8B2A4; background: #F4F0E4; }}
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


def draw_text(p: QPainter, rect: QRectF, text: str, font: QFont, color: QColor,
              align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter) -> None:
    p.setFont(font)
    p.setPen(color)
    p.drawText(rect, int(align), text)


def button_label(text: str) -> str:
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


class InkLabel(QLabel):
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        margin = self.margin()
        rect = QRectF(self.contentsRect()).adjusted(margin, margin, -margin, -margin)
        draw_text(p, rect, self.text(), self.font(), self.palette().color(group, self.foregroundRole()), self.alignment())
        p.end()


_INK_WINDOW = "comicInk"
_INK_EVENTS = frozenset((QEvent.Type.Paint, QEvent.Type.FocusIn, QEvent.Type.FocusOut))
_KEYBOARD_REASONS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)


def _button_face(rect: QRectF, radius: float, bottom_ry: float) -> QPainterPath:
    x0, y0, x1, y1, r = rect.left(), rect.top(), rect.right(), rect.bottom(), radius
    path = QPainterPath()
    path.moveTo(x0 + r, y0)
    path.lineTo(x1 - r, y0)
    path.arcTo(QRectF(x1 - 2 * r, y0, 2 * r, 2 * r), 90, -90)
    path.lineTo(x1, y1 - bottom_ry)
    path.arcTo(QRectF(x1 - 2 * r, y1 - 2 * bottom_ry, 2 * r, 2 * bottom_ry), 0, -90)
    path.lineTo(x0 + r, y1)
    path.arcTo(QRectF(x0, y1 - 2 * bottom_ry, 2 * r, 2 * bottom_ry), 270, -90)
    path.lineTo(x0, y0 + r)
    path.arcTo(QRectF(x0, y0, 2 * r, 2 * r), 180, -90)
    path.closeSubpath()
    return path


def _button_face_color(button: QPushButton) -> str:
    enabled = button.isEnabled()
    hovered = enabled and button.underMouse()
    if button.objectName() == "comicPrimary":
        if not enabled:
            return "#F4F0E4"
        return YELLOW_HOVER if hovered else YELLOW
    if enabled and button.hasFocus():
        return "#FFFDF2"
    return HOVER if hovered else "#FFFFFF"


def paint_button(button: QPushButton) -> None:
    enabled = button.isEnabled()
    down = button.isDown()
    bottom = 2.0 if down else 5.0
    rect = QRectF(button.rect())
    face = rect.adjusted(2, 2, -2, -bottom)
    p = QPainter(button)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline = QPainterPath()
    outline.addRoundedRect(rect, 12, 12)
    p.fillPath(outline, QColor(INK if enabled else "#B8B2A4"))
    p.fillPath(_button_face(face, 10, 12 - bottom), QColor(_button_face_color(button)))
    if button.hasFocus() and button.property("comicKeyFocus"):
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(INK), 2, Qt.PenStyle.DashLine))
        p.drawPath(_button_face(face.adjusted(3, 3, -3, -3), 7, 9 - bottom))
    box = face.adjusted(16, 8 if down else 5, -16, -3)
    draw_text(p, box, button_label(button.text()), button.font(), QColor(INK if enabled else "#9A9486"))
    p.end()


def _field_face_color(field: QWidget) -> str:
    hovered = field.isEnabled() and field.underMouse()
    if field.objectName() == "comicChip":
        return "#FFEDAE" if hovered else TINT
    if not field.isEnabled():
        return "#F4F0E4"
    if field.hasFocus():
        return "#FFFDF2"
    return HOVER if hovered else "#FFFFFF"


def paint_field(field: QWidget) -> None:
    radius = 14.0 if field.objectName() == "comicChip" else 12.0
    rect = QRectF(field.rect())
    p = QPainter(field)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline = QPainterPath()
    outline.addRoundedRect(rect, radius, radius)
    p.fillPath(outline, QColor(INK if field.isEnabled() else "#B8B2A4"))
    p.fillPath(_button_face(rect.adjusted(2, 2, -2, -5), radius - 2, radius - 5), QColor(_field_face_color(field)))
    p.end()


_FIELD_TYPES = (QLineEdit, QComboBox, QAbstractSpinBox)


def _paints_field(field: QWidget) -> bool:
    return bool(field.window().property(_INK_WINDOW)) and not isinstance(
        field.parentWidget(), (QComboBox, QAbstractSpinBox),
    )


def _paints_button(button: QPushButton) -> bool:
    return (
        bool(button.window().property(_INK_WINDOW))
        and not button.isFlat()
        and button.objectName() != "comicLink"
        and button.icon().isNull()
        and button.menu() is None
        and not button.styleSheet()
    )


class _InkPainter(QObject):
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        kind = event.type()
        if kind not in _INK_EVENTS:
            return False
        if type(obj) is not QPushButton:
            if kind == QEvent.Type.Paint and isinstance(obj, _FIELD_TYPES) and _paints_field(obj):
                paint_field(obj)
            return False
        if kind == QEvent.Type.Paint:
            if _paints_button(obj):
                paint_button(obj)
                return True
            return False
        obj.setProperty(
            "comicKeyFocus",
            kind == QEvent.Type.FocusIn and event.reason() in _KEYBOARD_REASONS
            and obj.window().testAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange),
        )
        return False


def ink_buttons(window: QWidget) -> None:
    window.setProperty(_INK_WINDOW, True)
    app = QApplication.instance()
    if app is not None and app.findChild(_InkPainter, "comicInkPainter") is None:
        painter = _InkPainter(app)
        painter.setObjectName("comicInkPainter")
        app.installEventFilter(painter)


class DarkHeader(QWidget):
    LINE = 4

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(INK))
        p.fillRect(0, self.height() - self.LINE, self.width(), self.LINE, QColor(YELLOW))


class DotBackground(QWidget):
    GRID = 14
    _tiles: dict[float, QPixmap] = {}

    @classmethod
    def _tile(cls, ratio: float) -> QPixmap:
        tile = cls._tiles.get(ratio)
        if tile is None:
            tile = QPixmap(round(cls.GRID * ratio), round(cls.GRID * ratio))
            tile.setDevicePixelRatio(ratio)
            tile.fill(QColor(CREAM))
            p = QPainter(tile)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            dot = QColor(INK)
            dot.setAlphaF(0.035)
            p.setBrush(dot)
            p.drawEllipse(QPointF(cls.GRID / 2, cls.GRID / 2), 0.9, 0.9)
            p.end()
            cls._tiles[ratio] = tile
        return tile

    def paintEvent(self, event) -> None:  # noqa: N802
        area = event.rect()
        p = QPainter(self)
        p.drawTiledPixmap(QRectF(area), self._tile(self.devicePixelRatioF()),
                          QPointF(area.x() % self.GRID, area.y() % self.GRID))


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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._keyboard_focus = False

    def sizeHint(self) -> QSize:  # noqa: N802
        width = QFontMetrics(self.font()).horizontalAdvance(self.text()) + 46
        return QSize(width, self.LIFT + self.PILL + self.TAIL)

    def focusInEvent(self, event) -> None:  # noqa: N802
        self._keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
        ) and self.window().testAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._keyboard_focus = False
        super().focusOutEvent(event)

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
        if self.hasFocus() and self._keyboard_focus:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(INK if self.isChecked() else YELLOW), 2, Qt.PenStyle.DashLine))
            p.drawRoundedRect(pill.adjusted(4, 4, -4, -4), 15, 15)
        draw_text(p, pill.adjusted(0, 1, 0, 0), self.text(), self.font(), text_color)


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


class _ToggleOnLabelClick(QObject):
    def __init__(self, switch: QAbstractButton, parent: QObject) -> None:
        super().__init__(parent)
        self._switch = switch

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._switch.isEnabled()
            and watched.rect().contains(event.position().toPoint())
        ):
            self._switch.toggle()
            return True
        return False


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
        title_label = InkLabel(title)
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
        head = InkLabel(label)
        head.setFont(baloo(700, 17))
        head.setStyleSheet(f"color: {LABEL};")
        text.addWidget(head)
        labels = [head]
        if sub:
            sub_label = QLabel(sub)
            sub_label.setObjectName("comicSub")
            sub_label.setWordWrap(True)
            text.addWidget(sub_label)
            labels.append(sub_label)
        if isinstance(control, ToggleSwitch):
            clicker = _ToggleOnLabelClick(control, row)
            for text_label in labels:
                text_label.setCursor(Qt.CursorShape.PointingHandCursor)
                text_label.installEventFilter(clicker)
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
    RADIUS = 8.0
    BOTTOM = 5.0

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFont(baloo(800, 15))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(32)
        self.setStyleSheet("background: transparent; border: none; padding: 0;")
        self.setContentsMargins(10, 4, 10, int(self.BOTTOM))

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        outline = QPainterPath()
        outline.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        p.fillPath(outline, QColor(INK))
        face = rect.adjusted(2, 2, -2, -self.BOTTOM)
        p.fillPath(_button_face(face, self.RADIUS - 2, self.RADIUS - self.BOTTOM), QColor("#FFFFFF"))
        draw_text(p, rect.adjusted(10, 4, -10, -self.BOTTOM), self.text(), self.font(), QColor(INK))
        p.end()


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


MENU_ICON = 28
DOTS = "#DED4BA"


def _menu_glyph(p: QPainter, kind: str) -> None:
    import math
    ink = QColor(INK)
    pen = QPen(ink, 2.1)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    def line(*pts):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))

    def shape(path: QPainterPath):
        p.setPen(pen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawPath(path)

    def arc(cx, cy, r, start, end):
        steps = 48
        line(*[(cx + r * math.cos(math.radians(start + (end - start) * i / steps)),
                cy + r * math.sin(math.radians(start + (end - start) * i / steps))) for i in range(steps + 1)])

    if kind == "gear":
        for i in range(8):
            a = i * math.pi / 4
            line((12 + 4.6 * math.cos(a), 12 + 4.6 * math.sin(a)), (12 + 6.6 * math.cos(a), 12 + 6.6 * math.sin(a)))
        ring = QPainterPath()
        ring.addEllipse(QRectF(7.6, 7.6, 8.8, 8.8))
        shape(ring)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        p.drawEllipse(QRectF(10.6, 10.6, 2.8, 2.8))
    elif kind == "clock":
        face = QPainterPath()
        face.addEllipse(QRectF(5.8, 5.8, 12.4, 12.4))
        shape(face)
        line((12, 8.6), (12, 12), (14.6, 13.6))
    elif kind == "wand":
        line((7, 17), (14.2, 9.8))
        line((16.6, 5.2), (16.6, 10))
        line((14.2, 7.6), (19, 7.6))
    elif kind == "book":
        for pts in (((6, 8), (11.4, 9.2), (11.4, 17.2), (6, 16)), ((18, 8), (12.6, 9.2), (12.6, 17.2), (18, 16))):
            page = QPainterPath()
            page.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
            page.closeSubpath()
            shape(page)
    elif kind in ("document", "file"):
        sheet = QPainterPath()
        sheet.addRoundedRect(QRectF(7.4, 5.8, 9.2, 12.4), 1.6, 1.6)
        shape(sheet)
        if kind == "document":
            for y in (9.6, 12.2, 14.8):
                line((9.8, y), (14.2, y))
        else:
            for x, h in ((9.9, 2.4), (12, 5.0), (14.1, 3.2)):
                line((x, 12 - h / 2), (x, 12 + h / 2))
    elif kind == "info":
        bubble = QPainterPath()
        bubble.addEllipse(QRectF(6, 5.4, 12, 12))
        shape(bubble)
        tail = QPainterPath()
        tail.addPolygon(QPolygonF([QPointF(8.9, 16.2), QPointF(7.6, 19.2), QPointF(11.4, 17.3)]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawPath(tail)
        line((8.9, 16.2), (7.6, 19.2), (11.4, 17.3))
        line((12, 10.8), (12, 14))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        p.drawEllipse(QRectF(10.9, 7.4, 2.2, 2.2))
    elif kind == "power":
        arc(12, 12.6, 5.6, -55, 235)
        line((12, 5.4), (12, 11.4))
    elif kind == "retry":
        arc(12, 12, 5.6, 20, 320)
        line((18.6, 6.2), (16.4, 8.6), (19.4, 9.6))


def _menu_icon_pixmap(kind: str, size: int, fill: str) -> QPixmap:
    scale = 3
    if kind == "update":
        badge = QPixmap.fromImage(ImageQt(update_badge.solo(size * scale)))
        badge.setDevicePixelRatio(scale)
        return badge
    pix = QPixmap(size * scale, size * scale)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * scale / 24, size * scale / 24)
    p.setPen(QPen(QColor(INK), 1.6))
    p.setBrush(QColor(fill))
    p.drawEllipse(QRectF(0.8, 0.8, 22.4, 22.4))
    _menu_glyph(p, kind)
    p.end()
    pix.setDevicePixelRatio(scale)
    return pix


@functools.lru_cache(maxsize=32)
def menu_icon(kind: str, size: int = MENU_ICON) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_menu_icon_pixmap(kind, size, YELLOW), QIcon.Mode.Normal)
    hovered = _menu_icon_pixmap(kind, size, CREAM)
    icon.addPixmap(hovered, QIcon.Mode.Active)
    icon.addPixmap(hovered, QIcon.Mode.Selected)
    return icon


class _MenuStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None) -> int:  # noqa: N802
        if metric == QStyle.PixelMetric.PM_SmallIconSize:
            return MENU_ICON
        return super().pixelMetric(metric, option, widget)


class ComicMenu(QMenu):
    SHADOW = 6
    RADIUS = 22

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        border_off_on_show(self)
        self._menu_style = _MenuStyle()
        self.setStyle(self._menu_style)
        fam = load_fonts()
        s = self.SHADOW
        self.setStyleSheet(f"""
            QMenu {{ background: transparent; border: none; padding: 3px {3 + s}px {6 + s}px 3px; }}
            QMenu::item {{
                color: {INK}; padding: 6px 28px 6px 12px; margin: 1px 8px; border-radius: 20px;
                border: 2px solid transparent;
                font-family: "{fam[700]}"; font-size: 15px; font-weight: 700;
            }}
            QMenu::item:selected {{ background: {YELLOW}; border: 2px solid {INK}; }}
            QMenu::item:disabled {{
                color: {LABEL}; font-family: "Segoe UI"; font-size: 13px; font-weight: 400;
            }}
            QMenu::icon {{ padding-left: 14px; }}
            QMenu::separator {{ height: 0px; border-top: 3px dotted {DOTS}; margin: 7px 18px; }}
        """)
        self.setContentsMargins(0, 0, s, 3 + s)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.SHADOW
        r = self.RADIUS
        body = QRectF(1.5, 1.5, self.width() - s - 3, self.height() - s - 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRoundedRect(body.translated(s, s), r, r)
        p.setBrush(QColor(CREAM))
        p.setPen(QPen(QColor(INK), 3))
        p.drawRoundedRect(body, r, r)
        p.end()
        super().paintEvent(event)


def _snap(value: float, ratio: float) -> float:
    return round(value * ratio) / ratio


STATUS_DOT = {"ready": "#2FA84F", "busy": YELLOW, "problem": RED}


class _MenuStatus(QWidget):
    MASCOT = 22
    TEXT_ROOM = 150

    def __init__(self, text: str, ready: bool) -> None:
        super().__init__()
        self._text = text
        self.tone = "ready" if ready else "problem" if text.startswith(tr("Fehler")) else "busy"
        self._mascots: dict[float, QPixmap | None] = {}
        self.setAccessibleName(text)
        self.setMinimumHeight(52)
        self._font = baloo(800, 16)
        advance = QFontMetricsF(self._font).horizontalAdvance(text)
        self.setMinimumWidth(int(min(advance, self.TEXT_ROOM)) + 10 + 2 + 12 + 22 + 10 + 34 + 2 + 10)

    def mascot(self, ratio: float) -> QPixmap | None:
        if ratio not in self._mascots:
            pix = mascot_pixmap(round(self.MASCOT * ratio))
            if pix is not None:
                pix.setDevicePixelRatio(ratio)
            self._mascots[ratio] = pix
        return self._mascots[ratio]

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(10, 6, self.width() - 20, self.height() - 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRoundedRect(card.adjusted(0, 0, 0, 2), 16, 16)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(card.adjusted(2, 2, -2, -2), 14, 14)
        x = card.left() + 14
        mid = card.top() + card.height() / 2
        ratio = self.devicePixelRatioF()
        mascot = self.mascot(ratio)
        if mascot is not None:
            p.drawPixmap(QPointF(_snap(x, ratio), _snap(mid - self.MASCOT / 2, ratio)), mascot)
        dot = QPointF(card.right() - 20, mid)
        if self.tone == "ready":
            p.setPen(QPen(QColor(47, 168, 79, 110), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(dot, 9.5, 9.5)
        p.setPen(QPen(QColor(INK), 1.6))
        p.setBrush(QColor(STATUS_DOT[self.tone]))
        p.drawEllipse(dot, 5.5, 5.5)
        room = QRectF(x + 32, card.top(), dot.x() - 16 - (x + 32), card.height())
        text = QFontMetricsF(self._font).elidedText(self._text, Qt.TextElideMode.ElideRight, room.width())
        draw_text(p, room, text, self._font, QColor(RED_TEXT if self.tone == "problem" else INK),
                  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def menu_status(parent: QWidget, text: str, ready: bool) -> QWidgetAction:
    action = QWidgetAction(parent)
    action.setDefaultWidget(_MenuStatus(text, ready))
    action.setEnabled(False)
    return action


class _MenuHeader(QWidget):
    LINE = 4

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        p.fillPath(_rounded_path(rect, ComicMenu.RADIUS - 3, ComicMenu.RADIUS - 3, 0, 0), QColor(INK))
        p.fillRect(QRectF(0, rect.height() - self.LINE, rect.width(), self.LINE), QColor(YELLOW))


def menu_header(parent: QWidget) -> QWidgetAction:
    head = _MenuHeader()
    lay = QHBoxLayout(head)
    lay.setContentsMargins(14, 10, 16, 10 + _MenuHeader.LINE)
    lay.setSpacing(11)
    logo = QLabel()
    pix = mascot_pixmap(44 * 3)
    if pix is not None:
        pix.setDevicePixelRatio(3)
        logo.setPixmap(pix)
    lay.addWidget(logo)
    lay.addWidget(Wordmark("dunkel", 30), 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addStretch()
    holder = QWidget()
    outer = QVBoxLayout(holder)
    outer.setContentsMargins(0, 0, 0, 6)
    outer.addWidget(head)
    action = QWidgetAction(parent)
    action.setDefaultWidget(holder)
    return action
