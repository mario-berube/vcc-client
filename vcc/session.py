from datetime import datetime, timedelta

from vcc import make_object


class Session:
    def __init__(self, data):
        self.error = False

        self.code = self.name = self.operations = self.analysis = self.correlator = ''
        self.start = datetime.utcnow() + timedelta(days=7)
        self.duration = 1 * 60 * 60
        self.included, self.removed = [], []
        self.schedule, self.db_code, self.type = None, '', 'standard'

        make_object(data, self)

        self.end = self.start + timedelta(seconds=self.duration)

    def __str__(self):
        oc = self.operations.upper() if hasattr(self, 'operations') else 'N/A'
        cor = self.correlator.upper() if hasattr(self, 'correlator') else 'N/A'
        return f'{self.code} {self.start} {self.end} {self.duration} {oc} {cor}'

    def update_schedule(self, data):
        self.schedule = make_object(data) if data else None

    @property
    def network(self):
        return list(map(str.capitalize, self.schedule.observing if self.schedule else self.included))

    def get_status(self):
        now = datetime.utcnow()
        return 'waiting' if now < self.start else 'terminated' if self.end < now else 'observing'

    def total_waiting(self):
         return (self.start - datetime.utcnow()).total_seconds() if self.get_status() == 'waiting' else -1

    def observing_done(self, ):
        return (datetime.utcnow() - self.start).total_seconds()

    @property
    def sched_version(self):
        return f'V{self.schedule.version:.0f} {self.schedule.updated.strftime("%Y-%m-%d %H:%M")}' \
            if self.schedule else 'None'