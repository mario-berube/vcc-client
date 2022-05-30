from datetime import datetime

from vcc import settings, signature, json_decoder, VCCError
from vcc.vws import get_client, get_inbox_credentials
from vcc.messaging import RMQclient, RMQclientException


def test_messaging(group_id, session=None):
    print('Test on message communication ', end = '')
    try:
        if not hasattr(settings.Signatures, group_id):
            raise VCCError(f'{group_id} not in configuration file')
        with RMQclient(get_inbox_credentials(group_id, session)) as client:
            rsp = client.alive()
            print(f'is successful! Delay is {rsp:.3f} seconds')
    except (VCCError, RMQclientException) as exc:
        print(f'fails! {str(exc)}')


def show_session(code):
    try:
        for group_id in ['CC', 'OC', 'AC', 'CO', 'NS', 'DB']:
            if hasattr(settings.Signatures, group_id):
                break
        else:
            raise VCCError('No valid groups in configuration file')
        client = get_client()
        rsp = client.get(f'/sessions/{code}', headers=signature.make(group_id))
        if not rsp or not signature.validate(rsp):
            raise VCCError(rsp.text)
        data = json_decoder(rsp.json())
        start = data['start']
        db_name = f'{start.strftime("%y%b%d")}{data["db_code"]}'.upper()
        included = f'{"".join(list(map(str.capitalize, data["included"])))}'
        #removed = list(map(str.capitalize, data['removed']))
        removed = f' -{"".join(list(map(str.capitalize, data["removed"])))}' if data['removed'] else ''
        print(f'{data["code"].upper()} {data["name"].upper()}', end = ' ')
        print(f'{start.strftime("%Y-%m-%d %H:%M")} {included}{removed}', end = ' ')
        print(f'{data["operations"].upper()} {data["correlator"].upper()}', end = ' ')
        print(f'{data["analysis"].upper()} {db_name}')
        return
    except VCCError as exc:
        print(f'Failed to get information for {code}! [{str(exc)}]')


# Test if user is valid
def is_valid_user(group_id):
    try:
        if not hasattr(settings.Signatures, group_id):
            raise VCCError(f'{group_id} not in configuration file')
        client = get_client()
        rsp = client.get('/users/valid', headers=signature.make(group_id))
        if not rsp or not signature.validate(rsp):
            raise VCCError(f'invalid response {rsp.text}')
        print('User is valid')
    except VCCError as exc:
        print(f'Failed validate user {str(exc)}')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser( description='Schedule Viewer' )
    parser.add_argument('-c', '--config', help='config file', required=True)
    parser.add_argument('-m', '--messaging', help='test messaging system', required=False)
    parser.add_argument('-d', '--dashboard', help='get dashboard queue name', required=False)
    parser.add_argument('-s', '--session', help='session code', required=False)
    parser.add_argument('-v', '--validate', help='group', required=False)

    args = settings.init(parser.parse_args())


    if args.messaging:
        test_messaging(args.messaging)
    elif args.dashboard:
        test_messaging('DB', session=args.dashboard)
    elif args.validate:
        is_valid_user(args.validate)
    elif args.session:
        show_session(args.session)

