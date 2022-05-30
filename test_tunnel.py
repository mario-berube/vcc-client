import time
import signal
import logging
from vcc.vws import get_client
from vcc import settings

killed = False

def kill(sig, frame):
    global killed
    killed = True

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Station Listener' )
    parser.add_argument('-c', '--config', help='config file', required=True)

    args = settings.init(parser.parse_args())


    api = get_client(keep_alive=True)
    signal.signal(signal.SIGINT, kill)
    signal.signal(signal.SIGTERM, kill)

    logging.getLogger("requests").setLevel(logging.CRITICAL)
    logging.getLogger("requests").propagate = False

    while True:
        print('Testing', api.welcome())
        if killed:
            api.close()
            break
        time.sleep(1)
