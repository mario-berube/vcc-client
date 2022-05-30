import re
from datetime import datetime, timedelta

from master import COLUMNS, UNUSED, TYPES
from vcc import signature, VCCError
from vcc.vws import get_client


def update_master(path):
    header = re.compile(r'\s*(?P<year>\d{4})\sMULTI-AGENCY (?P<type>INTENSIVES|VGOS)? ?SCHEDULE')
    now = datetime.utcnow()

    # Read master file
    sessions = {}
    with open(path) as master:
        for line in master:
            if not line.startswith('|'):
                if info := header.match(line):
                    # Read multi agency line
                    year, session_type = info.group('year'), TYPES.get(info.group('type'), 'standard')
            else:
                data = dict(zip(COLUMNS, list(map(str.strip, line.strip(' \n|').split('|')))))
                start = datetime.strptime(f'{year}{data["date"]} {data["time"]}', '%Y%b%d %H:%M')
                if (start + timedelta(hours=float(data['duration']))) > now:
                    # Clean some unused data
                    data = {key: value for key, value in data.items() if key not in UNUSED}
                    sessions[data['code']] = dict(**data, **{'start': start, 'type': session_type})

    # Post data to VCC
    try:
        client = get_client()
        headers = signature.make('CC')
        rsp = client.post('/sessions', data=sessions, headers=headers)
        if not rsp or not signature.validate(rsp):
            raise VCCError(rsp.text)
        for ses_id, status in rsp.json().items():
            print(ses_id, status)
    except VCCError as exc:
        print(str(exc))
