"""Append-only local JSON events, with atomic creation and retry deduplication.

Immutability is an application rule, not a filesystem retention guarantee.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

class EventConflict(ValueError):
    pass

class CorruptEvent(OSError):
    pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

class EventStore:
    def __init__(self,directory,clock=None):
        self.directory=Path(directory)
        self.staging=self.directory/'.staging'
        self.clock=clock or (lambda:dt.datetime.now(dt.timezone.utc))

    def initialise(self):
        self.staging.mkdir(parents=True,exist_ok=True)

    def _path(self,event_id):
        try: identifier=str(uuid.UUID(event_id))
        except (ValueError,TypeError,AttributeError):raise ValueError('Invalid event ID') from None
        return self.directory/(identifier+'.json')

    def get(self,event_id):
        path=self._path(event_id)
        try: event=json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:return None
        except (ValueError,UnicodeError):raise CorruptEvent('Unreadable event: '+path.name) from None
        try:
            valid=(event['schema_version']==1 and event['event_id']==path.stem and
                   event['type'] in ('answer_observed','observation_retracted') and
                   isinstance(event['payload'],dict) and
                   event['payload_sha256']==hashlib.sha256(canonical(event['payload'])).hexdigest() and
                   dt.datetime.fromisoformat(event['recorded_at']).utcoffset() is not None)
        except (KeyError,TypeError,ValueError,AttributeError):valid=False
        if not valid:raise CorruptEvent('Invalid event: '+path.name)
        return event

    def append(self,event_id,event_type,payload):
        if event_type not in ('answer_observed','observation_retracted') or not isinstance(payload,dict):
            raise ValueError('Invalid event')
        self.initialise();path=self._path(event_id)
        digest=hashlib.sha256(canonical(payload)).hexdigest()
        prior=self.get(path.stem)
        if prior:
            return self._same(prior,event_type,payload)
        event={'schema_version':1,'event_id':path.stem,'type':event_type,
               'recorded_at':self.clock().isoformat(),
               'payload_sha256':digest,'payload':payload}
        # Write outside the reader's glob, then publish using a no-replace hard link.
        fd,temp=tempfile.mkstemp(prefix='pending-',dir=self.staging)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(canonical(event)+b'\n');stream.flush();os.fsync(stream.fileno())
            try:os.link(temp,path)
            except FileExistsError:return self._same(self.get(path.stem),event_type,payload)
            directory_fd=os.open(self.directory,os.O_RDONLY)
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        finally:
            try:os.unlink(temp)
            except FileNotFoundError:pass
        return event

    @staticmethod
    def _same(prior,event_type,payload):
        if prior is None or prior['type']!=event_type or canonical(prior['payload'])!=canonical(payload):
            raise EventConflict('Event ID already used for a different observation')
        return prior

    def all(self):
        if not self.directory.exists():return []
        events=[self.get(path.stem) for path in self.directory.glob('*.json')]
        # Never silently present incomplete progress after a storage race or deletion.
        if any(event is None for event in events):raise CorruptEvent('Event disappeared during read')
        return sorted(events,key=lambda event:(event['recorded_at'],event['event_id']))
