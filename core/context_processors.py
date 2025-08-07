from .models import ConnectionConfig

def user_prompt(request):    
    prompt = ""
    try:
        conn_id = request.session.get('connection_id')
        if conn_id:
            cfg = ConnectionConfig.objects.filter(
                pk=conn_id,
                owner=request.user
            ).first()
            if cfg and cfg.custom_prompt:
                prompt = cfg.custom_prompt
    except:
        pass
    return {'user_prompt': prompt}