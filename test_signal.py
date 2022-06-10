import sys
import signal
import time


def kill_it(sig, dummy):
    sys.exit(0)


def main():
    while True:
        time.sleep(1)
        print('Hello')



if __name__ == '__main__':

    import sys

    signal.signal(signal.SIGUSR2, kill_it)

    sys.exit(main())
