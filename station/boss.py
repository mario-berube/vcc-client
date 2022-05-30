from threading import Event
from datetime import datetime, timedelta
import enum
import re
import os
import json
import math

from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QHBoxLayout, QStyle, QPushButton,\
    QTextEdit, QCheckBox, QMessageBox
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
from PyQt5.QtTest import QTest

from requests import codes as HttpCodes

from utils import settings, get_schedule_info
from tools import get_credentials
from processes import Timer, make_text_box, Session, SessionsViewer, Get, Post
from station.processor import Processor
from processes.messenger import Messenger
from processes.accept import Accepting


class Color(enum.Enum):
    black = "color: black"
    red = "color: red"


class Header(QWidget):
    HorizontalSpacing = 5

    def __init__(self):

        super().__init__()

        self.make_pixmaps()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.title, self.icon = QLabel('No session'), QLabel()
        self.icon.setPixmap(self.unknown)

        layout.addWidget(self.title, alignment=Qt.AlignLeft)
        layout.addWidget(self.icon, alignment=Qt.AlignRight)
        self.setLayout(layout)

    # Make pixmaps variables
    def make_pixmaps(self):
        size = QSize(16, 16)
        icons = {'unknown': 'SP_MessageBoxQuestion', 'warning': 'SP_MessageBoxWarning',
                 'critical': 'SP_MessageBoxCritical', 'stopped': 'SP_DialogNoButton',
                 'running': 'SP_DialogYesButton'}
        for name, code in icons.items():
            setattr(self, name, self.style().standardIcon(getattr(QStyle, code)).pixmap(size))

    # Set text for Header class
    def setText(self, text):
        self.title.setText(text)

    # Set icon
    def setIcon(self, item=None):
        self.icon.setPixmap(item) if item else self.icon.clear()


