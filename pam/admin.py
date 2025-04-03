from django.contrib import admin
from .models import Employee, Workstation

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name', 'id')
    list_filter = ('created_at',)

@admin.register(Workstation)
class WorkstationAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'employee', 'monitor', 'keyboard', 'mouse', 'mousepad', 'headset')
    list_filter = ('category', 'monitor', 'keyboard', 'mouse', 'mousepad', 'headset')
    search_fields = ('employee__name', 'employee__employee_id')
    raw_id_fields = ('employee',)
