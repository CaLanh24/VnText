"""Project a bridge response before logging/rendering it. Never expose full turn history."""
def latest(response):
    data=response.get('structuredContent') or {}
    agent=data.get('agent') or {}
    result=data.get('latest_result') or agent.get('latest_result') or {}
    payload=result.get('payload') or {}
    return {'agent_id':agent.get('agent_id',agent.get('id')), 'session_id':agent.get('session_id'),
            'status':agent.get('status',agent.get('state')), 'last_turn_status':agent.get('last_turn_status'), 'cursor':data.get('cursor',agent.get('cursor')),
            'turn_id':result.get('turn_id',payload.get('turn_id')),
            'result':payload.get('result'), 'is_error':payload.get('is_error',result.get('is_error')), 'error':result.get('error'),
            'structured_available':bool(data)}
