import re

from vcc import signature, VCCError
from vcc.vws import get_client


def update_network(client, path):

    # Extract data from file
    is_station = re.compile(' (?P<code>\w{2}) (?P<name>.{8}) (?P<domes>.{9}) (?P<cdp>.{4}) (?P<description>.+)$').match
    with open(path) as file:
        network = {rec['code']: rec.groupdict() for line in file if (rec := is_station(line))}
    # Set flag for VLBA stations
    vlba = network['Va']['description'] + 'Va'
    network = {sta: dict(**data, **{'is_vlba': sta in vlba}) for (sta, data) in network.items()}

    # Get existing information from VOC
    try:
        client = get_client()
        headers = signature.make('CC')
        rsp = client.get('/stations', headers=headers)
        if not rsp or not signature.validate(rsp):
            raise VCCError(rsp.text)
        old = {data['code']: data for data in rsp.json() if data.pop('updated')}
        if network == old:
            raise VCCError('No changes in network stations')
        added = {code: value for (code, value) in network.items() if old.get(code) != value}
        if added:
            rsp = client.post('/stations', data=added, headers=headers)
            if not rsp or not signature.validate(rsp):
                raise VCCError(rsp.text)
            [print(f'{index:4d} {sta} {status}') for index, (sta, status) in enumerate(rsp.json().items(), 1)]
        for index, sta_id in enumerate([code for code in old if code not in network], 1):
            rsp = client.delete(f'/stations/{sta_id}', headers=headers)
            if not rsp or not signature.validate(rsp):
                raise VCCError(rsp.text)
            print(f'{index:4d} {sta_id} {rsp.json()[sta_id]}')
    except VCCError as exc:
        print(str(exc))


def update_codes(code_type, path):
    (key, name) = {'operations': ('SKED CODES', 'operations'), 'analysis': ('SUBM CODES', 'analysis'),
                   'correlator': ('CORR CODES', 'correlator'), 'dbc': ('DBC CODES', 'dbc_codes')
                   }.get(code_type, (None, None))
    if not key:
        print(f'{code_type} is invalid option')
        return
    # Read file and extract data
    data, in_section = {}, False
    with open(path) as file:
        for line in file:
            if in_section:
                if key in line:
                    break
                code = line.strip().split()[0].strip()
                data[code] = {'code': code, 'description': line.strip()[len(code):].strip()}
            elif key in line:
                in_section = True
    if data:
        try:
            client = get_client()
            headers = signature.make('CC')
            rsp = client.post(f'/catalog/{name}', data=data, headers=headers)
            if not rsp or not signature.validate(rsp):
                raise VCCError(rsp.text)
            print(f'{len([code for code, status in rsp.json().items() if status == "updated"])} '
                  f'of {len(data)} codes where updated')
        except VCCError as exc:
            print(str(exc))
