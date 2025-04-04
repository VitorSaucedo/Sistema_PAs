from django.urls import path
from . import views

app_name = 'pam'

urlpatterns = [
    path('', views.office_view, name='office_view'),
    path('office-admin/', views.admin_office_view, name='admin_office_view'),
]