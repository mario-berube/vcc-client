from tools import get_credentials
from utils import settings, messaging

class Example:

    def __init__(self, credentials):
        self.client = messaging.RMQclient(credentials, multi=False)
        self.client.connect()
        self.client.connect_publisher()

        self.sta_id = settings.Identity.code

    def send(self, code, data):
        self.client._send(self.sta_id, code, 'msg', data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Station Listener' )
    parser.add_argument('-c', '--config', help='config file', required=True)

    args = settings.init(parser.parse_args())

    credentials = get_credentials()

    publisher = Example(credentials)
    publisher.send('sta_info', {'status': f'source=0016+731', 'session': 'r11021'})
    publisher.send('sta_info', {'status': f'scan_name=291-1700a', 'session': 'r11021'})
    publisher.send('sta_info', {'status': f'schedule ready', 'session': 'r11021'})
    publisher.send('sta_info', {'status': f'schedule terminate', 'session': 'r11021'})

