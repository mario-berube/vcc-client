import os.path
from collections import defaultdict

from master import COLUMNS
from vcc import settings, signature, json_decoder
from vcc.vws import get_client

import sys


def test_codes():
    # Get DBC codes
    client = get_client()
    secret, headers = signature.make('CC')
    rsp = client.get('/catalog/dbc_codes', headers=headers)
    codes = [item['code'].strip() for item in json_decoder(rsp.json())]

    missing = defaultdict(list)
    # Read master file
    folder = '/Volumes/ExtraStorage/IVSDATA/masters'
    for year in range(1979, 2023):
        for code in ['', '-int', '-vgos']:
            path = os.path.join(folder, f'master{year % 100:02d}{code}.txt')
            if os.path.exists(path):
                print(path)
                with open(path) as master:
                    for line in master:
                        if line.startswith('|'):
                            data = dict(zip(COLUMNS, list(map(str.strip, line.strip(' \n|').split('|')))))
                            if data['db_code'] not in codes:
                                missing[data['db_code']].append((data['code'], year))

    for code, sessions in missing.items():
        print(code, sessions)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)

    args = settings.init(parser.parse_args())

    test_codes()
