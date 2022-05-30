import sys
import json

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from utils import settings
#from station.boss import Boss


class VCHlistener(QtWidgets.QMainWindow):

    def __init__(self, args):

        self.app = QtWidgets.QApplication(sys.argv)

        super().__init__()

        #self.boss = Boss(self)

        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        self.setWindowTitle('VCH Listener')
        self.resize(700, 300)

        # Make Application layout
        self.Vlayout = QtWidgets.QVBoxLayout()
        #self.Vlayout.addLayout(self.make_action_box())
        #self.Vlayout.addLayout(self.make_message_box())
        #self.Vlayout.addLayout(self.make_operator_box())

        widget = QtWidgets.QWidget()
        widget.setLayout(self.Vlayout)
        self.setCentralWidget(widget)

        self.init_pos()
        self.show()

        #self.boss.start()

    # Move window to initial position
    def init_pos(self):
        if hasattr(settings, 'Position'):
            self.move(settings.Position.x, settings.Position.y)

    # Make box for displaying session status and actions
    def make_action_box(self):

        # Create buttons
        box = QtWidgets.QGridLayout()
        box.addWidget(self.boss, 0, 0, 1, 3)
        box.addWidget(self.boss.upcoming_button, 0, 5)
        box.addWidget(self.boss.label_widget, 1, 0, 1, 1)
        box.addWidget(self.boss.status_widget, 1, 1, 1, 5)

        box.addWidget(self.boss.processor, 2, 0, 4, 6)

        groupbox = QtWidgets.QGroupBox('Action')
        groupbox.setStyleSheet("QGroupBox { font-weight: bold; } ")
        groupbox.setLayout(box)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(groupbox)
        return grid

    # Make box displaying session information
    def make_message_box(self):

        box = QtWidgets.QGridLayout()
        box.addWidget(self.boss.messages_widget, 0, 0, 3, 6)
        box.addWidget(self.boss.automatic_widget, 3, 0)
        box.addWidget(self.boss.accept_widget, 3, 4)
        box.addWidget(self.boss.skip_widget, 3, 5)

        groupbox = QtWidgets.QGroupBox('Messages')
        groupbox.setStyleSheet("QGroupBox { font-weight: bold; } ")
        groupbox.setLayout(box)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(groupbox)
        return grid

    # Make box for displaying operations
    def make_operator_box(self):

        box = QtWidgets.QGridLayout()
        box.addWidget(self.boss.oper_widget, 0, 0, 1, 5)
        box.addWidget(self.boss.execute_widget, 0, 5)

        groupbox = QtWidgets.QGroupBox('Operator input')
        groupbox.setStyleSheet("QGroupBox { font-weight: bold; } ")
        groupbox.setLayout(box)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(groupbox)
        return grid

    def process_messages(self, headers, data):

        self.messenger.accept_msg()
        print('STA', headers)
        print('STA', data)
        return

        text = data
        if headers['format'] == 'json':
            data = json.loads(data)
            text = ', '.join([f'{key}={val}' for key, val in data.items()])
        msg = f'{headers["code"]} {text}'
        self.display_message(msg)

        if fnc := self.boss.get_task(headers['code']):
            if self.automatic_mode:
                fnc(headers['code'], data)
                self.messenger.accept_msg()
            else:
                self.last_msg = (fnc, headers['code'], data)
                self.enable_msg_reply(True)
        else:
            self.boss.processor.add_text(':', f'{msg} not valid')

    def ack_message(self):
        self.enable_msg_reply(False)
        if self.sender() == self.accept:
            fnc, code, command = self.last_msg
            fnc(code, command)
        self.messenger.accept_msg()

    def check_next(self):
        print('Checking master')

    def test_msg(self):
        self.messenger.ping('NS-K2')
        self.messenger.pong('NS-GS', 'STA_Ow', 'testing mode')
        self.messenger.send('NS-GS', 'test', 'TEST', {'info': 'this is a test'})

    def send_message(self):
        print('sending ', self.input_msg.text())
        publisher = '' #Publisher(self.boss.sta_id, settings.Messaging)
        publisher.send(self.input_msg.text())
        self.input_msg.setText('')

    def get_schedule(self):
        print('Get schedule')

    def update_session_status(self, utc):
        if not (int(utc.timestamp()) % 60):
            self.session_status.setText(self.session.status(utc))
            #if utc > self.session.end:
            #    self.utctimer.remove_action('status')

    def test_action(self, utc):
        if not int(utc.timestamp()) % 5:
            self.session_info.append(utc.strftime('%Y-%m-%d %H:%M:%S'))

    # Execute QtApplication
    def exec(self):
        sys.exit(self.app.exec_())

    def closeEvent(self,event):
        try:
            self.boss.stop()
        except:
            print('Closed with problem')
