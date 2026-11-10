# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QWidget,
)

from kira._resources import assets_dir
from kira.lexicon import Entry
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme
from kira.texte import N_, decimal_mark, tr

log = logging.getLogger(__name__)
_ASSETS = assets_dir()
KIND_LABELS = {"replacement": N_("Ersetzung"), "glossary": N_("Glossar")}
COLUMNS = (N_("Erkannt"), N_("Richtig"), N_("Art"), N_("Anzahl"), N_("Beispiel"))
NO_SOURCES_HINT = (
    N_(
        "Keine Lernquellen eingetragen (learning.sources in der Rohconfig). "
        "Speech2Anywhere schreibt nur den Verlauf."
    )
)

_BUTTON_MIN_WIDTH = 120
_BUTTON_ROW_SPACING = 8
_TABLE_MIN_HEIGHT = 60


def format_rate(value: tuple[int, int] | None) -> str:
    if not value or value[1] == 0:
        return tr("noch keine Daten")
    corrected, matched = value
    percent = f"{corrected / matched * 100:.1f}".replace(".", decimal_mark())
    return tr("{} % ({} von {})").format(percent, corrected, matched)


class LearnedWordsDialog(QDialog):
    def __init__(self, service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle(tr("Speech2Anywhere: Gelernte Wörter"))
        icon_path = _ASSETS / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumWidth(880)
        self.setModal(True)
        apply_light_theme(self)
        body = comic.dialog_frame(self, tr("Gelernte Wörter"))

        self.metrics_label = QLabel()
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setFont(comic.baloo(600, 15))
        body.addWidget(comic.HintBubble([self.metrics_label]))

        mascot = comic.mascot_pixmap(32)
        pending = comic.ComicCard(tr("Wartet auf dich"), mascot)
        self.pending_table = self._make_table()
        pending.add_note(self.pending_table)
        self.accept_button = QPushButton(tr("Übernehmen"))
        self.accept_button.setObjectName("comicPrimary")
        self.reject_button = QPushButton(tr("Verwerfen"))
        self.accept_button.setAutoDefault(False)
        self.reject_button.setAutoDefault(False)
        pending.add_note(self._button_row(self.reject_button, self.accept_button))
        body.addWidget(pending)

        active = comic.ComicCard(tr("Aktiv"), mascot)
        self.active_table = self._make_table()
        active.add_note(self.active_table)
        self.delete_button = QPushButton(tr("Löschen"))
        self.delete_button.setAutoDefault(False)
        active.add_note(self._button_row(self.delete_button))
        body.addWidget(active)

        close_button = QPushButton(tr("Schließen"))
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        body.addLayout(comic.footer_row(tr("Ein Klick, und es wirkt sofort."), close_button))

        self.accept_button.clicked.connect(lambda: self._decide(self.pending_table, "accept"))
        self.reject_button.clicked.connect(lambda: self._decide(self.pending_table, "reject"))
        self.delete_button.clicked.connect(lambda: self._decide(self.active_table, "reject"))
        self.pending_table.itemSelectionChanged.connect(self._update_buttons)
        self.active_table.itemSelectionChanged.connect(self._update_buttons)
        self.refresh()
        screen = self.screen()
        if screen is not None:
            self.resize(self.width(), min(self.sizeHint().height(), screen.availableGeometry().height() - 60))

    @staticmethod
    def _button_row(*buttons: QPushButton) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 10, 0, 4)
        row.setSpacing(_BUTTON_ROW_SPACING)
        row.addStretch()
        for button in buttons:
            button.setMinimumWidth(_BUTTON_MIN_WIDTH)
            row.addWidget(button)
        return holder

    @staticmethod
    def _make_table() -> QTableWidget:
        table = QTableWidget(0, len(COLUMNS))
        table.setHorizontalHeaderLabels([tr(column) for column in COLUMNS])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setMinimumHeight(_TABLE_MIN_HEIGHT)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return table

    @staticmethod
    def _fill(table: QTableWidget, entries: list[Entry]) -> None:
        table.clearSelection()
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = (
                entry.wrong, entry.right, tr(KIND_LABELS.get(entry.kind, entry.kind)),
                str(entry.count), entry.example,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, list(entry.key))
                table.setItem(row, col, item)

    def refresh(self) -> None:
        lexicon = self._service.lexicon
        pending_row = min(self._selected_rows(self.pending_table), default=0)
        self._fill(self.pending_table, lexicon.pending())
        self._fill(self.active_table, lexicon.active())
        if self.pending_table.rowCount():
            self.pending_table.selectRow(min(pending_row, self.pending_table.rowCount() - 1))
        self._update_buttons()
        metrics = self._service.metrics()
        text = (
            tr(
                "Korrekturquote diese Woche: {} · Vorwoche: {} · Ausgangswert: {}\n"
                "Zuordnung diese Woche: {}"
            ).format(format_rate(metrics.get('this_week')), format_rate(metrics.get('last_week')), format_rate(metrics.get('baseline')), format_rate(metrics.get('coverage')))
        )
        if not getattr(self._service, "has_sources", True):
            text += "\n" + tr(NO_SOURCES_HINT)
        self.metrics_label.setText(text)

    @staticmethod
    def _selected_rows(table: QTableWidget) -> list[int]:
        return [index.row() for index in table.selectionModel().selectedRows()]

    def _update_buttons(self) -> None:
        has_pending = bool(self._selected_rows(self.pending_table))
        self.accept_button.setEnabled(has_pending)
        self.reject_button.setEnabled(has_pending)
        self.delete_button.setEnabled(bool(self._selected_rows(self.active_table)))

    def _selected_keys(self, table: QTableWidget) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for index in table.selectionModel().selectedRows():
            item = table.item(index.row(), 0)
            if item is not None:
                keys.append(tuple(item.data(Qt.ItemDataRole.UserRole)))
        return keys

    def _decide(self, table: QTableWidget, action: str) -> None:
        keys = self._selected_keys(table)
        if not keys:
            return
        lexicon = self._service.lexicon
        for key in keys:
            getattr(lexicon, action)(key)
        try:
            lexicon.save()
        except OSError:
            log.exception("Lernen: Speichern nach Entscheidung fehlgeschlagen")
        self.refresh()
