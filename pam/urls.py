from django.urls import path
from . import views

app_name = 'pam'

urlpatterns = [
    # Views principais
    path('', views.office_view, name='office_view'),
    path('office-admin/', views.admin_office_view, name='admin_office_view'),
    
    # Autenticação
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # View Unificada
    path('unified-management/', views.unified_management_view, name='unified_management'),
    
    # Gerenciamento para Superusers
    path('manage-employees/', views.manage_employees_view, name='manage_employees'),
    path('manage-rooms/', views.manage_rooms_view, name='manage_rooms'),
    path('manage-islands/', views.manage_islands_view, name='manage_islands'),
    path('manage-workstations/', views.manage_workstations_view, name='manage_workstations'),
    
    # API para filtros dinâmicos
    path('get-islands-by-room/<int:room_id>/', views.get_islands_by_room, name='get_islands_by_room'),
    
    # Operações de exclusão
    path('delete-room/<int:room_id>/', views.delete_room_view, name='delete_room'),
    path('delete-island/<int:island_id>/', views.delete_island_view, name='delete_island'),
    path('delete-workstation/<int:workstation_id>/', views.delete_workstation_view, name='delete_workstation'),
    
    # URLs AJAX
    path('office-admin/add-room-ajax/', views.add_room_ajax_view, name='add_room_ajax'),
    path('office-admin/list-rooms-ajax/', views.list_rooms_ajax_view, name='list_rooms_ajax'),
    path('office-admin/remove-room-ajax/<int:room_id>/', views.remove_room_ajax_view, name='remove_room_ajax'),
    
    # Toggle Periféricos
    path('toggle-peripheral/<int:workstation_id>/', views.toggle_peripheral_view, name='toggle_peripheral'),
]