import json
import re
import os
import signal
import sys

from vcc import settings, messaging
from vcc.vws import get_client, VCCError
from vcc.session import Session

from PyQt5.QtWidgets import QApplication, QMessageBox

class Listener:

    extract_name = re.compile('.*filename=\"(?P<name>.*)\".*').match

    def __init__(self, group_id, session):

        # Make sure it terminate elegantly after Ctr+C
        #signal.signal(signal.SIGINT, self.killed)
        signal.signal(signal.SIGTERM, self.killed)

        self.messenger = None

        self.client = get_client(group_id)
        self.sta_id = settings.Signatures.NS[0]

    def killed(self, sig, frame):
        self.messenger.close()
        exit(0)

    def monit(self, keep_alive=False):

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)

        msg.setText("This is a message box")
        msg.setInformativeText("This is additional information")
        msg.setWindowTitle("MessageBox demo")
        msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.show()

        while True:
            try:
                config = self.client.get_inbox_credentials()
                with messaging.RMQclient(config, multi=True) as self.messenger:
                    self.messenger.monit(self.process_message, self.process_timeout, timeout=60)
                    break
            except KeyboardInterrupt:
                return
            except VCCError as err:
                print('Fatal error', str(err))
                return
            except messaging.RMQclientException as exc:
                print('Monit error', str(exc))
                if not keep_alive:
                    return

    def process_message(self, headers, data):
        # Ping sent by dashboard
        code = headers['code']
        if code == 'ping':
            self.messenger.pong(self.sta_id, headers.get('reply_to'), 'Ok')
        else:
            # Decode message
            data = json.loads(data) if headers.get('format', 'text') == 'json' else {}
            text = ', '.join([f'{key}={val}' for key, val in data.items()]) if isinstance(data, dict) else str(data)
            print(f'Message: {code} {text}')
            if code == 'master':
                for ses_id, status in data.items():
                    self.session_has_changed(ses_id, status)
                self.show_upcoming_sessions()
            elif code == 'schedule':
                self.download_schedule(data)
        # Always acknowledge message
        print('Calling acknowledge')
        self.messenger.acknowledge_msg()

    def session_has_changed(self, ses_id, status):
        # Get session information
        rsp = self.client.get(f'/sessions/{ses_id}')
        if rsp:
            session = Session(rsp.json())
            print(f'{session} --- {status}!')

    # Process timeout
    def process_timeout(self):
        print('Processing time out')
        self.messenger.send(self.sta_id, 'TEST', 'CC-GSFC', {'test': 'This is a test'})

    # Process message with master code
    def show_upcoming_sessions(self):
        # Print upcoming sessions
        print(f'\nComing sessions for {self.sta_id}')
        rsp = self.client.get(f'/sessions/next/{self.sta_id}', params={'days': 14})
        if rsp:
            for index, data in enumerate(rsp.json(), 1):
                session = Session(data)
                print(f'{index:2d} {session}')

    # Download schedule from VOC
    def download_schedule(self, data):
        ses_id = data['session'].lower()
        # Get session information (formats: ('skd', 'vex' 'skd|vex' 'vex|skd') default is 'skd|vex' skd first.
        rsp = self.client.get(f'schedules/{ses_id}', params={'sta_id': self.sta_id, 'format': 'skd'})
        if rsp:
            found = self.extract_name(rsp.headers['content-disposition'])
            if found:
                filename = found['name']
                path = os.path.join(settings.Folders.schedules, filename)
                with open(path, 'wb') as f:
                    f.write(rsp.content)

                print(f'{filename} has been downloaded!')


if __name__ == '__main__':

    import argparse

    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser( description='Station Listener' )
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('code')
    parser.add_argument('session', nargs='?')

    args = settings.init(parser.parse_args())

    Listener(args.code, args.session).monit(keep_alive=True)


