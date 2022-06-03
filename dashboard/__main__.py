
def main():
    import argparse
    from vcc import settings
    from dashboard import Dashboard
    from dashboard.picker import SessionPicker

    parser = argparse.ArgumentParser(description='Dashboard')
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('-d', '--dashboard', help= 'start dashboard', required=False)
    parser.add_argument('-p', '--picker', help='start session picker', required=False)

    args = settings.init(parser.parse_args())

    if args.dashboard:
        dashboard = Dashboard(args.dashboard)
        dashboard.exec()
    elif args.picker:
        picker = SessionPicker(args.picker)
        picker.exec()


if __name__ == '__main__':
    import sys

    sys.exit(main())
