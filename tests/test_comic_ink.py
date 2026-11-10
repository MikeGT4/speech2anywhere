# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QColor, QFocusEvent, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout

from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme


def _dialog(qtbot, *buttons):
    dialog = QDialog()
    lay = QVBoxLayout(dialog)
    for button in buttons:
        lay.addWidget(button)
    apply_light_theme(dialog)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    return dialog


def test_comic_buttons_are_painted_by_the_ink_painter(qtbot, monkeypatch):
    painted = []
    monkeypatch.setattr(comic, "paint_button", lambda button: painted.append(button.text()))
    plain, link, flat = QPushButton("Aktualisieren"), QPushButton("Mehr"), QPushButton("Flach")
    link.setObjectName("comicLink")
    flat.setFlat(True)
    dialog = _dialog(qtbot, plain, link, flat)
    dialog.grab()
    assert "Aktualisieren" in painted
    assert "Mehr" not in painted and "Flach" not in painted


def test_buttons_outside_comic_windows_keep_the_qt_painting(qtbot, monkeypatch):
    _dialog(qtbot, QPushButton("Speichern"))
    painted = []
    monkeypatch.setattr(comic, "paint_button", lambda button: painted.append(button.text()))
    other = QDialog()
    QPushButton("Fremd", other)
    qtbot.addWidget(other)
    other.grab()
    assert painted == []


def test_button_faces_follow_the_comic_states(qtbot):
    normal, primary, idle = QPushButton("Abbrechen"), QPushButton("Speichern"), QPushButton("Weiter")
    primary.setObjectName("comicPrimary")
    idle.setObjectName("comicPrimary")
    idle.setEnabled(False)
    dialog = _dialog(qtbot, normal, primary, idle)
    assert dialog.isVisible()
    for button, face in ((normal, "#ffffff"), (primary, comic.YELLOW.lower()), (idle, "#f4f0e4")):
        image = button.grab().toImage()
        assert image.pixelColor(6, image.height() // 2).name() == face


def test_pressed_button_sinks_onto_its_ink(qtbot):
    button = QPushButton("Laden…")
    dialog = _dialog(qtbot, button)
    assert dialog.isVisible()
    ink = comic.INK.lower()
    image = button.grab().toImage()
    h = image.height()
    assert [image.pixelColor(14, h - k).name() for k in (1, 5, 6)] == [ink, ink, "#ffffff"]
    button.setDown(True)
    image = button.grab().toImage()
    assert [image.pixelColor(14, h - k).name() for k in (1, 2, 3)] == [ink, ink, "#ffffff"]


def test_mnemonics_are_hidden_like_qt_does():
    assert comic.button_label("&OK") == "OK"
    assert comic.button_label("Ja && Nein") == "Ja & Nein"


def test_draw_text_sits_centred_in_its_box(qtbot):
    image = QImage(220, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("#FFFFFF"))
    p = QPainter(image)
    comic.draw_text(p, QRectF(10, 20, 200, 30), "Speichern", comic.baloo(700, 15), QColor(comic.INK))
    p.end()
    ink = [(x, y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y).lightness() < 128]
    xs, ys = [x for x, _ in ink], [y for _, y in ink]
    assert abs((min(xs) + max(xs)) / 2 - 110) < 2
    assert 20 <= min(ys) and max(ys) <= 50


def test_keyboard_focus_is_told_apart_from_mouse_focus(qtbot):
    first, second = QPushButton("Abbrechen"), QPushButton("Speichern")
    dialog = _dialog(qtbot, first, second)
    assert dialog.isVisible()
    dialog.setAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange)
    QApplication.sendEvent(second, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
    QApplication.sendEvent(first, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))
    assert second.property("comicKeyFocus") is True
    assert first.property("comicKeyFocus") is False
    QApplication.sendEvent(second, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason))
    assert second.property("comicKeyFocus") is False


def test_ink_label_keeps_the_size_of_a_label(qtbot):
    ink, plain = comic.InkLabel("Schneller Modus"), QLabel("Schneller Modus")
    for label in (ink, plain):
        label.setFont(comic.baloo(700, 17))
        qtbot.addWidget(label)
    assert ink.sizeHint() == plain.sizeHint()
    image = ink.grab().toImage()
    assert any(image.pixelColor(x, image.height() // 2).lightness() < 128 for x in range(image.width()))


def test_card_title_and_row_heads_are_ink_labels(qtbot):
    card = comic.ComicCard("Politur")
    card.add_row("Modell", "Setzt Satzzeichen.", QLineEdit())
    qtbot.addWidget(card)
    assert [label.text() for label in card.findChildren(comic.InkLabel)] == ["Politur", "Modell"]


def test_fields_get_the_ink_frame_but_not_their_inner_line_edit(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QDoubleSpinBox
    painted = []
    monkeypatch.setattr(comic, "paint_field", lambda field: painted.append(type(field).__name__))
    dialog = _dialog(qtbot, QLineEdit("gemma4:12b"), QDoubleSpinBox())
    dialog.grab()
    assert painted.count("QLineEdit") == 1
    assert "QDoubleSpinBox" in painted


def test_field_faces_follow_the_comic_states(qtbot):
    normal, idle = QLineEdit("gemma4:12b"), QLineEdit("gemma4:e4b")
    idle.setEnabled(False)
    dialog = _dialog(qtbot, normal, idle)
    assert dialog.isVisible()
    ink = comic.INK.lower()
    for field, face in ((normal, "#ffffff"), (idle, "#f4f0e4")):
        image = field.grab().toImage()
        h = image.height()
        assert image.pixelColor(6, h // 2).name() == face
    image = normal.grab().toImage()
    h = image.height()
    assert [image.pixelColor(14, h - k).name() for k in (1, 5, 6)] == [ink, ink, "#ffffff"]


def test_radio_buttons_get_comic_ink_instead_of_the_system_colours():
    import re
    rule = re.search(r"QRadioButton \{(.*?)\}", comic.dialog_qss(), re.S)
    assert rule and f"color: {comic.INK}" in rule.group(1)
    assert "QRadioButton::indicator:checked" in comic.dialog_qss()
