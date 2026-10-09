"""Automação por intervalos com key determinística: tick deve ser executado periodicamente."""
import json, time
from .models import new_id

def tick(store, engine, now=None):
    now = int(now if now is not None else time.time())
    submitted = []
    for schedule in store.due_schedules(now):
        slot = int(schedule['next_run_at'])
        period = int(schedule['every_seconds'])
        # Salta ocorrências atrasadas sem tempestade após reboot
        next_run = slot + (max(0,(now-slot)//period)+1)*period
        if store.advance_schedule(schedule['id'],slot,next_run):
            data = json.loads(schedule['input_json'])
            job_id = engine.submit(schedule['job_type'],data['text'],
                                   idempotency_key='schedule:%s:%s'%(schedule['id'],slot))
            submitted.append(job_id)
    return submitted
