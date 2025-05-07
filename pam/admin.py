from django.contrib import admin
from .models import Employee, Room, Island, Workstation

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'sector')
    search_fields = ('name',)
    list_filter = ('sector',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Island)
class IslandAdmin(admin.ModelAdmin):
    list_display = ('room', 'island_number', 'category')
    list_filter = ('room',)
    search_fields = ('room__name', 'island_number')

@admin.register(Workstation)
class WorkstationAdmin(admin.ModelAdmin):
    list_display = ('get_display_name', 'category', 'status', 'employee')
    list_filter = ('status', 'category', 'island__room')
    search_fields = ('employee__name', 'category', 'sequence')
    raw_id_fields = ('employee', 'island',) # Add island to raw_id_fields for better UI with many islands
    list_select_related = ('employee', 'island', 'island__room') # Optimize queries
    
    def get_display_name(self, obj):
        if obj.island:
            return f"Sala {obj.island.room.name}, Ilha {obj.island.island_number}, PA {obj.sequence}"
        return f"{obj.get_category_display()} {obj.sequence}"
    get_display_name.short_description = "Estação"
