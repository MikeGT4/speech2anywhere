from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QDialog, QLabel, QMessageBox, QWidget

from kira.ui import _comic as comic

_GERMAN_BUTTONS = (
    (QMessageBox.StandardButton.Yes, "Yes", "Ja"),
    (QMessageBox.StandardButton.No, "No", "Nein"),
)
_SYMBOL_SIZE = 56


def _light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(comic.CREAM))
    p.setColor(QPalette.ColorRole.WindowText, QColor(comic.INK))
    p.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(comic.TINT))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(comic.INK))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Text, QColor(comic.INK))
    p.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(comic.INK))
    p.setColor(QPalette.ColorRole.BrightText, QColor(comic.RED_TEXT))
    p.setColor(QPalette.ColorRole.Link, QColor(comic.INK))
    p.setColor(QPalette.ColorRole.Highlight, QColor(comic.YELLOW))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(comic.INK))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9A9486"))
    return p


def _symbol(icon: QMessageBox.Icon):
    if icon in (QMessageBox.Icon.Information, QMessageBox.Icon.Question):
        return comic.mascot_pixmap(_SYMBOL_SIZE)
    if icon == QMessageBox.Icon.Warning:
        return comic.alert_pixmap("warning", _SYMBOL_SIZE)
    if icon == QMessageBox.Icon.Critical:
        return comic.alert_pixmap("critical", _SYMBOL_SIZE)
    return None


def _comic_message(box: QMessageBox) -> None:
    head, _, detail = box.text().partition("\n\n")
    if detail and not box.informativeText():
        box.setText(head)
        box.setInformativeText(detail)
    for name in ("qt_msgbox_label", "qt_msgbox_informativelabel"):
        label = box.findChild(QLabel, name)
        if label is not None:
            label.setWordWrap(True)
    symbol = _symbol(box.icon())
    if symbol is not None:
        box.setIconPixmap(symbol)
    for standard, english, german in _GERMAN_BUTTONS:
        button = box.button(standard)
        if button is not None and button.text().replace("&", "") == english:
            button.setText(german)
    default = box.defaultButton()
    if default is not None:
        default.setObjectName("comicPrimary")


def apply_light_theme(dialog: QDialog) -> None:
    dialog.setPalette(_light_palette())
    if isinstance(dialog, QMessageBox):
        _comic_message(dialog)
    dialog.setStyleSheet(comic.dialog_qss())
    comic.ink_titlebar_on_show(dialog)


def _build_message(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(QMessageBox.StandardButton.Ok)
    apply_light_theme(box)
    return box


def _show_message(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
) -> int:
    return int(_build_message(parent, icon, title, text).exec())


def light_information(parent: QWidget | None, title: str, text: str) -> int:
    return _show_message(parent, QMessageBox.Icon.Information, title, text)


def light_warning(parent: QWidget | None, title: str, text: str) -> int:
    return _show_message(parent, QMessageBox.Icon.Warning, title, text)


def light_critical(parent: QWidget | None, title: str, text: str) -> int:
    return _show_message(parent, QMessageBox.Icon.Critical, title, text)
