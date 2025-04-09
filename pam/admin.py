from django.contrib import admin
from .models import Employee, Workstation, Room, Island

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'sector', 'created_at')
    search_fields = ('name', 'id')
    list_filter = ('sector', 'created_at')
    readonly_fields = ('sector',)  # Torna o campo sector apenas leitura

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)

@admin.register(Island)
class IslandAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'island_number', 'created_at')
    list_filter = ('room',)
    search_fields = ('room__name',)
    list_select_related = ('room',) # Optimize query

@admin.register(Workstation)
class WorkstationAdmin(admin.ModelAdmin):
    list_display = ('id', 'island', 'category', 'sequence', 'employee', 'status', 'monitor', 'keyboard', 'mouse', 'mousepad', 'headset')
    list_filter = ('island__room', 'island', 'category', 'status', 'monitor', 'keyboard', 'mouse', 'mousepad', 'headset')
    search_fields = ('employee__name', 'island__room__name') # Search by room name too
    raw_id_fields = ('employee', 'island',) # Add island to raw_id_fields for better UI with many islands
    list_select_related = ('employee', 'island', 'island__room') # Optimize queries
