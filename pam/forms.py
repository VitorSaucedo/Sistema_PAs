from django import forms
from .models import Employee, Workstation

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
        }
        labels = {
            'name': 'Nome',
            'employee_id': 'ID do Funcionário',
        }

class WorkstationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        preselected_category = kwargs.pop('preselected_category', None)
        super().__init__(*args, **kwargs)
        if preselected_category:
            self.fields['category'].widget.attrs.update({
                'class': 'form-control',
                'disabled': 'disabled'
            })
            self.fields['category'].initial = preselected_category
            # Garante que o valor será enviado mesmo com o campo desabilitado
            self.fields['category'].disabled = True

    class Meta:
        model = Workstation
        fields = ['category', 'employee', 'monitor', 'keyboard', 'mouse', 'mousepad', 'headset']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'monitor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'keyboard': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mouse': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mousepad': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'headset': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'employee': 'Funcionário',
            'monitor': 'Monitor',
            'keyboard': 'Teclado',
            'mouse': 'Mouse',
            'mousepad': 'Mousepad',
            'headset': 'Fone de Ouvido',
        }