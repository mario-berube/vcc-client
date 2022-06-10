import os

from psutil import Process, process_iter
import signal

def main():

    import argparse

    parser = argparse.ArgumentParser( description='Station Listener' )
    parser.add_argument('cmd')

    args = parser.parse_args()

    my_pid = os.getpid()
    for prc in process_iter(attrs=['pid', 'name', 'cmdline']):
        if prc.info['name'] == 'Python':
            print(prc.info['pid'], prc.info['cmdline'])
        if prc.info['pid'] != my_pid and prc.info['cmdline'] and args.cmd in prc.info['cmdline']:
            print('Found', prc.info['pid'])
            try:
                Process(prc.info['pid']).send_signal(signal.SIGUSR2)
                killed = f'Successfully killed process for queue {prc.info["name"]}'
            except Exception as err:
                killed = f'Failed trying to kill process for queue {prc.info["name"]} {prc.info["pid"]}. [{str(err)}]'

            print(killed)

    return 0

if __name__ == '__main__':

    import sys

    sys.exit(main())
