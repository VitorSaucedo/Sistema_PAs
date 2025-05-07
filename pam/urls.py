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
    path('delete-employee/<int:employee_id>/', views.delete_employee_view, name='delete_employee'),
    
    # URLs AJAX
    path('office-admin/add-room-ajax/', views.add_room_ajax_view, name='add_room_ajax'),
    path('office-admin/list-rooms-ajax/', views.list_rooms_ajax_view, name='list_rooms_ajax'),
    path('office-admin/remove-room-ajax/<int:room_id>/', views.remove_room_ajax_view, name='remove_room_ajax'),
    
    # Toggle Periféricos
    path('toggle-peripheral/<int:workstation_id>/', views.toggle_peripheral_view, name='toggle_peripheral'),
    
    # Atribuir funcionário
    path('assign-employee/<int:workstation_id>/', views.assign_employee_view, name='assign_employee'),
    
    # Remover funcionário
    path('remove-employee/<int:workstation_id>/', views.remove_employee_view, name='remove_employee'),
    
    # Obter funcionários disponíveis
    path('get-available-employees/', views.get_available_employees_view, name='get_available_employees'),
    
    # Histórico e Logs
    path('history/', views.history_view, name='history'),
    path('history/employee/<int:employee_id>/', views.employee_history_view, name='employee_history'),
    path('history/changes/', views.change_log_view, name='change_log'),
    
    # --- NOVAS ROTAS AJAX PARA API CRUD ---
    
    # API CRUD para Funcionários
    path('api/employees/', views.api_employee_list, name='api_employee_list'),
    path('api/employees/<int:employee_id>/', views.api_employee_detail, name='api_employee_detail'),
    path('api/employees/create/', views.api_employee_create, name='api_employee_create'),
    path('api/employees/<int:employee_id>/update/', views.api_employee_update, name='api_employee_update'),
    path('api/employees/<int:employee_id>/delete/', views.api_employee_delete, name='api_employee_delete'),
    
    # API CRUD para Salas
    path('api/rooms/', views.api_room_list, name='api_room_list'),
    path('api/rooms/<int:room_id>/', views.api_room_detail, name='api_room_detail'),
    path('api/rooms/create/', views.api_room_create, name='api_room_create'),
    path('api/rooms/<int:room_id>/update/', views.api_room_update, name='api_room_update'),
    path('api/rooms/<int:room_id>/delete/', views.api_room_delete, name='api_room_delete'),
    
    # API CRUD para Ilhas
    path('api/islands/', views.api_island_list, name='api_island_list'),
    path('api/islands/<int:island_id>/', views.api_island_detail, name='api_island_detail'),
    path('api/islands/create/', views.api_island_create, name='api_island_create'),
    path('api/islands/<int:island_id>/update/', views.api_island_update, name='api_island_update'),
    path('api/islands/<int:island_id>/delete/', views.api_island_delete, name='api_island_delete'),
    
    # API CRUD para Estações de Trabalho
    path('api/workstations/', views.api_workstation_list, name='api_workstation_list'),
    path('api/workstations/<int:workstation_id>/', views.api_workstation_detail, name='api_workstation_detail'),
    path('api/workstations/create/', views.api_workstation_create, name='api_workstation_create'),
    path('api/workstations/<int:workstation_id>/update/', views.api_workstation_update, name='api_workstation_update'),
    path('api/workstations/<int:workstation_id>/delete/', views.api_workstation_delete, name='api_workstation_delete'),
]