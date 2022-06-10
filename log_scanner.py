import sys
from datetime import datetime
import tempfile
from threading import Event
import subprocess
import signal

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, RegexMatchingEventHandler


class Scanner(QThread):
    update = pyqtSignal(str, str)

    def __init__(self, on_new_line, path=None):
        super().__init__()
        if not path:
            path = tempfile.NamedTemporaryFile().name
            open(path, 'w').close()

        self.path = path
        self.stopped = Event()
        self.update.connect(on_new_line)

    def run(self):
        file = self.open()
        waiting_time = 1.0
        while not self.stopped.wait(waiting_time):
            line = file.readline()
            if line.strip():
                print('T', self.path, line.rstrip())
                self.update.emit(self.path, line)
                waiting_time = 0.01
            else:
                waiting_time = 1.0

    def stop(self):
        self.stopped.set()

    def open(self):
        command = f'grep -b "Log Opened" {self.path} | tail -1'
        try:
            st_out, st_err = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE).communicate()
            pos = int(st_out.decode('utf-8').split(':')[0])
        except:
            pos = 0
        file = open(self.path, 'r')
        file.seek(pos)
        print('POS', self.path, pos)
        return file


class FileHandler(PatternMatchingEventHandler):
    patterns = ['*.log']

    def __init__(self, scanners, fnc):
        super().__init__()
        self.scanners = scanners
        self.fnc = fnc

    def on_any_event(self, event):
        print(event)
        if event.event_type in ['moved', 'deleted'] and event.src_path in self.scanners:
            self.scanners[event.src_path].stop()
            self.scanners.pop(event.src_path)
        elif event.event_type in ['created', 'modified']:
            # Stop other scanners
            for path in list(self.scanners.keys()):
                if path != event.src_path:
                    self.scanners[path].stop()
                    self.scanners.pop(path)
                    print('DELETED', path)
            if event.src_path not in self.scanners:
                self.scanners[event.src_path] = scanner = Scanner(self.fnc, event.src_path)
                scanner.start()
                print('ADDED', path)


def print_it(file, text):
    print(f'{datetime.utcnow()} : {file} {text}')


def kill_it(a, b):
    global files

    print('Try to kill')
    for name, scanner in files.items():
        scanner.stop()
        print('Stopped scanner', name)

    QApplication.quit()

if __name__ == '__main__':

    import os

    signal.signal(signal.SIGINT, kill_it)
    signal.signal(signal.SIGTERM, kill_it)

    folder = '/Users/Mario/VLBI/logs'
    station = os.path.join(folder, 'station.log')

    files = {station: Scanner(print_it, station)}
    files[station].start()

    obs = Observer()
    handler = FileHandler(files, print_it)
    obs.schedule(handler, path=folder)
    obs.start()

    app = QApplication(sys.argv)
    sys.exit(app.exec())


