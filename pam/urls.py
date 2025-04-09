from django.urls import path
from . import views

app_name = 'pam'

urlpatterns = [
    path('', views.office_view, name='office_view'),
    path('office-admin/', views.admin_office_view, name='admin_office_view'),
    # URLs AJAX
    path('office-admin/add-room-ajax/', views.add_room_ajax_view, name='add_room_ajax'),
    path('office-admin/list-rooms-ajax/', views.list_rooms_ajax_view, name='list_rooms_ajax'),
    path('office-admin/remove-room-ajax/<int:room_id>/', views.remove_room_ajax_view, name='remove_room_ajax'),
]