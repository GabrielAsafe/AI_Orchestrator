"""Router puro e scheduler determinístico com decision trace."""
from .models import Requirements

CAPABILITIES = {
    'generic_text': ['generic_text'],
    'summarize': ['summarize|generic_text'],
    'classify': ['classify|generic_text'],
    'extract': ['generic_text'],
    'iot_intent': ['iot_intent|generic_text'],
    'coding_patch': ['coding', 'patch_generation'],
}

def requirements_for(job_type):
    if job_type not in CAPABILITIES:
        raise ValueError('Job type desconhecido: ' + str(job_type))
    return Requirements(required_capabilities=list(CAPABILITIES[job_type]))

def has_capabilities(spec, requirements):
    have = set(spec.capabilities)
    return all(any(option in have for option in expression.split('|'))
               for expression in requirements.required_capabilities)

def select_worker(registry, requirements):
    trace, candidates = [], []
    for spec in registry.specs.values():
        health = registry.health[spec.id]
        reason = None
        if not spec.enabled:
            reason = 'disabled'
        elif health.status not in ('HEALTHY', 'DEGRADED', 'BUSY'):
            reason = 'unhealthy:' + health.status
        elif not has_capabilities(spec, requirements):
            reason = 'missing_capability'
        elif requirements.max_context and spec.context_limit < requirements.max_context:
            reason = 'insufficient_context'
        elif health.active_jobs >= spec.max_parallel:
            reason = 'no_slot'
        elif requirements.preferred_worker and not requirements.allow_fallback and spec.id != requirements.preferred_worker:
            reason = 'fallback_denied'
        if reason:
            trace.append({'worker': spec.id, 'eligible': False, 'reason': reason})
        else:
            candidates.append(spec)
            trace.append({'worker': spec.id, 'eligible': True, 'reason': 'eligible'})
    # Preferred -> healthy -> performance -> normalized occupancy -> ID
    candidates.sort(key=lambda spec: (
        0 if spec.id == requirements.preferred_worker else 1,
        0 if registry.health[spec.id].status == 'HEALTHY' else 1,
        -spec.performance_tier,
        registry.health[spec.id].active_jobs / spec.max_parallel,
        spec.id))
    return (candidates[0] if candidates else None), trace
