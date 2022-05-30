import json
import re
import os
import signal

from vcc import settings, messaging, vws
from vcc.session import Session

from requests import codes as HTTPcodes


class Listener:

    extract_name = re.compile('.*filename=\"(?P<name>.*)\".*').match

    def __init__(self):

        # Make sure it terminate elegantly after Ctr+C
        #signal.signal(signal.SIGINT, self.killed)
        signal.signal(signal.SIGTERM, self.killed)

        self.messenger = None

        self.sta_id = settings.Signatures.NS[0]

    def killed(self, sig, frame):
        self.messenger.close()
        exit(0)

    def monit(self, keep_alive=False):

        while True:
            try:
                config = vws.get_credentials('NS')

                with messaging.RMQclient(config, multi=True) as self.messenger:
                    self.messenger.monit(self.process_message, self.process_timeout, timeout=60)
                    break
            except KeyboardInterrupt:
                return
            except vws.VWSclientError as err:
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
                self.session_has_changed(data)
            elif code == 'schedule':
                self.download_schedule(data)
        # Always acknowledge message
        self.messenger.acknowledge_msg()

    # Process timeout
    def process_timeout(self):
        print('Processing time out')
        self.messenger.send(self.sta_id, 'TEST', 'CC-GSFC', {'test': 'This is a test'})

    # Process message with master code
    def session_has_changed(self, data):
        ses_id = data['session']
        print(f'Session {ses_id} has been updated!')
        # Get client
        client = vws.get_client()
        # Get session information
        rsp = client.get(f'/sessions/{ses_id}')
        if rsp.status_code == HTTPcodes.ok:
            session = Session(rsp.json())
            print(session)
        # Print upcoming sessions
        print(f'\nComing sessions for {self.sta_id}')
        rsp = client.get(f'/sessions/next/{self.sta_id}', params={'days': 14})
        if rsp.status_code == HTTPcodes.ok:
            for data in rsp.json():
                session = Session(data)
                print(session)

    # Download schedule from VOC
    def download_schedule(self, data):
        ses_id = data['session'].lower()
        # Get client
        client = vws.get_client()
        # Get session information (formats: ('skd', 'vex' 'skd|vex' 'vex|skd') default is 'skd|vex' skd first.
        rsp = client.get(f'schedules/{ses_id}', params={'sta_id': self.sta_id, 'format': 'skd'})
        if rsp.status_code == HTTPcodes.ok:
            found = self.extract_name(rsp.headers['content-disposition'])
            if found:
                filename = found['name']
                path = os.path.join(settings.Folders.schedules, filename)
                with open(path, 'wb') as f:
                    f.write(rsp.content)

                print(f'{filename} has been downloaded!')
                # You could add code to process new schedule


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser( description='Station Listener' )
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('code')
    parser.add_argument('session', nargs='?')

    args = settings.init(parser.parse_args())

    Listener().monit(keep_alive=True)


