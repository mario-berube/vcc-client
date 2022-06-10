import argparse
import sys

parser = argparse.ArgumentParser(description='Station Listener')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-start', help='start monitoring', action='store_true')
group.add_argument('-stop', help='stop monitoring', action='store_true')


args, _ = parser.parse_known_args()
if args.stop:
    print('Stop')
elif args.start:
    parser = argparse.ArgumentParser(description='Station Listener')
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('-start', help='start monitoring', action='store_true', required=False)
    print('Start')
    args = parser.parse_args()
    print(args.config)
