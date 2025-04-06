from django.shortcuts import render, redirect, HttpResponse
from django.db import transaction
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from .models import Workstation, Employee
from .forms import WorkstationForm
from django.http import JsonResponse

def is_admin(user):
    return user.is_authenticated and user.is_staff
def office_view(request):
    """Visualização pública do escritório"""
    # Configura headers para evitar cache
    response = HttpResponse()
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    # Busca dados frescos do banco (com lock para evitar race conditions)
    with transaction.atomic():
        # Garante que existam 12 workstations para cada setor
        for category in ['INSS', 'SIAPE_LEO', 'SIAPE_DION', 'ESTAGIO']:
            existing = Workstation.objects.filter(category=category).order_by('sequence')
            existing_sequences = set(ws.sequence for ws in existing)
            
            # Cria workstations faltantes
            for i in range(1, 13):
                if i not in existing_sequences:
                    Workstation.objects.get_or_create(
                        category=category,
                        sequence=i,
                        defaults={'status': 'UNOCCUPIED'}
                    )
        
        # Busca todas as 12 workstations de cada setor
        inss_workstations = list(Workstation.objects.select_for_update()
                               .filter(category='INSS')
                               .order_by('sequence'))
        siae_leo_workstations = list(Workstation.objects.select_for_update()
                                   .filter(category='SIAPE_LEO')
                                   .order_by('sequence'))
        siae_dion_workstations = list(Workstation.objects.select_for_update()
                                    .filter(category='SIAPE_DION')
                                    .order_by('sequence'))
        estagio_workstations = list(Workstation.objects.select_for_update()
                                  .filter(category='ESTAGIO')
                                  .order_by('sequence'))
    
    # Organiza cada grupo em colunas 6x2 (de baixo para cima)
    def organize_columns(workstations):
        columns = [[], []]
        for i, ws in enumerate(workstations):
            columns[i // 6].append(ws)
        return [list(reversed(col)) for col in columns]
    
    inss_columns = organize_columns(inss_workstations)
    siae_leo_columns = organize_columns(siae_leo_workstations)
    siae_dion_columns = organize_columns(siae_dion_workstations)
    estagio_columns = organize_columns(estagio_workstations)
    
    return render(request, 'pam/office_view.html', {
        'inss_columns': inss_columns,
        'siae_leo_columns': siae_leo_columns,
        'siae_dion_columns': siae_dion_columns,
        'estagio_columns': estagio_columns
    })

@user_passes_test(is_admin)
def admin_office_view(request):
    """Visualização administrativa do escritório"""
    # Garante que existam 12 workstations para cada setor
    for category in ['INSS', 'SIAPE_LEO', 'SIAPE_DION', 'ESTAGIO']:
        existing = Workstation.objects.filter(category=category).order_by('sequence')
        existing_sequences = set(ws.sequence for ws in existing)
        
        # Cria workstations faltantes
        for i in range(1, 13):
            if i not in existing_sequences:
                Workstation.objects.get_or_create(
                    category=category,
                    sequence=i,
                    defaults={'status': 'UNOCCUPIED'}
                )
    
    # Busca todas as 12 workstations de cada setor
    inss_workstations = Workstation.objects.filter(category='INSS').order_by('sequence')
    siae_leo_workstations = Workstation.objects.filter(category='SIAPE_LEO').order_by('sequence')
    siae_dion_workstations = Workstation.objects.filter(category='SIAPE_DION').order_by('sequence')
    estagio_workstations = Workstation.objects.filter(category='ESTAGIO').order_by('sequence')
    
    error_message = None
    
    if request.method == 'POST':
        print("Dados POST recebidos:", request.POST)  # Log dos dados recebidos
        # Identifica qual PA foi modificada
        modified_pa_id = request.POST.get('modified_pa')
        if modified_pa_id:
            try:
                print(f"Tentando salvar workstation {modified_pa_id}")  # Log de depuração
                workstation = Workstation.objects.get(id=modified_pa_id)
                print(f"Status atual: {workstation.status}")  # Log status atual
                form = WorkstationForm(request.POST, instance=workstation, prefix=modified_pa_id)
                print(f"Dados do formulário: {form.data}")  # Log dos dados recebidos
                if form.is_valid():
                    print("Formulário válido, salvando...")  # Log antes de salvar
                    # Save the form first to update the employee if selected
                    workstation = form.save()
                    
                    # Get the status submitted by the user
                    submitted_status = request.POST.get(f'{modified_pa_id}-status')
                    
                    # Apply logic based on submitted status
                    if submitted_status == 'UNOCCUPIED':
                        workstation.employee = None
                        workstation.status = 'UNOCCUPIED'
                    elif submitted_status == 'MAINTENANCE':
                        # Keep employee assigned by form, just update status
                        workstation.status = 'MAINTENANCE'
                    elif submitted_status == 'OCCUPIED':
                         # Keep employee assigned by form, just update status
                        workstation.status = 'OCCUPIED'
                        # Optional: Add check here if workstation.employee is None and raise error?
                    else:
                        # Handle potentially invalid status if necessary, maybe log it
                        # For now, just assign it if it's a valid choice in the model
                        if submitted_status in dict(Workstation.STATUS_CHOICES):
                             workstation.status = submitted_status

                    # Save the final status and potentially cleared employee
                    workstation.save(update_fields=['employee', 'status'])
                    messages.success(request, 'Alterações salvas com sucesso!')
                else:
                    error_message = 'Erro ao salvar: Dados inválidos'
                    # Log detalhado dos erros
                    print("Erros detalhados no formulário:")
                    for field, errors in form.errors.items():
                        print(f"Campo {field}:")
                        for error in errors:
                            print(f" - {error}")
                    print(f"Dados completos: {form.data}")
            except Workstation.DoesNotExist:
                error_message = 'Erro: Estação não encontrada'
            except Exception as e:
                error_message = f'Erro ao salvar alterações: {str(e)}'
                print(f"Erro ao salvar workstation {modified_pa_id}: {str(e)}")
        else:
            error_message = 'Nenhuma estação foi modificada'
        
        # Recarrega a página com mensagem de erro se houver
        if error_message:
            messages.error(request, error_message)
        return redirect('pam:admin_office_view')
    
    # GET request - prepara os formulários
    def prepare_forms(workstations):
        return [(ws, WorkstationForm(instance=ws, prefix=str(ws.id)))
               for ws in workstations]
    
    inss_forms = prepare_forms(inss_workstations)
    siae_leo_forms = prepare_forms(siae_leo_workstations)
    siae_dion_forms = prepare_forms(siae_dion_workstations)
    estagio_forms = prepare_forms(estagio_workstations)
    
    # Organiza cada grupo em colunas 6x2 (de baixo para cima)
    def organize_columns(workstations_with_forms):
        columns = [[], []]
        for i, (ws, form) in enumerate(workstations_with_forms):
            columns[i // 6].append((ws, form))
        return [list(reversed(col)) for col in columns]
    
    inss_columns = organize_columns(inss_forms)
    siae_leo_columns = organize_columns(siae_leo_forms)
    siae_dion_columns = organize_columns(siae_dion_forms)
    estagio_columns = organize_columns(estagio_forms)
    
    return render(request, 'pam/admin_office.html', {
        'inss_columns': inss_columns,
        'siae_leo_columns': siae_leo_columns,
        'siae_dion_columns': siae_dion_columns,
        'estagio_columns': estagio_columns,
        'error_message': error_message
    })
