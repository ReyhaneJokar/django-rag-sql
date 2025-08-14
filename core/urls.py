from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('connections/', views.connections_view, name='connections'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('chat/', views.chat_view, name='chat'),
    path('chat/prompt_update/', views.update_custom_prompt, name='update_custom_prompt'),
    path('table/<str:table_name>/', views.table_list,   name='table_list'),
    path('table/<str:table_name>/add/',   views.table_add,    name='table_add'),
    path('table/<str:table_name>/<int:pk>/edit/', views.table_edit,   name='table_edit'),
    path('table/<str:table_name>/<int:pk>/delete/', views.table_delete, name='table_delete'),

]
