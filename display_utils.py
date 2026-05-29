"""
Utilitários para posicionar a tela do público/plenário em monitores.
"""

from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication, QWidget


def ordered_screens(app: Optional[QApplication] = None) -> List[QScreen]:
    """Lista monitores em ordem estável (esquerda → direita, depois Y)."""
    app = app or QApplication.instance()
    if not app:
        return []
    screens = list(app.screens())
    screens.sort(key=lambda s: (s.geometry().x(), s.geometry().y()))
    return screens


def screen_choice_label(screen: QScreen, index: int, primary: Optional[QScreen]) -> str:
    """Rótulo amigável para combo de seleção de monitor."""
    name = screen.name() or f"Display {index + 1}"
    geo = screen.geometry()
    suffix = " — principal" if primary and screen == primary else ""
    return f"Monitor {index + 1}: {name} ({geo.width()}×{geo.height()}){suffix}"


def list_screen_choices(app: Optional[QApplication] = None) -> List[Tuple[int, str]]:
    """Retorna [(índice, rótulo), ...] para QComboBox."""
    app = app or QApplication.instance()
    screens = ordered_screens(app)
    if not app or not screens:
        return []
    primary = app.primaryScreen()
    return [(i, screen_choice_label(s, i, primary)) for i, s in enumerate(screens)]


def resolve_public_screen(
    screen_index: Optional[int] = None,
    session_config=None,
    app: Optional[QApplication] = None,
) -> Optional[QScreen]:
    """
    Resolve o QScreen da tela do público.
    Por padrão usa índice 1 (segundo monitor). Com 1 monitor, usa o único disponível.
    """
    app = app or QApplication.instance()
    screens = ordered_screens(app)
    if not screens:
        return None

    if screen_index is None and session_config is not None:
        screen_index = session_config.get_public_screen_index()
    if screen_index is None:
        screen_index = 1

    if len(screens) == 1:
        return screens[0]

    if screen_index < 0:
        screen_index = 0
    if screen_index >= len(screens):
        screen_index = len(screens) - 1

    return screens[screen_index]


def apply_public_screen_fullscreen(
    window: QWidget,
    session_config=None,
    window_name: str = "Tela do público",
) -> None:
    """Exibe a janela em fullscreen no monitor configurado."""
    app = QApplication.instance()
    target_screen = resolve_public_screen(session_config=session_config, app=app)

    if not target_screen:
        window.showFullScreen()
        return

    try:
        handle = window.windowHandle()
        if handle:
            handle.setScreen(target_screen)
    except Exception as e:
        print(f"⚠️ {window_name}: falha ao definir monitor ({e})")

    window.setGeometry(target_screen.geometry())

    if sys.platform == "darwin":
        window.showNormal()
        window.show()
        QTimer.singleShot(120, window.showFullScreen)
        QTimer.singleShot(
            320,
            lambda: _retry_macos_fullscreen(window, session_config, window_name, 1),
        )
    else:
        window.showFullScreen()

    screens = ordered_screens(app)
    idx = screens.index(target_screen) if target_screen in screens else -1
    monitor_num = idx + 1 if idx >= 0 else "?"
    print(f"✅ {window_name} → Monitor {monitor_num}: {target_screen.name()}")


def _retry_macos_fullscreen(
    window: QWidget,
    session_config,
    window_name: str,
    attempt: int,
) -> None:
    if sys.platform != "darwin" or attempt > 4:
        return

    app = QApplication.instance()
    if not app:
        return

    target_screen = resolve_public_screen(session_config=session_config, app=app)
    if not target_screen:
        return

    if window.screen() == target_screen:
        return

    try:
        handle = window.windowHandle()
        if handle:
            handle.setScreen(target_screen)
    except Exception:
        pass

    window.showNormal()
    window.setGeometry(target_screen.geometry())
    window.showFullScreen()
    QTimer.singleShot(
        180,
        lambda: _retry_macos_fullscreen(window, session_config, window_name, attempt + 1),
    )
