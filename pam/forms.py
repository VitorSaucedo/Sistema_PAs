from django import forms
from .models import Workstation, Employee, Room # Import Room

class WorkstationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize employee choices to show (Ocupado)
        current_employee = self.instance.employee # Employee currently assigned to this specific workstation
        
        # Get IDs of all employees currently assigned to *any* workstation
        occupied_employee_ids = set(
            Workstation.objects.filter(employee__isnull=False)
                             .exclude(pk=self.instance.pk) # Exclude the current workstation being edited
                             .values_list('employee_id', flat=True)
        )

        choices = [('', '---------')] # Start with empty choice
        
        # Use select_related('workstation_set') might be too heavy, simple iteration is fine for moderate numbers
        for emp in Employee.objects.order_by('name'):
            label = emp.name
            # Check if employee is occupied elsewhere OR if they are the current employee (to avoid showing occupied for self)
            if emp.id in occupied_employee_ids:
                 label = f"{emp.name} (Ocupado)"
            
            choices.append((emp.id, label))
            
        self.fields['employee'].choices = choices

    class Meta:
        model = Workstation
        # Note: 'employee' field is customized in __init__
        fields = ['status', 'employee', 'monitor', 'keyboard', 'mouse', 'headset']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'monitor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'keyboard': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mouse': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'headset': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'status': 'Status',
            'employee': 'Funcionário',
            'monitor': 'Monitor',
            'keyboard': 'Teclado',
            'mouse': 'Mouse',
            'headset': 'Fone de Ouvido'
        }

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da Nova Sala'})
        }
        labels = {
            'name': 'Nome da Sala'
        }

# We will handle island/workstation counts dynamically in the view/template
# class IslandForm(forms.Form):
#     number_of_workstations = forms.IntegerField(min_value=1, label="Número de Workstations")