from unittest.mock import patch, MagicMock


def test_menubar_imports():
    from kira.ui import menubar
    assert hasattr(menubar, "KiraMenubar")


def test_assets_exist():
    from kira.ui.menubar import ICON_DEFAULT
    from pathlib import Path
    assert Path(ICON_DEFAULT).exists()
