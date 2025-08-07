from .models import ConnectionConfig

def user_prompt(request):
    prompt = ""
    if request.user.is_authenticated:
        conn_id = request.session.get('connection_id')
        if conn_id:
            try:
                conn = ConnectionConfig.objects.get(pk=conn_id, owner=request.user)
                prompt = conn.custom_prompt or ""
            except ConnectionConfig.DoesNotExist:
                pass
    return {'user_prompt': prompt}
