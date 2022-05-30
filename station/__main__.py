
if __name__ == '__main__':
    import argparse
    from utils import settings
    from station import VLBIstation

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)

    args = settings.init(parser.parse_args())

    station = VLBIstation(args)
    station.exec()

