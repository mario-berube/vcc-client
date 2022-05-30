if __name__ == '__main__':
    import argparse
    from utils import settings
    from listener import VCHlistener

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)

    args = settings.init(parser.parse_args())

    listener = VCHlistener(args)
    listener.exec()
