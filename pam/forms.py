from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Workstation, Employee, Room, Island

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
        
        # Adiciona campos ocultos que serão usados para processamento
        self.fields['room'] = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Workstation
        fields = ['employee', 'category', 'island', 'monitor', 'keyboard', 'mouse', 'mousepad', 'headset']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'island': forms.Select(attrs={'class': 'form-control'}),
            'monitor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'keyboard': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mouse': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mousepad': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'headset': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'employee': 'Funcionário',
            'category': 'Setor',
            'island': 'Ilha',
            'monitor': 'Monitor',
            'keyboard': 'Teclado',
            'mouse': 'Mouse',
            'mousepad': 'Mousepad',
            'headset': 'Fone de Ouvido'
        }

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da Sala'}),
        }
        labels = {
            'name': 'Nome da Sala'
        }

# We will handle island/workstation counts dynamically in the view/template
# class IslandForm(forms.Form):
#     number_of_workstations = forms.IntegerField(min_value=1, label="Número de Workstations")

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'cpf', 'email', 'phone', 'sector']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Completo'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123.456.789-00'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX'}),
            'sector': forms.Select(attrs={'class': 'form-control'}),
        }

    # Opcional: Adicionar validação customizada para CPF, telefone, etc.
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        # Remover caracteres não numéricos para validação/armazenamento
        cpf_digits = ''.join(filter(str.isdigit, cpf or ''))
        if len(cpf_digits) != 11:
            raise forms.ValidationError("CPF deve conter 11 dígitos.")
        # Adicionar aqui validação de CPF (algoritmo) se desejado
        return cpf # Ou retorna cpf_digits se quiser salvar só números

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_digits = ''.join(filter(str.isdigit, phone or ''))
            if not (10 <= len(phone_digits) <= 11):
                 raise forms.ValidationError("Telefone deve ter 10 ou 11 dígitos (com DDD).")
            # Adicionar formatação aqui se desejar
        return phone # Ou retorna formatado

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome de usuário'}),
        label='Nome de usuário'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Senha'}),
        label='Senha'
    )