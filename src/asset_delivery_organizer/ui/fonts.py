from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


def configure_application_font(app: QApplication) -> str:
    preferred = ("Microsoft YaHei UI", "Microsoft YaHei", "Alibaba PuHuiTi 2.0")
    families = set(QFontDatabase.families())
    selected = next((name for name in preferred if name in families), None)
    if selected is None and os.name == "nt":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for filename in ("msyh.ttc", "msyhbd.ttc", "simsun.ttc"):
            font_id = QFontDatabase.addApplicationFont(str(fonts_dir / filename))
            loaded = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if loaded:
                selected = next((name for name in preferred if name in loaded), loaded[0])
                break
    selected = selected or app.font().family()
    app.setFont(QFont(selected, 10))
    return selected
