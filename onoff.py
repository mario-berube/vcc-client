from datetime import datetime

from vcc import settings, VCCError
from vcc.vws import get_client, signature

onoff_header = ['Source', 'Az', 'El', 'De', 'I', 'P', 'Center', 'Comp', 'Tsys', 'SEFD', 'Tcal_j', 'Tcal_r']


def onoff(path):
    sta_id, _ = settings.Signatures.NS
    now = datetime.utcnow().isoformat()
    data = {'time': now, 'station': sta_id, 'values': []}

    def decode_onoff_record(record):
        info = record.split()
        return {name: info[index] for index, name in enumerate(onoff_header)}

    with open(path) as file:
        for line in file:
            data['values'].append(decode_onoff_record(line[30:].lstrip()))

    # Send data to VCC
    try:
        client = get_client()
        headers = signature.make('NS')
        rsp = client.post('/data/onoff', data=data, headers=headers)
        if not rsp or not signature.validate(rsp):
            raise VCCError(f'onoff {rsp.txt}')
        print(rsp.json())
    except VCCError as exc:
        print(str(exc))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('path', help='onoff data file')

    args = settings.init(parser.parse_args())

    if not settings.check_privilege('NS'):
        print('Only a Network Station can send ONOFF data')
        exit(0)

    onoff(args.path)

