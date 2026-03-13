from PySide6 import QtCore, QtWidgets


class RiftFormWorker(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(str)
    progress = QtCore.Signal(str)

    def __init__(self, dest_folder, logger, rift_core, rustmeta, apply_silent, debug_build):
        super().__init__()
        self.dest_folder = dest_folder
        self.logger = logger
        self.rift_core = rift_core
        self.rustmeta = rustmeta
        self.apply_silent = apply_silent
        self.debug_build = debug_build

    @QtCore.Slot()
    def do_apply(self):
        try:
            # Heavy/slow logic here. Do NOT touch Qt widgets here.
            # self.progress.emit("Starting RIFT apply...")
            self.logger.info("Running RIFT flirt signature generation ..")
            self.rift_core.run(self.dest_folder, self.rustmeta, self.apply_silent, self.debug_build)
            # ... run RIFT apply ...
            # self.progress.emit("RIFT apply running silently.")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

class RiftController(QtCore.QObject):

    def __init__(self, parent=None, rift_core=None, logger=None):
        super().__init__(parent)
        self._active = []
        self.rift_core = rift_core
        self.logger = logger
    
    def start_apply(self, dest_folder, rustmeta, parent_widget=None, apply_silent=False, debug_build=False):
        thread = QtCore.QThread()
        worker = RiftFormWorker(dest_folder, self.logger, self.rift_core, rustmeta, apply_silent, debug_build)
        worker.moveToThread(thread)
        # wiring
        thread.started.connect(worker.do_apply)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # optional: handle error/progress in UI thread safely
        worker.error.connect(lambda msg: self._notify_error(msg, parent_widget))
        worker.progress.connect(lambda msg: self._notify_info(msg, parent_widget))

        # cleanup refs
        thread.finished.connect(lambda: self._drop(thread, worker))

        self._active.append((thread, worker))
        thread.start()

    def _drop(self, thread, worker):
        self._active = [(t, w) for (t, w) in self._active if t is not thread]

    def _notify_info(self, text, parent_widget=None):
        # lightweight non-blocking notification (or log to IDA output)
        # Keep it short; avoid spamming.
        pass

    def _notify_error(self, text, parent_widget=None):
        # You can show a non-modal message box if needed.
        msg = QtWidgets.QMessageBox(parent_widget)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("RIFT Apply Error")
        msg.setText(text)
        msg.setWindowModality(QtCore.Qt.NonModal)
        msg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        msg.show()

