from django.urls import path
from . import views

app_name = 'pam'

urlpatterns = [
    path('', views.home, name='home'),
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/new/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('employees/<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='employee_delete'),
    path('workstations/', views.WorkstationListView.as_view(), name='workstation_list'),
    path('workstations/new/', views.WorkstationCreateView.as_view(), name='workstation_create'),
    path('workstations/<int:pk>/edit/', views.WorkstationUpdateView.as_view(), name='workstation_update'),
    path('workstations/<int:pk>/delete/', views.WorkstationDeleteView.as_view(), name='workstation_delete'),
]