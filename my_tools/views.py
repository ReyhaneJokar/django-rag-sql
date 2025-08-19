from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
import json
from .registry import TOOLS
from .tools import chart_detector, chart_renderer
from core.models import ConnectionConfig
from core.views import conn_str_for, connect_db
from django.shortcuts import get_object_or_404

def tools_list(request):
    if request.method != "GET":
        return HttpResponseBadRequest()
    return JsonResponse({"tools": list(TOOLS.values())})

@csrf_exempt
def tools_call(request):
    if request.method != "POST":
        return HttpResponseBadRequest()
    payload = json.loads(request.body)
    tool = payload.get("tool")
    conn_id = payload.get("conn_id")
    input_data = payload.get("input", {})
    conn = get_object_or_404(ConnectionConfig, pk=conn_id)
    engine = connect_db(conn_str_for(conn))
    if tool == "chart_detector":
        res = chart_detector(engine, input_data.get("question",""))
        return JsonResponse({"result": res})
    if tool == "chart_renderer":
        res = chart_renderer(engine, input_data.get("sql"), input_data.get("plot_type"), input_data.get("limit_rows",200))
        return JsonResponse({"result": res})
    return JsonResponse({"error":"unknown tool"}, status=400)
