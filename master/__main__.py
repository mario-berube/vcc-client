from vcc import settings
from master.session import update_master
from master.viewer import view_session
from master.catalog import update_network, update_codes


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('-s', '--session', required=False)
    parser.add_argument('-m', '--master', action='store_true')
    parser.add_argument('-n', '--network', action='store_true')
    parser.add_argument('-C', '--codes', required=False)
    parser.add_argument('path', help='path to file', nargs='?')

    args = settings.init(parser.parse_args())

    if not settings.check_privilege('CC'):
        print('Only Coordinating center can update master information')
        exit(0)

    if args.session:
        view_session(args.session)
    elif args.master:
        update_master(args.path)
    elif args.network:
        update_network(args.path)
    elif args.codes:
        update_codes(args.codes, args.path)
