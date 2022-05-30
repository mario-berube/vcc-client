from collections import namedtuple
from datetime import datetime, timedelta
import os

from PyQt5.QtWidgets import QTextEdit, QCheckBox, QPushButton, QGridLayout, QGroupBox
from PyQt5.QtGui import QFont, QColor
from requests import codes as HttpCodes

from utils import settings
from processes import Timer, Post

# Declaring namedtuple()
Action = namedtuple('Action',['start','event','data'])


class Processor(QTextEdit):
    onoff_header = ['Source', 'Az', 'El', 'De', 'I', 'P', 'Center', 'Comp', 'Tsys', 'SEFD', 'Tcal_j', 'Tcal_r']
    redColor = QColor(255, 0, 0)
    blackColor = QColor(0, 0, 0)

    def __init__(self, sta_id, boss):
        super().__init__()

        self.setReadOnly(True)
        self.setFont(QFont('Courier New'))

        self.boss = boss
        self.sta_id, self.ses_id, self.halted = sta_id.lower(), 'unknown', False
        self.actions, self.to_do, self.next_action = [], {}, None

        self.auto_loaded = {}
        self.log = None

        self.add_text(';', 'waiting')

        self.timer = Timer(self.process_timeout)
        self.timer.start()

    def open_log(self, session):
        self.close_log()
        path = os.path.join(settings.Folders.logs, f'{session}{self.sta_id}.log')
        self.log = open(path, 'a+')

    def close_log(self):
        if self.log:
            self.log.close()
            self.log = None

    # Stop timer
    def stop(self):
        self.timer.stop()

    # Insert the action into the to_do list
    def do(self, action, data=''):
        self.to_do[action if hasattr(self, action) else 'unknown'] = (action, data)

    # Process timeout
    def process_timeout(self, utc):

        for key in list(self.to_do.keys()):
            (action, data) = self.to_do.pop(key, ("unknown", None))
            text = ', '.join([f'{k}={val}' for k, val in data.items()]) if isinstance(data, dict) else data
            if action != 'auto':
                self.add_text(';', f'{action}{" " if text else ""}{text}')
            getattr(self, key)(action, data, utc)

        # Execute commands from schedule
        if self.next_action and utc > self.next_action.start:
            action = self.next_action
            self.next_action = self.actions.pop(0) if self.actions else None

            if not self.halted:
                getattr(self, action.event)(action.event, action.data, utc)

    def check_master(self):
        pass

    def command(self, cmd):
        pass

    def add_text(self, separator, msg, flag=False):
        record = f'{datetime.utcnow().isoformat(sep=" ", timespec="milliseconds")}{separator}{msg}'
        self.setTextColor(self.redColor if flag else self.blackColor)
        self.append(record)
        if self.log:
            print(record, file=self.log)

    def decode_onoff_record(self, line):
        data = line.split()
        return {name: data[index] for index, name in enumerate(self.onoff_header)}

    def onoff(self, action, which, utc):
        which = which if which in ['before', 'after'] else 'before'
        self.add_text(':', f'{action}')

        path = os.path.join(settings.Folders.data, f'onoff.{which}')
        data = {'time': utc.isoformat(), 'station': self.sta_id, 'values':[]}

        with open(path) as file:
            for line in file:
                self.add_text('#onoff#VAL ', line[30:].rstrip())
                data['values'].append(self.decode_onoff_record(line[30:].lstrip()))

        # Send data to VLBI Data Center web service
        self.post = Post('onoff/', data)
        self.post.on_finish(self.onoff_submitted)
        self.post.start()

    def unknown(self, action, data, utc):
        self.add_text(':', f'{action} unknown command')

    def msg(self, action, data):
        data['station'] = self.sta_id  # Add station id to data
        # Send message to VLBI Data Center using messenger from boss
        self.boss.messenger.send(self.sta_id, action, 'msg', data)

    def onoff_submitted(self, response, error):
        if error:
            self.add_text(':', error)
        elif not response or response.status_code != HttpCodes.ok:
            self.add_text(':', 'onoff records not accepted.')
        elif 'updated' in response.json():
            self.add_text(':', 'onoff records updated')
        else:
            self.add_text(':', f'problem submitting onoff records. {response.text}')

    def urgent(self, action, data, utc):
        text = ', '.join([f'{k}={val}' for k, val in data.items()]) if isinstance(data, dict) else data
        self.add_text(':', f'{action}={text}')
        self.msg('urgent', {'msg': data})

    def source(self, action, data, utc):
        self.add_text(':', f'{action}={data}')
        self.msg('sta_info', {'status': f'source={data.split(",")[0]}', 'session': self.ses_id})

    def scan_name(self, action, data, utc):
        scan, scan_id = data.split('|')
        self.add_text(':', f'{action}={scan}')
        self.msg('sta_info', {'status': f'scan_name={scan.split(",")[0]}', 'scan_id': scan_id, 'session': self.ses_id})

    def scan_end(self, action, data, utc):
        self.add_text(':', f'{action}={data}')
        self.msg('sta_info', {'status': f'scan_end={data}', 'session': self.ses_id})

    def ready(self, action, data, utc):
        self.add_text(':', f'{action}')
        self.msg('sta_info', {'status': 'schedule ready', 'session': self.ses_id})

    def terminate(self, action, data, utc):

        if self.next_action:
            self.next_action = None
        self.add_text(':', f'{action}')
        self.msg('sta_info', {'status': 'schedule terminated', 'session': self.ses_id})
        self.close_log()

        self.plog('plog', self.ses_id, utc)


    def plog(self, action, session, utc):
        filename = f'{session}{self.sta_id}.log'.lower()
        path = os.path.join(settings.Folders.logs, filename)
        if os.path.exists(path):
            self.add_text(':', f'submit {filename}')
            # Send log to VLBI Data Center web service
            files = {'file': (filename, open(path,'rb'))}
            self.post = Post('log/', files=files)
            self.post.on_finish(self.log_submitted)
            self.post.start()
        else:
            self.add_text(':', f'{filename} does not exist', flag=True)

    def log_submitted(self, response, error):
        if error:
            self.add_text(':', error, flag=True)
        elif not response or response.status_code != HttpCodes.ok:
            self.add_text(':', 'log not accepted.', flag=True)
        elif 'accepted' in response.json():
            self.add_text(':', f'log uploaded to VOC')
        else:
            self.add_text(':', f'problem submitting log. {response.text}', flag=True)

    def halt(self, action, data, utc):
        self.add_text(':', f'{action}')
        self.halted = True
        self.msg('sta_info', {'status': 'schedule halted', 'session': self.ses_id})

    def resume(self, action, data, utc):
        self.add_text(':', f'{action}')
        self.halted = False
        self.msg('sta_info', {'status': 'schedule resume', 'session': self.ses_id})

    def decode_scan(self, line, sources):
        start, src_name, scan_name, dur, stations = line.split('|')
        src_name = src_name.split('=')[-1]
        scan_name = scan_name.split('=')[-1]
        duration = int(dur.split('=')[-1])
        stations = stations.lower().split()
        start = datetime.strptime(start.strip(), '%Y-%m-%d %H:%M:%S')
        end = start + timedelta(seconds=duration)
        src = sources[src_name]
        scan = f'{scan_name},{self.ses_id},{self.sta_id},{duration},{duration}'
        status = f'{scan_name},ok'

        return start, end, src, scan, status, stations

    def auto(self, action, data, utc):
        session = data['session']
        if utc < data['time']:
            if session not in self.auto_loaded:
                self.auto_loaded[session] = True
                self.add_text(':', f'{session} will be loaded at {data["time"].strftime("%j-%H:%M")}')
            self.do(action, data)
        else:
            self.load('auto', session, utc)

    def load(self, action, session, utc):

        self.add_text(':', f'{action}={session}')
        session = session.lower()
        self.open_log(session)

        self.actions = []
        for ext in ['.skd', '.vex']:
            path = os.path.join(settings.Folders.schedules, f'{session}{ext}')
            if os.path.exists(path):
                self.ses_id = session
                sources = {}
                scan_id = 0
                now, src_time = datetime.utcnow(), None
                expr_start = now
                with open(path) as file:
                    for line in file:
                        key, info = line.split(':', 1)
                        if key == 'SESSION':
                            expr_start = datetime.strptime(line.split('|')[1], '%Y-%m-%d %H:%M:%S')
                        elif key == 'SOURCE':
                            code, name, rad, dec, epoch = info[1:10], info[10:19], info[19:35], info[36:55], info[55:62]
                            name = code.strip() if name.startswith('$') else name.strip()
                            rad, dec, epoch = float(rad.replace(' ', '')), float(dec.replace(' ', '')), epoch.strip()
                            sources[name] = f'{name},{rad:.2f},{dec:.2f},{epoch}'
                        elif key == 'SCAN':
                            start, end, src, scan, status, stations = self.decode_scan(info, sources)
                            if self.sta_id in stations:
                                scan_id += 1
                                if start > now:
                                    src_time = src_time if src_time else start - timedelta(seconds=60)
                                    self.actions.append(Action(src_time, 'source', src))
                                    self.actions.append(Action(start, 'scan_name', f'{scan}|{scan_id}'))
                                    self.actions.append(Action(end, 'scan_end', status))
                                    scr_time = end

                    # Run onoff if automated
                    print('ADDING READY', expr_start, now)
                    if expr_start > now:
                        start = max(now, expr_start-timedelta(seconds=120))
                        print('ADDED READY')
                        self.actions.insert(0, Action(start, 'ready', ''))
                    if action == 'auto':
                        print('AUTO', expr_start - timedelta(seconds=300), now)
                        if expr_start - timedelta(seconds=300) > now:
                            self.actions.insert(0, Action(utc, 'onoff', 'before'))
                        end += timedelta(seconds=10)
                        self.actions.append(Action(end, 'onoff', 'after'))
                    # Add terminate 5 second after last
                    end += timedelta(seconds=5)
                    self.actions.append(Action(end, 'terminate', ''))
                    # Activate the processing by setting next_action
                    self.next_action = self.actions.pop(0)
                    print('ACTION 0', len(self.actions), self.actions[0].event, self.actions[0].start)
                    print('ACTION 1', len(self.actions), self.actions[0].event, self.actions[-1].start)
                break
        else:
            self.add_text(':', f'No schedule file for {session}')





