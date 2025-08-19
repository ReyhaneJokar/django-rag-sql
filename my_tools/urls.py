from django.urls import path
from . import views

urlpatterns = [
    path("list/", views.tools_list, name="mcp_tools_list"),
    path("call/", views.tools_call, name="mcp_tools_call"),
]
