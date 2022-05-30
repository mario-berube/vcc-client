import re
import sys
from datetime import datetime, timedelta

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtWidgets import QPushButton, QGridLayout, QLineEdit, QLabel, QSizePolicy, QCheckBox
from PyQt5.QtWidgets import QComboBox, QFrame, QMessageBox, QStyle, qApp
from PyQt5.QtCore import Qt

from master import COLUMNS
from vcc import signature, json_decoder, VCCError
from vcc.vws import get_client
from vcc.session import Session


# Popup window to display error message with icon.
def ErrorMessage(text, critical=True):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical if critical else QMessageBox.Information)
    msg.setText(text)

    msg.setGeometry(
    QStyle.alignedRect(Qt.LeftToRight, Qt.AlignCenter, msg.size(), qApp.desktop().availableGeometry(),
    ))
    msg.setWindowTitle('Fatal Error')
    msg.exec_()


# Create a read-only QLineEdit with size based on length of text
class TextBox(QLineEdit):
    def __init__(self, text, readonly=False, parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred))
        self.parent = parent
        self.setReadOnly(readonly)

    def sizeHint(self):
        if not self.parent:
            return super().sizeHint()
        return self.parent.size()


# Class used to draw horizontal separator
class HSeparator(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(1)
        self.setFixedHeight(20)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


class SessionViewer(QMainWindow):

    def __init__(self, ses_id):

        super().__init__()

        try:
            client = get_client()
        except VCCError as exc:
            ErrorMessage(str(exc), critical=True)
            sys.exit(0)
        self.headers = signature.make('CC')

        self.session = self.get_session(client, ses_id)
        self.operations = self.make_combobox(client, '/catalog/operations', self.session.operations)
        self.correlator = self.make_combobox(client, '/catalog/correlator', self.session.correlator)
        self.analysis = self.make_combobox(client, '/catalog/analysis', self.session.analysis)
        self.db_code = self.make_combobox(client, '/catalog/dbc_codes', self.session.db_code)

        self.stations = self.get_stations(client)

        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        self.setWindowTitle(f'Session {self.session.code}')

        widget = QWidget()
        self.grid = self.initUI()
        widget.setLayout(self.grid)
        self.setCentralWidget(widget)

        self.resize(20, 20)
        self.move(300, 150)

    def initUI(self):

        grid = QGridLayout()

        grid.addWidget(QLabel("Code"), 0, 0)
        grid.addWidget(TextBox(self.session.code, readonly=True), 0, 1)
        grid.addWidget(QLabel("Name"), 0, 3)
        grid.addWidget(TextBox(self.session.name), 0, 4)
        is_intensive = QCheckBox("Intensive")
        is_intensive.setChecked(self.session.type == 'intensive')
        is_intensive.setLayoutDirection(Qt.RightToLeft)
        grid.addWidget(is_intensive, 0, 5, 1, 2)
        grid.addWidget(QLabel("Start"), 1, 0)
        grid.addWidget(TextBox(self.session.start.strftime('%Y-%m-%d %H:%M')), 1, 1, 1, 2)
        grid.addWidget(QLabel("Duration"), 1, 3)
        grid.addWidget(TextBox(f'{float(self.session.duration/3600):.2f}'), 1, 4)
        grid.addWidget(QLabel("hours"), 1, 5)
        grid.addWidget(QLabel("Operations Center"), 2, 0, 1, 2)
        grid.addWidget(self.operations, 2, 2)
        grid.addWidget(QLabel("Correlator"), 2, 3)
        grid.addWidget(self.correlator, 2, 4)
        grid.addWidget(QLabel("Analysis"), 2, 5)
        grid.addWidget(self.analysis, 2, 6)
        grid.addWidget(QLabel("DBC Code"), 3, 0)
        grid.addWidget(self.db_code, 3, 1)
        grid.addWidget(HSeparator(), 4, 0, 1, 7)
        grid.addWidget(QLabel("Stations"), 5, 0)
        grid.addWidget(self.station_list(), 5, 1, 1, 6)
        grid.addWidget(HSeparator(), 6, 0, 1, 7)
        button = QPushButton('Quit')
        button.clicked.connect(self.close)
        grid.addWidget(button, 7, 0)
        button = QPushButton('Submit')
        button.clicked.connect(self.submit)
        grid.addWidget(button, 7, 6)

        return grid

    def submit(self):
        def get_text(row, col):
            return self.grid.itemAtPosition(row, col).widget().text()

        # Check if name is not empty
        self.session.name = get_text(0, 4).strip()
        if not self.session.name:
            ErrorMessage('Session name is empty')
            self.grid.itemAtPosition(0, 4).widget().setFocus()
            return
        # Get session type
        self.session.type = 'intensive' if self.grid.itemAtPosition(0, 5).widget().isChecked() else 'standard'
        # Check if start time is valid
        try:
            self.session.start = datetime.strptime(get_text(1, 1).strip(), '%Y-%m-%d %H:%M')
            if self.session.start < datetime.utcnow():
                ErrorMessage('Start time in the past')
                self.grid.itemAtPosition(1, 1).widget().setFocus()
                return
        except Exception as exc:
            ErrorMessage(f'Invalid start time [{str(exc)}]')
            self.grid.itemAtPosition(1, 1).widget().setFocus()
            return
        # Check if duration is at least 1 minute
        self.session.duration = float(get_text(1, 4).strip())
        if int(self.session.duration * 3600) < 60:
            ErrorMessage(f'Duration is less than 1 minute')
            self.grid.itemAtPosition(1, 4).widget().setFocus()
            return
        # Check if centers are selected
        for (name, line, label) in [('operations', 2, 0), ('correlator', 2, 3), ('analysis', 2, 5), ('db_code', 3, 0)]:
            item = getattr(self, name).currentText()
            if not item:
                ErrorMessage(f'Please select {get_text(line, label)}')
                self.operations.setFocus()
                return
            setattr(self.session, name, item)
        # Check station list
        network = get_text(5, 1).split(' -')
        self.session.included = [code.capitalize() for code in re.findall('..', network[0])]
        self.session.removed = [code.capitalize() for code in re.findall('..', network[1])] if len(network) > 1 else []
        if len(self.session.included) + len(self.session.removed) < 2:
            ErrorMessage('Not enought stations')
            self.grid.itemAtPosition(5, 1).widget().setFocus()
            return
        not_valid = [sta_id for sta_id in self.session.included+self.session.removed if sta_id not in self.stations]
        if not_valid:
            ErrorMessage(f'Not valid stations\n{"".join(not_valid)}')
            self.grid.itemAtPosition(5, 1).widget().setFocus()
            return
        # Update information on VCC
        try:
            client = get_client()
            data = {code: getattr(self.session, code) for code in COLUMNS if hasattr(self.session, code)}
            data = dict(**data, **{'start': self.session.start, 'type': self.session.type, 'stations': get_text(5, 1)})
            headers = signature.make('CC')
            rsp = client.put(f'/sessions/{self.session.code}', data=data, headers=headers)
            if not rsp or not signature.validate(rsp):
                raise VCCError(f'VCC response {rsp.status_code}\n{rsp.text}')
            ErrorMessage(f'{self.session.code.upper()} not updated\nSame information already on VCC'
                         if json_decoder(rsp.json())[self.session.code] == 'same'
                         else f'{self.session.code.upper()} updated', critical=False)
        except VCCError as exc:
            ErrorMessage(f'Problem updating {self.session.code}\n{str(exc)}')

    def get_session(self, client, ses_id):
        try:
            rsp = client.get(f'/sessions/{ses_id}', headers=self.headers)
            if rsp and signature.validate(rsp):
                return Session(json_decoder(rsp.json()))
        except VCCError:
            pass
        return Session({'code': ses_id})

    def get_stations(self, client):
        try:
            rsp = client.get(f'/stations', headers=self.headers)
            if rsp and signature.validate(rsp):
                return [sta['code'].capitalize() for sta in json_decoder(rsp.json())]
        except VCCError:
            pass
        return []

    def make_combobox(self, client, url, selection):
        try:
            rsp = client.get(url, headers=self.headers)
            cb = QComboBox()
            if rsp and signature.validate(rsp):
                [cb.addItem(item['code'].strip()) for item in json_decoder(rsp.json())]
        except VCCError:
            pass
        cb.setCurrentIndex(cb.findText(selection))
        return cb

    def station_list(self):
        lst = [code.capitalize() for code in self.session.included]
        if self.session.removed:
            lst.append(' -')
            lst.extend([code.capitalize() for code in self.session.removed])
        return TextBox(''.join(lst))


def view_session(ses_id):
    app = QApplication(sys.argv)
    viewer = SessionViewer(ses_id)
    viewer.show()
    sys.exit(app.exec_())


