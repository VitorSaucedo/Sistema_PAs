from django import forms
from .models import Workstation, Employee, Room # Import Room

class WorkstationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personalizar as opções do campo 'employee'
        current_instance = self.instance
        current_employee_id = current_instance.employee.id if current_instance and current_instance.employee else None
        workstation_category = current_instance.category if current_instance and current_instance.category else None

        # Obter IDs de todos os funcionários atualmente alocados em *outras* workstations
        occupied_employee_ids = set(
            Workstation.objects.filter(employee__isnull=False)
                             .exclude(pk=current_instance.pk if current_instance else None) # Exclui a workstation atual
                             .values_list('employee_id', flat=True)
        )

        choices = [('', '---------')] # Começa com a opção vazia
        
        # Busca todos os funcionários ordenados por nome
        all_employees = Employee.objects.order_by('name') 

        for emp in all_employees:
            # --- NOVA LÓGICA DE FILTRO ---
            # Verifica se o funcionário pertence ao setor da workstation OU se é o funcionário atual
            include_employee = False
            if workstation_category and emp.sector == workstation_category:
                include_employee = True
            elif emp.id == current_employee_id:
                include_employee = True
            # --- FIM DA NOVA LÓGICA DE FILTRO ---

            if include_employee:
                label = emp.name
                # Adiciona '(Ocupado)' se o funcionário estiver em outra PA
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