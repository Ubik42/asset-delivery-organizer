from __future__ import annotations

APP_STYLE = """
* { font-family: "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 13px; }
QMainWindow, QWidget#AppRoot { background: #101815; color: #E9F0EC; }
QLabel { color: #E9F0EC; }
QScrollArea { background: #101815; border: 0; }
QWidget#ProfileEditor { background: #101815; color: #E9F0EC; }
QFrame#TopBar { background: #17221D; border-bottom: 1px solid #314239; }
QLabel#ProductName { font-size: 20px; font-weight: 700; color: #F4F8F5; }
QLabel#ProductSubtitle, QLabel#Muted { color: #A7B9AF; }
QLabel#ReadOnlyBadge { background: #244A38; color: #DFF6E9; border-radius: 12px; padding: 5px 10px; font-weight: 600; }
QFrame#Sidebar { background: #131D19; border-right: 1px solid #2A3A32; }
QListWidget#Navigation { background: transparent; border: 0; outline: 0; padding: 8px; }
QListWidget#Navigation::item { color: #AFC0B6; padding: 11px 12px; margin: 2px 0; border-radius: 7px; }
QListWidget#Navigation::item:selected { color: #F2FAF5; background: #2A5C45; font-weight: 600; }
QListWidget#Navigation::item:hover:!selected { background: #1D2B25; color: #E9F0EC; }
QLabel#PageTitle { font-size: 20px; font-weight: 700; color: #F4F8F5; }
QLabel#SectionTitle { font-size: 15px; font-weight: 650; color: #EAF3ED; }
QFrame#Panel, QGroupBox { background: #18231E; border: 1px solid #304139; border-radius: 10px; }
QGroupBox { margin-top: 14px; padding: 14px 12px 12px 12px; font-weight: 650; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #DCE9E1; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit { background: #101815; color: #EDF4F0; border: 1px solid #3B5045; border-radius: 7px; padding: 7px 9px; selection-background-color: #397759; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #5DAE82; }
QLineEdit:disabled { color: #6F8077; background: #151C19; }
QLineEdit[invalid="true"], QSpinBox[invalid="true"] { border: 1px solid #D87364; background: #211815; }
QLabel#ProfileValidation { color: #AFC0B6; padding: 7px 10px; border-radius: 7px; }
QLabel#ProfileValidation[status="valid"] { color: #DDF6E7; background: #234A37; }
QLabel#ProfileValidation[status="invalid"] { color: #FFD8D1; background: #572A25; }
QPushButton { background: #26352E; color: #E8F0EB; border: 1px solid #40564A; border-radius: 7px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #31463B; }
QPushButton:pressed { background: #1E2B25; }
QPushButton:focus { border: 1px solid #79C29B; }
QPushButton:disabled { color: #708078; background: #1B2420; border-color: #2A3731; }
QPushButton#PrimaryButton { background: #397C59; color: #FFFFFF; border: 0; padding: 9px 18px; }
QPushButton#PrimaryButton:hover { background: #458E68; }
QPushButton#PrimaryButton:pressed { background: #2F694A; }
QPushButton#PrimaryButton:disabled { background: #26332D; color: #718078; border: 1px solid #34433B; }
QTableWidget { background: #111A16; alternate-background-color: #16201B; color: #E5EEE8; border: 1px solid #2E4037; border-radius: 8px; gridline-color: #27372F; selection-background-color: #28543F; selection-color: #FFFFFF; }
QHeaderView::section { background: #202E27; color: #C7D5CD; border: 0; border-right: 1px solid #31433A; border-bottom: 1px solid #31433A; padding: 8px; font-weight: 650; }
QTableWidget::item { padding: 7px; }
QCheckBox { spacing: 9px; color: #DCE6E0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { background: #111A16; border: 1px solid #53695D; border-radius: 4px; }
QCheckBox::indicator:checked { background: #4E9C70; border: 1px solid #69B789; border-radius: 4px; }
QProgressBar { background: #101815; border: 1px solid #35483E; border-radius: 5px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #4E9C70; border-radius: 4px; }
QLabel#SummaryPassed { background: #234A37; color: #DDF6E7; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QLabel#SummaryWarning { background: #5B4520; color: #FFE7B0; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QLabel#SummaryError { background: #572A25; color: #FFD8D1; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QLabel#StatusMessage { background: #18231E; color: #BED0C5; border-top: 1px solid #2D4036; padding: 7px 14px; }
QSplitter::handle { background: #293A32; width: 1px; }
QScrollBar:vertical { background: #121A17; width: 10px; }
QScrollBar::handle:vertical { background: #3A5044; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #EAF2ED; color: #15201B; border: 0; padding: 6px; }
"""
