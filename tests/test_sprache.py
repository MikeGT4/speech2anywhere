# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import pytest
from kira import texte


@pytest.fixture(autouse=True)
def _german_again():
    yield
    texte.set_language("de")


def test_german_is_the_default_and_returns_the_text_itself():
    assert texte.language() == "de"
    assert texte.tr("Speichern") == "Speichern"


def test_english_looks_the_text_up():
    texte.set_language("en")
    assert texte.language() == "en"
    assert texte.tr("Speichern") == "Save"


def test_text_without_an_entry_stays_as_it_is():
    texte.set_language("en")
    assert texte.tr("dafür gibt es keinen Eintrag") == "dafür gibt es keinen Eintrag"


def test_marker_returns_its_text_unchanged_in_every_language():
    texte.set_language("en")
    assert texte.N_("Speichern") == "Speichern"


def test_unknown_language_is_ignored():
    texte.set_language("en")
    texte.set_language("xx")
    assert texte.language() == "en"


@pytest.mark.parametrize("setting", ["de", "en"])
def test_fixed_setting_wins_over_the_system(setting):
    assert texte.resolve_language(setting, system=lambda: "fr") == setting


def test_auto_follows_a_german_system():
    assert texte.resolve_language("auto", system=lambda: "de") == "de"


@pytest.mark.parametrize("system", ["en", "fr", "", None])
def test_auto_is_english_on_every_other_system(system):
    assert texte.resolve_language("auto", system=lambda: system) == "en"


def test_system_language_names_german_and_english_and_nothing_else():
    assert texte.language_of_windows_id(0x0407) == "de"
    assert texte.language_of_windows_id(0x0C07) == "de"
    assert texte.language_of_windows_id(0x0409) == "en"
    assert texte.language_of_windows_id(0x040C) == ""
