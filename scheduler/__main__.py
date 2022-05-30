import os

from vcc import settings, signature, VCCError
from vcc.vws import get_client


def upload_schedule_files(path_list):
    try:
        client = get_client()
        files = [('files', (os.path.basename(path), open(path,'rb'), 'text/plain')) for path in path_list]
        _, headers = signature.make('OC')
        rsp = client.post('/schedules', files=files, headers=headers)
        if not rsp or not signature.validate(rsp):
            raise VCCError(f'{rsp.status_code}: {rsp.text}')
        [print(file, result) for file, result in rsp.json().items()]
    except VCCError as exc:
        print(f'Problem uploading {[os.path.basename(path) for path in path_list]} [{str(exc)}]')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('path', help='schedule file', nargs='+')

    args = settings.init(parser.parse_args())

    if not settings.check_privilege('OC'):
        print('Only an Operations Center can modify schedules')
        exit(0)

    upload_schedule_files(args.path)

