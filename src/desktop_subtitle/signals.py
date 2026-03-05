from PySide6.QtCore import QObject, Signal

class AppSignals(QObject):
    subtitle = Signal(str)
    status = Signal(str)
    error = Signal(str)
