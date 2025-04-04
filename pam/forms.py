from django import forms
from .models import Workstation

class WorkstationForm(forms.ModelForm):
    class Meta:
        model = Workstation
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