# Class Boss that control actions
class Boss(QLabel):

    update_rate = timedelta(seconds=60)
    one_day = timedelta(days=1)
    one_hour = timedelta(hours=1)
    fifteen_minutes = timedelta(minutes=15)

    get_name = re.compile('.*filename=\"(?P<name>.*)\".*').match

    def __init__(self, parent):
        super().__init__('')

        self.parent = parent

        self.commands = ['onoff', 'load', 'urgent', 'halt', 'resume', 'terminate', 'plog']
        self.functions = {'master': self.get_upcoming_session, 'schedule': self.get_schedule,
                          'ping': self.send_status}

        self.automatic_mode, self.accept_msg = False, None

        self.sta_id = settings.Identity.code

        self.processor = Processor(self.sta_id, self)

        self.title = f'{self.sta_id} - {settings.Identity.name}'

        self.session, self.wnd_sessions = None, None
        self.last_update = datetime.utcnow() - self.update_rate

        self.actions = {}

    # Display received message
    def display_message(self, msg):
        self.messages.append(f'{datetime.utcnow().isoformat(sep=" ", timespec="milliseconds")}: {msg}')

    @property
    def label_widget(self):
        self.label = Header()
        return self.label

    @property
    def status_widget(self):
        self.status = QLineEdit()
        self.status.setReadOnly(True)
        return self.status

    # Check box for automatic mode selection
    @property
    def automatic_widget(self):
        widget = QCheckBox('Automatic mode')
        widget.setChecked(self.automatic_mode)
        widget.toggled.connect(self.automatic_mode_changed)
        widget.setEnabled(True)
        return widget

    # Check box for automatic mode selection
    @property
    def upcoming_button(self):
        button = QPushButton('Upcoming Sessions')
        button.clicked.connect(lambda event: self.get_upcoming_session())
        return button

    # Edit box for displaying messages
    @property
    def messages_widget(self):
        self.messages = QTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setFont(QFont('Courier New'))
        return self.messages

    # Button for accepting last message
    @property
    def accept_widget(self):
        self.accept = QPushButton('Process')
        self.accept.clicked.connect(lambda event: self.process_last_message(True))
        self.accept.setEnabled(False)
        print('ACCEPT', self.accept.palette().window().color().name())
        #self.accept.setStyleSheet("background-color: green")
        return self.accept

    @property
    def skip_widget(self):
        self.skip = QPushButton('Skip')
        self.skip.clicked.connect(lambda event: self.process_last_message(False))
        #self.skip.setStyleSheet("background-color: yellow")
        self.skip.setEnabled(False)
        return self.skip

    @property
    def execute_widget(self):
        self.execute = QPushButton('Execute')
        self.execute.clicked.connect(self.execute_command)
        self.execute.setEnabled(False)
        return self.execute

    @property
    def oper_widget(self):
        self.oper_input = make_text_box('', readonly=False, fit=False)
        self.oper_input.textChanged.connect(self.enable_execute_button)
        return self.oper_input

    # Get function that will process a specific task
    def get_task(self, name):
        return self.functions.get(name, self.processor.do)

    # Toggle automatic mode when button is press
    def automatic_mode_changed(self):
        self.automatic_mode = self.sender().isChecked()

    # Start timer and other processes
    def start(self):
        self.timer = Timer(self.update_timer)
        self.timer.start()

        # Get next session from web service
        self.get_upcoming_session()
        # Start messenger
        if info := get_credentials(): # Request queue information from web service
            self.display_message('connected to VOC messenger. Waiting for messages')
            self.messenger = Messenger(info, self.process_messages)
            self.messenger.start()
        else:
            self.display_message('Could not connect to VOC messenger')

    # Stop timer
    def stop(self):
        self.timer.stop()

    # Update display for timer
    def update_timer(self, utc):
        self.setText(utc.strftime('%Y-%m-%d %H:%M:%S UTC'))

        self.update_session_info(utc)

        # Execute external actions
        for fnc in self.actions.values():
            fnc(utc)

    # Process or skip last message and remove message
    def process_last_message(self, accept=True):
        self.enable_msg_reply(False)
        #if self.sender() == self.accept:
        if accept:
            fnc, code, command = self.last_msg
            fnc(code, command)
        self.messenger.acknowledge_msg()

    def add_action(self, name, action):
        self.actions[name] = action

    def remove_action(self, name):
        self.actions.pop(name, '')

    def get_upcoming_session(self, action=None, data=None):

        print('GET SESSIONS')
        self.get = Get(f'next/{self.sta_id}', params={'days': 14})
        self.get.on_finish(action, self.process_coming_session)
        self.get.start()

    def get_schedule(self, action, data=None):

        self.processor.add_text('$', 'before wait')
        if self.automatic_mode:
            QTest.qWait(1000) # Make sure it will arrive after any dashboard
        self.processor.add_text('$', 'after wait')

        ses_id = data['session'].lower()
        self.get = Get(f'schedules/{ses_id}', params={'sta_id': self.sta_id, 'format': 'skd'})
        self.get.on_finish(action, self.save_new_schedule)
        self.get.start()

    def process_coming_session(self, action, response, error):

        self.session = None
        result = 'failed'
        if error:
            self.label.setText('Error')
            self.label.setIcon(self.label.critical)
            self.status.setText(error)
        elif not response or response.status_code != HttpCodes.ok:
            self.label.setText('Error')
            self.label.setIcon(self.label.critical)
            self.status.setText('invalid data from VLBI Data Center')
        elif sessions := response.json():
            self.last_update = datetime.utcnow() - self.update_rate
            self.session = Session(sessions[0])
            self.label.setText(self.session.code)
            self.label.setIcon(self.label.running)
            self.status.setText('')
            self.show_sessions(sessions)
            result = 'processed'
        if action:
            self.processor.add_text(':', f'{action} {result}')

    def save_new_schedule(self, msg, response, error):
        result = f'{msg} failed'
        if not error and response and response.status_code == HttpCodes.ok:
            if found := self.get_name(response.headers['content-disposition']):
                filename = found['name']
                path = os.path.join(settings.Folders.schedules, filename)
                with open(path, 'wb') as f:
                    f.write(response.content)
                result = f'{filename} downloaded'
                if self.automatic_mode:
                    self.processor.add_text('&', 'receive schedule')
                    ses_id, start, end, version = get_schedule_info(path)
                    if ses_id and end > datetime.utcnow():
                        data = {'session': ses_id, 'time': start - timedelta(seconds=305)}
                        self.processor.do('auto', data)

        self.processor.add_text(':', result)
        self.update_sessions()

    def update_status(self, msg, color=Color.black):
        self.status.setText(msg)
        self.status.setStyleSheet(color.value)

    def update_session_info(self, utc):
        if not self.session or utc - self.last_update < self.update_rate:
            return
        self.last_update = utc.replace(second=0, microsecond=0)

        if utc > self.session.end:
            self.update_status('Terminated', Color.red)
        elif utc >= self.session.start:
            self.update_status('Running')
        else:
            dt = self.session.start - utc
            if dt > self.one_day:
                self.update_status(f'Starting in {dt.days} day{"s" if dt.days > 1 else ""}')
            elif dt > self.one_hour:
                self.update_status(f'Starting in {dt.seconds//3600:02d}:{dt.seconds%3600//60:02d}')
            else:
                minutes = math.ceil(dt.seconds % 3600 / 60)
                color = Color.red if dt < self.fifteen_minutes else Color.black
                self.update_status(f'Starting in {minutes} minute{"s" if minutes > 1 else ""}', color)

    def enable_execute_button(self):
        if command := self.oper_input.text().lstrip():
            self.execute.setEnabled(command.split()[0].lower() in self.commands)
        else:
            self.execute.setEnabled(False)

    def execute_command(self):
        input = self.oper_input.text().lstrip().lower()
        self.oper_input.setText('')
        command = input.split()[0]
        self.functions.get(command, self.processor.do)(command, input.replace(command, '').strip())

    def show_sessions(self, sessions):
        try:
            self.wnd_sessions.close()
        except:
            pass
        self.wnd_sessions = SessionsViewer(self, sessions)
        self.wnd_sessions.show()

    def update_sessions(self):
        try:
            self.wnd_sessions.check_schedules()
        except:
            pass

    def session_viewer_closed(self, event):
        print('CLOSE VIEWER')
        self.wnd_sessions = None

    def send_status(self, ):
        self.messenger.pong(settings.get_user_id(), 'Ok')

    def is_ping(self, headers):
        if not headers.get('code', '') == 'ping':
            return False
        self.send_status(headers.get('reply_to'))
        self.messenger.acknowledge_msg()
        return True

    def process_messages(self, headers, data):
        print('MSG', headers, data)
        # Check if message is 'vlbi' or a ping
        if self.is_ping(headers):
            return
        # Decode message
        if headers.get('format', 'text') == 'json':
            data = json.loads(data)
        text = ', '.join([f'{key}={val}' for key, val in data.items()]) if isinstance(data, dict) else str(data)
        msg = f'{headers["code"]} {text}'

        # Call appropriate function
        if fnc := self.get_task(headers['code']):
            self.display_message(msg)
            if self.automatic_mode:
                fnc(headers['code'], data)
                self.messenger.acknowledge_msg()
            else:
                self.last_msg = (fnc, headers['code'], data)
                self.enable_msg_reply(True)
                #self.show_accept_message(msg)
        else:  # Remove message since there nothing to do with it.
            self.display_message(':', f'{msg} not valid')
            self.messenger.acknowledge_msg()

    def decode_onoff_record(self, line):
        data = line.split()
        return {name: data[index] for index, name in enumerate(self.onoff_header)}

    def onoff(self, action, which='before'):
        self.processor.add_text(':', f'{action}')

        path = os.path.join(settings.Folders.data, f'onoff.{which}')
        data = {'time': datetime.utcnow().isoformat(), 'station': self.sta_id, 'values':[]}

        with open(path) as file:
            for line in file:
                self.processor.add_text('#onoff#VAL ', line[30:].rstrip())
                data['values'].append(self.decode_onoff_record(line[30:].lstrip()))

        # Send data to VLBI Data Center web service
        self.post = Post('onoff/', data)
        self.post.on_finish(self.onoff_submitted)
        self.post.start()

    def onoff_submitted(self, response, error):
        if error:
            text= error
        elif not response or response.status_code != HttpCodes.ok:
            text = 'Invalid response from VLBI Data Center'
        elif 'updated' in response.json():
            text = 'onoff records updated'
        else:
            text = f'Unknown problem {response.text}'

        self.processor.add_text(':', text)

    def enable_msg_reply(self, enable):
        self.accept.setStyleSheet(f'background-color: {"green" if enable else "#efefef"}')
        self.skip.setStyleSheet(f'background-color: {"yellow" if enable else "#efefef"}')
        self.accept.setEnabled(enable)
        self.skip.setEnabled(enable)

    def show_accept_message_test(self, text):
        self.prc = Accepting(text, self.parent, self.process_last_message)
        self.prc.start()

    # Popup window to display station message.
    def show_accept_message(self, text):
        title = f'{settings.Identity.name} received message'
        line_length = len(text)+50

        box = QMessageBox(self.parent)
        box.setIcon(QMessageBox.Warning)
        box.setStandardButtons(QMessageBox.Yes|QMessageBox.No)

        box.button(QMessageBox.Yes).setText('Process')
        box.button(QMessageBox.No).setText('Skip')

        box.setText('{:}'.format(text.ljust(line_length)))
        box.setGeometry(QStyle.alignedRect(Qt.LeftToRight, Qt.AlignCenter, box.size(), self.parent.geometry()))
        box.setWindowTitle(title)

        self.process_last_message(box.exec_() == QMessageBox.Yes)


