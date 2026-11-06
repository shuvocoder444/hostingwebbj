from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.ticket_list_view, name='ticket_list'),
    path('new/', views.ticket_create_view, name='ticket_create'),
    path('<uuid:ticket_id>/', views.ticket_detail_view, name='ticket_detail'),
    path('attachments/<uuid:attachment_id>/download/', views.ticket_attachment_download_view, name='ticket_attachment_download'),
]

