from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from .models import Workstation, Employee, Room, Island, ChangeLog, EmployeePositionHistory, log_change
from .forms import WorkstationForm, RoomForm, EmployeeForm, LoginForm
from django.http import JsonResponse
from django.db.models import Prefetch
from django.views.decorators.http import require_POST, require_http_methods
from django.http import Http404 # Import Http404
import math # Add math import
from django.db.models.query import Prefetch
from django.db import transaction
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

import json
from datetime import datetime, timedelta

def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def is_superuser(user):
    return user.is_authenticated and user.is_superuser

def login_view(request):
    """View para login de usuários."""
    if request.method == 'POST':
        form = LoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
    else:
        form = LoginForm()
    return render(request, 'pam/login.html', {'form': form})

def logout_view(request):
    """View para logout de usuários."""
    logout(request)
    return redirect('pam:office_view')

# --- Refined arrange_workstations_in_columns Function ---
def arrange_workstations_in_columns(workstations_list_input, num_columns=2):
    """Adiciona numeração sequencial (display_sequence) e divide em colunas invertidas."""
    # Retorna lista vazia imediatamente se a entrada estiver vazia
    if not workstations_list_input:
        return []

    # Determina o tipo de lista (objetos ou dicionários) com segurança
    is_dict_list = isinstance(workstations_list_input[0], dict)

    # 1. Adiciona display_sequence ao objeto Workstation correto
    processed_list_with_sequence = []
    for i, item in enumerate(workstations_list_input):
        try:
            # Identifica o objeto workstation alvo
            target_workstation = item['workstation'] if is_dict_list else item
            if target_workstation: # Garante que o objeto existe
                 target_workstation.display_sequence = i + 1
                 processed_list_with_sequence.append(item) # Adiciona o item (original ou dict) à nova lista
            # else: # Log se um item inesperado for encontrado (opcional)
            #    print(f"Warning: Item {i} inválido encontrado.")
        except (AttributeError, KeyError, TypeError) as e:
             # Log de erro se algo der errado ao tentar acessar/definir o atributo
             print(f"Warning: Não foi possível definir display_sequence para o item {i}. Erro: {e}")
             # Decide se inclui o item mesmo sem a sequência ou pula
             # Vamos incluir por enquanto para não quebrar a estrutura
             processed_list_with_sequence.append(item)


    # 2. Divide a lista processada (com display_sequence) em colunas
    total_ws = len(processed_list_with_sequence)
    if total_ws == 0 or num_columns <= 0:
         return []

    # Cálculo de linhas/colunas (mantido, com correção de edge case)
    num_rows = math.ceil(total_ws / num_columns) if total_ws > 0 else 0
    if num_rows == 0 and total_ws > 0: # Edge case: num_columns > total_ws > 0
         num_rows = 1

    columns = [[] for _ in range(num_columns)]
    for i, item in enumerate(processed_list_with_sequence):
         col_index = i // num_rows if num_rows > 0 else 0
         if col_index < num_columns:
             columns[col_index].append(item)

    # 3. Inverte as colunas para renderização bottom-up
    processed_columns = [list(reversed(col)) for col in columns]
    return processed_columns

def office_view(request):
    """Visualização pública do escritório, organizada por Salas e Ilhas"""
    # Configura headers para evitar cache
    response = HttpResponse()
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    # Busca dados usando a nova estrutura, otimizada com prefetch_related
    rooms_data = Room.objects.prefetch_related(
        Prefetch(
            'islands',
            queryset=Island.objects.prefetch_related(
                Prefetch(
                    'workstations',
                    queryset=Workstation.objects.select_related('employee').order_by('sequence'),
                )
            ).order_by('island_number'),
        )
    ).order_by('name')

    # Processa workstations em colunas para cada ilha
    for room in rooms_data:
        for island in room.islands.all(): # Itera sobre as ilhas pré-carregadas
             workstations_on_island = list(island.workstations.all()) # Acessa workstations pré-carregadas
             # Chama a função refatorada (definida acima)
             island.processed_columns = arrange_workstations_in_columns(workstations_on_island)

    # Passa os dados estruturados por sala para o template
    context = {
        'rooms_data': rooms_data,
    }
    # Precisamos garantir que o template 'pam/office_view.html' também use 'rooms_data'
    return render(request, 'pam/office_view.html', context)

@login_required
@user_passes_test(is_admin)
def admin_office_view(request):
    """Visualização administrativa do escritório, organizada por Salas e Ilhas"""

    if request.method == 'POST':
        modified_workstations = []
        errors_found = []
        workstation_ids_in_post = set()

        # 1. Coletar todos os IDs de Workstation presentes no POST
        for key in request.POST:
            if '-' in key:
                try:
                    ws_id_str = key.split('-')[0]
                    ws_id = int(ws_id_str)
                    workstation_ids_in_post.add(ws_id)
                except (ValueError, IndexError):
                    continue # Ignora chaves mal formatadas

        if not workstation_ids_in_post:
            messages.warning(request, "Nenhuma alteração detectada.")
            return redirect('pam:admin_office_view')

        # 2. Buscar todas as workstations relevantes do banco de dados de uma vez
        workstations_to_check = Workstation.objects.select_related('employee').filter(id__in=workstation_ids_in_post)
        workstations_dict = {ws.id: ws for ws in workstations_to_check}

        # 3. Iterar sobre os IDs e verificar modificações
        try:
            with transaction.atomic(): # Garante que todas as alterações sejam salvas ou nenhuma
                for ws_id in workstation_ids_in_post:
                    if ws_id not in workstations_dict:
                        errors_found.append(f"Erro: Workstation com ID {ws_id} não encontrada no banco.")
                        continue # Pula para o próximo ID
                    
                    workstation = workstations_dict[ws_id]
                    original_status = workstation.status
                    original_employee = workstation.employee
                    fields_to_update = []

                    # Verificar Employee (ANTES de verificar/aplicar status)
                    submitted_employee_id = request.POST.get(f'{ws_id}-employee')
                    selected_employee = None
                    employee_changed = False
                    if submitted_employee_id is not None: # Verifica se o campo foi enviado
                        if submitted_employee_id == '' and original_employee is not None: # Desatribuindo
                            workstation.employee = None
                            employee_changed = True
                            
                            # Registra a remoção do funcionário no log
                            log_change(
                                user=request.user,
                                entity_type='WORKSTATION',
                                entity_id=ws_id,
                                entity_name=f"PA {workstation.category} {workstation.sequence}",
                                action_type='UNASSIGNMENT',
                                description=f"Funcionário {original_employee.name} removido da estação de trabalho"
                            )
                        elif submitted_employee_id:
                            try:
                                submitted_employee_id_int = int(submitted_employee_id)
                                if original_employee is None or original_employee.id != submitted_employee_id_int:
                                    # Busca o funcionário SE houver mudança ou for nova atribuição
                                    # Idealmente, ter um cache de funcionários aqui seria mais eficiente se muitos forem alterados
                                    selected_employee = Employee.objects.get(pk=submitted_employee_id_int)
                                    workstation.employee = selected_employee
                                    employee_changed = True
                                    
                                    # Registra a atribuição do funcionário no log
                                    action_type = 'ASSIGNMENT'
                                    if original_employee:
                                        description = f"Funcionário alterado de {original_employee.name} para {selected_employee.name}"
                                    else:
                                        description = f"Funcionário {selected_employee.name} atribuído à estação de trabalho"
                                    
                                    log_change(
                                        user=request.user,
                                        entity_type='WORKSTATION',
                                        entity_id=ws_id,
                                        entity_name=f"PA {workstation.category} {workstation.sequence}",
                                        action_type=action_type,
                                        description=description
                                    )
                                else:
                                     # ID enviado é o mesmo que já estava, não faz nada
                                     pass
                            except (ValueError, Employee.DoesNotExist):
                                errors_found.append(f"Erro: Funcionário com ID '{submitted_employee_id}' inválido para PA {ws_id}.")
                                continue # Pula esta PA
                    
                    # Se o funcionário foi alterado, marca para salvar
                    if employee_changed:
                        fields_to_update.append('employee')

                    # Verificar Status
                    submitted_status = request.POST.get(f'{ws_id}-status')
                    if submitted_status and submitted_status != original_status:
                        if submitted_status in dict(Workstation.STATUS_CHOICES):
                            # Aplica o status ANTES da lógica condicional abaixo
                            workstation.status = submitted_status
                            fields_to_update.append('status')
                            
                            # Registra a alteração de status no log
                            status_display = dict(Workstation.STATUS_CHOICES).get(submitted_status)
                            original_status_display = dict(Workstation.STATUS_CHOICES).get(original_status)
                            log_change(
                                user=request.user,
                                entity_type='WORKSTATION',
                                entity_id=ws_id,
                                entity_name=f"PA {workstation.category} {workstation.sequence}",
                                action_type='UPDATE',
                                description=f"Status alterado de '{original_status_display}' para '{status_display}'"
                            )
                        else:
                            errors_found.append(f"Erro: Status '{submitted_status}' inválido para PA {ws_id}.")
                            continue # Pula esta PA

                    # Aplicar lógica de status (APÓS processar employee e status submetidos)
                    if workstation.status == 'UNOCCUPIED' and workstation.employee is not None:
                        # Se status foi definido como Vaga, mas ainda temos um funcionário (vindo do original ou selecionado)
                        # Força a desassociação do funcionário.
                        workstation.employee = None # Desassocia funcionário
                        if 'employee' not in fields_to_update: fields_to_update.append('employee')

                    # Não precisamos mais da verificação explícita `elif workstation.status == 'OCCUPIED' and workstation.employee is None:`
                    # porque se o status for OCCUPIED e o employee não foi selecionado/mantido,
                    # a verificação final antes do save() pegará isso.

                    # 4. Salvar se houver alterações
                    if fields_to_update:
                        # Verifica consistência final antes de salvar
                        if workstation.status == 'OCCUPIED' and workstation.employee is None:
                             errors_found.append(f"Erro Crítico: Tentativa de salvar PA {ws_id} como 'Ocupada' sem funcionário.")
                             # Reverte o status para o original para evitar inconsistência?
                             # workstation.status = original_status
                             # if 'status' in fields_to_update: fields_to_update.remove('status')
                             # if 'employee' in fields_to_update: fields_to_update.remove('employee')
                             # fields_to_update = [] # Não salva nada desta PA
                        elif workstation.status == 'UNOCCUPIED' and workstation.employee is not None:
                            # Deveria ter sido corrigido acima, mas como segurança
                            errors_found.append(f"Erro Crítico: Tentativa de salvar PA {ws_id} como 'Vaga' com funcionário.")
                        else:
                            workstation.save(update_fields=fields_to_update)
                            modified_workstations.append(ws_id)

        except Exception as e:
            messages.error(request, f"Erro inesperado durante o processamento: {e}")
            print(f"Erro inesperado salvando multiplas workstations: {e}") # Log
            return redirect('pam:admin_office_view')

        # 5. Feedback ao usuário
        if modified_workstations and not errors_found:
            messages.success(request, f"Alterações salvas com sucesso para {len(modified_workstations)} workstation(s)!")
        elif modified_workstations:
             messages.warning(request, f"Alterações salvas para {len(modified_workstations)} workstation(s), mas ocorreram erros em outras: {'; '.join(errors_found)}")
        elif errors_found:
            messages.error(request, f"Nenhuma alteração salva. Erros encontrados: {'; '.join(errors_found)}")
        else:
             messages.info(request, "Nenhuma alteração foi realizada.") # Caso não haja fields_to_update

        return redirect('pam:admin_office_view')

    # --- GET Logic (Preparing Data for Display) ---
    rooms_data = Room.objects.prefetch_related(
        Prefetch(
            'islands',
            queryset=Island.objects.prefetch_related(
                Prefetch(
                    'workstations',
                    queryset=Workstation.objects.select_related('employee').order_by('sequence'),
                    to_attr='workstations_with_forms' # Mantém to_attr aqui
                )
            ).order_by('island_number'),
            to_attr='islands_prefetched'
        )
    ).order_by('name')
        
    # Processa workstations em colunas para cada ilha
    # temp_forms_list = [] # Não precisamos mais guardar forms separadamente
    for room in rooms_data:
        for island in room.islands_prefetched:
             # Prepara a lista de entrada para a função
             input_list_for_island = []
             if hasattr(island, 'workstations_with_forms'):
                  for ws in island.workstations_with_forms:
                       form = WorkstationForm(instance=ws, prefix=str(ws.id))
                       # Cria o dict esperado pela função
                       input_list_for_island.append({'workstation': ws, 'form': form})
                  # Chama a função refatorada (definida acima)
                  island.processed_columns = arrange_workstations_in_columns(input_list_for_island)
                  # Remove o atributo antigo para evitar confusão
                  delattr(island, 'workstations_with_forms')
             else:
                  # Garante que processed_columns exista mesmo sem workstations_with_forms
                  island.processed_columns = [] 

    # The context now contains rooms, each with islands, each island with processed_columns
    context = {
        'rooms_data': rooms_data,
        # 'error_message': error_message # Error message is handled by Django messages framework on redirect
    }
    return render(request, 'pam/admin_office.html', context)

@require_POST # Garante que esta view só aceite POST
@user_passes_test(is_admin) # Garante que só admin pode acessar
def add_room_ajax_view(request):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Rejeitar se não for AJAX (opcional, mas boa prática)
        return JsonResponse({'success': False, 'errors': {'__all__': ['Requisição inválida.']}}, status=400)

    room_form = RoomForm(request.POST)
    num_islands_str = request.POST.get('num_islands', '0')
    
    errors = {}
    num_islands = 0 # Inicializa
    try:
        num_islands = int(num_islands_str)
        if num_islands <= 0:
             errors['counts'] = ['Número de ilhas deve ser positivo.']
    except ValueError:
         errors['counts'] = ['Número de ilhas inválido.']

    # *** CORREÇÃO: Ler workstations e categorias usando os nomes indexados ***
    workstations_per_island_str = []
    island_categories_str = []
    if not errors: # Só tenta ler se num_islands for válido
        for i in range(num_islands):
            ws_count_str = request.POST.get(f'island_{i+1}_workstations', '0') # Lê island_1_workstations, etc.
            category_str = request.POST.get(f'island_{i+1}_category', '')      # Lê island_1_category, etc.
            workstations_per_island_str.append(ws_count_str)
            island_categories_str.append(category_str)

    # A verificação de inconsistência não é mais necessária da mesma forma,
    # pois o loop garante que temos a quantidade certa de itens se num_islands for válido.

    # Validação dos valores lidos
    workstations_per_island = []
    if not errors:
        for count_str in workstations_per_island_str:
            try:
                count = int(count_str)
                if count <= 0:
                    errors.setdefault('counts', []).append('Número de workstations por ilha deve ser positivo.')
                    break # Para no primeiro erro de contagem
                workstations_per_island.append(count)
            except ValueError:
                errors.setdefault('counts', []).append('Número inválido de workstations por ilha fornecido.')
                break # Para no primeiro erro de valor

    if not errors and room_form.is_valid():
        try:
            with transaction.atomic(): # Garante que tudo seja salvo ou nada
                room = room_form.save() # Salva a sala

                # Cria ilhas e workstations
                for i in range(num_islands):
                    island_num = i + 1
                    # Valida se temos dados suficientes antes de tentar acessar o índice
                    if i < len(workstations_per_island) and i < len(island_categories_str):
                        num_workstations = workstations_per_island[i]
                        island_category = island_categories_str[i] # *** NOVO: Pega a categoria da ilha ***

                        island = Island.objects.create(
                            room=room,
                            island_number=island_num,
                            name=str(island_num),
                            category=island_category # *** NOVO: Salva a categoria na ilha ***
                        )
                        for j in range(num_workstations):
                            # Lógica de criação da workstation (usando a categoria da ilha)
                            Workstation.objects.create(
                                island=island,
                                status='UNOCCUPIED',
                                sequence = j + 1, # Definindo a sequência
                                category=island_category, # Usando a categoria da própria ilha
                            )
                    else:
                        # Tratar erro: Inconsistência nos dados coletados
                        # Isso não deveria acontecer se as leituras anteriores estiverem corretas
                        # mas é uma salvaguarda.
                        errors['__all__'] = ['Erro interno: Inconsistência nos dados das ilhas.']
                        # Força a saída do loop e falha da transação
                        raise transaction.TransactionManagementError("Dados de ilha inconsistentes.")

                return JsonResponse({'success': True}) # Sucesso!

        except ValueError: # Erro na conversão de números DENTRO da lógica de criação (se houver)
            errors.setdefault('counts', []).append('Valores inválidos detectados durante a criação.')
            # Não retorna aqui, deixa cair para o retorno de erro geral abaixo
        except transaction.TransactionManagementError as tme:
             # O erro já foi adicionado a errors['__all__']
             print(f"Erro de transação: {tme}")
             # Deixa cair para o retorno de erro geral
             pass
        except Exception as e: # Erro inesperado no banco ou outro DENTRO da transação
            print(f"Erro inesperado em add_room_ajax_view durante a transação: {e}") # Log do erro
            errors['__all__'] = ['Ocorreu um erro interno ao salvar a sala e suas estruturas.']
            # Deixa cair para o retorno de erro geral

    # --- Bloco de retorno de erro (agora fora do try/except principal da lógica de criação) ---
    # Coleta erros do RoomForm SE o if principal falhou E room_form não for válido
    if not room_form.is_valid():
        for field, field_errors in room_form.errors.items():
            # Evita sobrescrever erros já detectados
            errors.setdefault(field, []).extend(field_errors)

    # Retorna JSON de erro se houver QUALQUER erro detectado
    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # Se chegou aqui sem erros, algo muito estranho aconteceu.
    # Adiciona um erro genérico por segurança.
    print("Alerta: A view add_room_ajax chegou ao final sem sucesso ou erro definido.")
    errors['__all__'] = ['Ocorreu uma falha inesperada no processamento.']
    return JsonResponse({'success': False, 'errors': errors}, status=500)

# --- Views AJAX para Remoção ---

@user_passes_test(is_admin) # Protege a view
def list_rooms_ajax_view(request):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Requisição inválida.'}, status=400)

    try:
        rooms = Room.objects.all().values('id', 'name').order_by('name') # Pega só id e nome
        return JsonResponse({'rooms': list(rooms)})
    except Exception as e:
        print(f"Erro ao listar salas via AJAX: {e}")
        return JsonResponse({'error': 'Erro ao buscar salas.'}, status=500)


@require_POST # Garante que só aceite POST (ou DELETE, se preferir mudar)
@user_passes_test(is_admin)
def remove_room_ajax_view(request, room_id):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Requisição inválida.'}, status=400)

    try:
        room = get_object_or_404(Room, pk=room_id)
        room_name = room.name # Guarda o nome para log ou mensagem futura
        room.delete() # CASCADE configurado no modelo deve remover Ilhas e Workstations
        # print(f"Sala '{room_name}' removida com sucesso.") # Log opcional
        return JsonResponse({'success': True})
    except Http404:
         return JsonResponse({'success': False, 'error': 'Sala não encontrada.'}, status=404)
    except Exception as e:
        print(f"Erro ao remover sala {room_id} via AJAX: {e}")
        return JsonResponse({'success': False, 'error': 'Erro interno ao remover a sala.'}, status=500)

# --- View para Gerenciar Funcionários ---

@login_required
@user_passes_test(is_admin)
def manage_employees_view(request):
    """View para gerenciar funcionários."""
    
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            form = EmployeeForm(request.POST)
            if form.is_valid():
                try:
                    form.save()
                    messages.success(request, "Funcionário adicionado com sucesso!")
                    return redirect('pam:manage_employees') # Redireciona para limpar o POST
                except Exception as e:
                    # Captura erros de integridade (ex: CPF/Email duplicado)
                    messages.error(request, f"Erro ao adicionar funcionário: {e}")
                    # O form com os erros será passado para o contexto abaixo
            else:
                messages.error(request, "Erro de validação. Verifique os campos.")
                # O form inválido será passado para o contexto abaixo

        elif action == 'remove':
            employee_id = request.POST.get('employee_id')
            if employee_id:
                try:
                    employee = get_object_or_404(Employee, pk=employee_id)
                    employee_name = employee.name # Guarda nome para mensagem
                    # Antes de deletar, desassociar de qualquer Workstation
                    # Workstation.objects.filter(employee=employee).update(employee=None, status='UNOCCUPIED') # O SET_NULL já faz isso
                    employee.delete()
                    messages.success(request, f"Funcionário '{employee_name}' removido com sucesso!")
                except Http404:
                    messages.error(request, "Erro: Funcionário não encontrado.")
                except Exception as e:
                     messages.error(request, f"Erro ao remover funcionário: {e}")
            else:
                messages.error(request, "ID do funcionário não fornecido para remoção.")
            return redirect('pam:manage_employees') # Redireciona após remover (ou tentar)

    # Lógica GET (ou se o POST falhou a validação no 'add')
    employees = Employee.objects.prefetch_related(
        Prefetch('workstation_set', 
                queryset=Workstation.objects.select_related('island', 'island__room'))
    ).all().order_by('name')
    
    # Se a requisição foi POST e o form falhou, usa o form com erros
    # Senão, cria um form vazio para o GET
    form_to_render = form if ('form' in locals() and request.method == 'POST' and action == 'add') else EmployeeForm()

    context = {
        'employees': employees,
        'form': form_to_render,
    }
    return render(request, 'pam/manage_employees.html', context)

@user_passes_test(is_superuser)
def manage_rooms_view(request):
    """View para gerenciar salas."""
    rooms = Room.objects.all().order_by('name')
    
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Sala adicionada com sucesso!")
            return redirect('pam:manage_rooms')
    else:
        form = RoomForm()
        
    context = {
        'rooms': rooms,
        'form': form
    }
    return render(request, 'pam/manage_rooms.html', context)

@user_passes_test(is_superuser)
def manage_islands_view(request):
    """View para gerenciar ilhas."""
    islands = Island.objects.select_related('room').all().order_by('room__name', 'island_number')
    rooms = Room.objects.all().order_by('name')
    
    if request.method == 'POST':
        room_id = request.POST.get('room')
        island_name = request.POST.get('island_number')
        category = request.POST.get('category')
        
        if not category:
            messages.error(request, "A categoria da ilha é obrigatória!")
            return redirect('pam:manage_islands')
        
        if room_id and island_name:
            try:
                room = Room.objects.get(id=room_id)
                # Tratamento para aceitar valores não numéricos
                try:
                    island_number = int(island_name)
                except ValueError:
                    # Se não for um número, usamos um número sequencial
                    last_island = Island.objects.filter(room=room).order_by('-island_number').first()
                    island_number = 1
                    if last_island:
                        island_number = last_island.island_number + 1
                
                island = Island.objects.create(
                    room=room,
                    island_number=island_number,
                    name=island_name,
                    category=category
                )
                messages.success(request, f"Ilha {island_name} adicionada com sucesso!")
                return redirect('pam:manage_islands')
            except Exception as e:
                messages.error(request, f"Erro ao adicionar ilha: {str(e)}")
        else:
            messages.error(request, "Sala e nome da ilha são obrigatórios!")
    
    context = {
        'islands': islands,
        'rooms': rooms
    }
    return render(request, 'pam/manage_islands.html', context)

@user_passes_test(is_superuser)
def manage_workstations_view(request):
    """View para gerenciar estações de trabalho (PAs)."""
    workstations = Workstation.objects.select_related('employee', 'island', 'island__room').all()
    islands = Island.objects.select_related('room').all().order_by('room__name', 'island_number')
    employees = Employee.objects.all().order_by('name')
    rooms = Room.objects.all().order_by('name')
    
    # Obter funcionários disponíveis (não atribuídos a nenhuma PA)
    assigned_employee_ids = Workstation.objects.exclude(employee=None).values_list('employee_id', flat=True)
    available_employees = Employee.objects.exclude(id__in=assigned_employee_ids).order_by('name')
    
    if request.method == 'POST':
        # Obter os dados do formulário
        island_id = request.POST.get('island')
        room_id = request.POST.get('room')
        quantity = int(request.POST.get('quantity', 1))
        
        # Verificar se a quantidade está dentro dos limites
        if quantity < 1:
            quantity = 1
        elif quantity > 50:
            quantity = 50
        
        if island_id and room_id:
            try:
                island = Island.objects.get(id=island_id)
                if str(island.room_id) != room_id:
                    messages.error(request, "A ilha selecionada não pertence à sala selecionada!")
                    return redirect('pam:manage_workstations')
                
                # Buscar a última workstation com esta categoria para definir a sequência inicial
                category = island.category
                last_workstation = Workstation.objects.filter(
                    category=category
                ).order_by('-sequence').first()
                
                next_sequence = 1
                if last_workstation:
                    next_sequence = last_workstation.sequence + 1
                
                # Criar as PAs conforme a quantidade solicitada
                pas_criados = 0
                for i in range(quantity):
                    try:
                        workstation = Workstation(
                            island=island,
                            category=category,
                            sequence=next_sequence + i,
                            # Configuração padrão para periféricos
                            monitor=True,
                            keyboard=True,
                            mouse=True,
                            mousepad=True,
                            headset=True
                        )
                        workstation.save()
                        pas_criados += 1
                    except Exception as e:
                        messages.error(request, f"Erro ao criar PA #{next_sequence + i}: {str(e)}")
                
                if pas_criados > 0:
                    messages.success(request, f"{pas_criados} estação(ões) de trabalho adicionada(s) com sucesso!")
                return redirect('pam:manage_workstations')
            except Island.DoesNotExist:
                messages.error(request, "Ilha não encontrada.")
            except Exception as e:
                messages.error(request, f"Erro ao adicionar estações de trabalho: {str(e)}")
        else:
            messages.error(request, "Sala e ilha são campos obrigatórios!")
    
    context = {
        'workstations': workstations,
        'islands': islands,
        'employees': employees,
        'available_employees': available_employees,
        'rooms': rooms
    }
    return render(request, 'pam/manage_workstations.html', context)

@user_passes_test(is_admin)
@require_POST
def delete_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    room_name = room.name
    room.delete()
    
    # Registra a alteração no log
    log_change(
        user=request.user,
        entity_type='ROOM',
        entity_id=room_id,
        entity_name=room_name,
        action_type='DELETE',
        description=f"Sala {room_name} excluída"
    )
    
    messages.success(request, f'Sala {room_name} excluída com sucesso.')
    return redirect('pam:manage_rooms')

@user_passes_test(is_superuser)
@require_POST
def delete_island_view(request, island_id):
    island = get_object_or_404(Island, pk=island_id)
    island_name = island.name
    room_name = island.room.name
    island.delete()
    
    # Registra a alteração no log
    log_change(
        user=request.user,
        entity_type='ISLAND',
        entity_id=island_id,
        entity_name=island_name,
        action_type='DELETE',
        description=f"Ilha {island_name} da sala {room_name} excluída"
    )
    
    messages.success(request, f'Ilha {island_name} excluída com sucesso.')
    return redirect('pam:manage_islands')

@user_passes_test(is_superuser)
@require_POST
def delete_workstation_view(request, workstation_id):
    workstation = get_object_or_404(Workstation, pk=workstation_id)
    ws_description = str(workstation)
    workstation.delete()
    
    # Registra a alteração no log
    log_change(
        user=request.user,
        entity_type='WORKSTATION',
        entity_id=workstation_id,
        entity_name=f"PA {workstation.category} {workstation.sequence}",
        action_type='DELETE',
        description=f"Estação de trabalho {ws_description} excluída"
    )
    
    messages.success(request, f'Estação de trabalho excluída com sucesso.')
    return redirect('pam:manage_workstations')

@user_passes_test(is_admin)
def get_islands_by_room(request, room_id):
    """API para obter ilhas de uma sala específica."""
    try:
        islands = Island.objects.filter(room_id=room_id).values('id', 'island_number', 'name', 'category').order_by('island_number')
        # Formatar o nome da ilha para cada item da lista
        islands_list = list(islands)
        for island in islands_list:
            island['display_name'] = f"Ilha {island['name']}"
        return JsonResponse({'islands': islands_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@user_passes_test(is_superuser)
def unified_management_view(request):
    """View unificada para gerenciar todas as entidades (Salas, Ilhas, PAs e Funcionários) em uma única página."""
    
    # Variáveis para controlar se houve algum POST e para qual entidade
    form_submitted = False
    active_tab = request.POST.get('active_tab', 'rooms')  # Default para a aba de salas
    
    # ----- PROCESSAMENTO DE ROOMS -----
    rooms = Room.objects.all().order_by('name')
    room_form = RoomForm()
    
    if request.method == 'POST' and 'room_submit' in request.POST:
        form_submitted = True
        active_tab = 'rooms'
        room_form = RoomForm(request.POST)
        if room_form.is_valid():
            room_form.save()
            messages.success(request, "Sala adicionada com sucesso!")
            return redirect('pam:unified_management')
    
    # ----- PROCESSAMENTO DE ISLANDS -----
    islands = Island.objects.select_related('room').all().order_by('room__name', 'island_number')
    
    if request.method == 'POST' and 'island_submit' in request.POST:
        form_submitted = True
        active_tab = 'islands'
        room_id = request.POST.get('room')
        island_name = request.POST.get('island_number')
        category = request.POST.get('category')
        
        if not category:
            messages.error(request, "A categoria da ilha é obrigatória!")
        elif room_id and island_name:
            try:
                room = Room.objects.get(id=room_id)
                try:
                    island_number = int(island_name)
                except ValueError:
                    last_island = Island.objects.filter(room=room).order_by('-island_number').first()
                    island_number = 1
                    if last_island:
                        island_number = last_island.island_number + 1
                
                island = Island.objects.create(
                    room=room,
                    island_number=island_number,
                    name=island_name,
                    category=category
                )
                messages.success(request, f"Ilha {island_name} adicionada com sucesso!")
                return redirect('pam:unified_management')
            except Exception as e:
                messages.error(request, f"Erro ao adicionar ilha: {str(e)}")
        else:
            messages.error(request, "Sala e nome da ilha são obrigatórios!")
    
    # ----- PROCESSAMENTO DE WORKSTATIONS -----
    workstations = Workstation.objects.select_related('employee', 'island', 'island__room').all()
    islands_for_ws = Island.objects.select_related('room').all().order_by('room__name', 'island_number')
    workstation_form = WorkstationForm()
    
    # Obter funcionários disponíveis (não atribuídos a nenhuma PA)
    assigned_employee_ids = Workstation.objects.exclude(employee=None).values_list('employee_id', flat=True)
    available_employees = Employee.objects.exclude(id__in=assigned_employee_ids).order_by('name')
    
    if request.method == 'POST' and 'workstation_submit' in request.POST:
        form_submitted = True
        active_tab = 'workstations'
        
        # Obter os dados do formulário
        island_id = request.POST.get('island')
        room_id = request.POST.get('room')
        quantity = int(request.POST.get('quantity', 1))
        
        # Verificar se a quantidade está dentro dos limites
        if quantity < 1:
            quantity = 1
        elif quantity > 50:
            quantity = 50
        
        if island_id and room_id:
            try:
                island = Island.objects.get(id=island_id)
                if str(island.room_id) != room_id:
                    messages.error(request, "A ilha selecionada não pertence à sala selecionada!")
                    return redirect('pam:unified_management')
                
                # Buscar a última workstation com esta categoria para definir a sequência inicial
                category = island.category
                last_workstation = Workstation.objects.filter(
                    category=category
                ).order_by('-sequence').first()
                
                next_sequence = 1
                if last_workstation:
                    next_sequence = last_workstation.sequence + 1
                
                # Criar as PAs conforme a quantidade solicitada
                pas_criados = 0
                for i in range(quantity):
                    try:
                        workstation = Workstation(
                            island=island,
                            category=category,
                            sequence=next_sequence + i,
                            # Configuração padrão para periféricos
                            monitor=True,
                            keyboard=True,
                            mouse=True,
                            mousepad=True,
                            headset=True
                        )
                        workstation.save()
                        pas_criados += 1
                    except Exception as e:
                        messages.error(request, f"Erro ao criar PA #{next_sequence + i}: {str(e)}")
                
                if pas_criados > 0:
                    messages.success(request, f"{pas_criados} estação(ões) de trabalho adicionada(s) com sucesso!")
                return redirect('pam:unified_management')
            except Island.DoesNotExist:
                messages.error(request, "Ilha não encontrada.")
            except Exception as e:
                messages.error(request, f"Erro ao adicionar estações de trabalho: {str(e)}")
        else:
            messages.error(request, "Sala e ilha são campos obrigatórios!")
    
    # ----- PROCESSAMENTO DE EMPLOYEES -----
    employees = Employee.objects.all().order_by('name')
    employee_form = EmployeeForm()
    
    if request.method == 'POST' and 'employee_submit' in request.POST:
        form_submitted = True
        active_tab = 'employees'
        employee_form = EmployeeForm(request.POST)
        if employee_form.is_valid():
            try:
                employee_form.save()
                messages.success(request, "Funcionário adicionado com sucesso!")
                return redirect('pam:unified_management')
            except Exception as e:
                messages.error(request, f"Erro ao adicionar funcionário: {e}")
        else:
            messages.error(request, "Erro de validação. Verifique os campos.")
    
    # ----- PROCESSAMENTO DE REMOÇÃO DE FUNCIONÁRIO -----
    if request.method == 'POST' and request.POST.get('action') == 'remove':
        active_tab = 'employees'
        employee_id = request.POST.get('employee_id')
        if employee_id:
            try:
                employee = get_object_or_404(Employee, pk=employee_id)
                employee_name = employee.name  # Guarda nome para mensagem
                
                # Registra a alteração no log
                log_change(
                    user=request.user,
                    entity_type='EMPLOYEE',
                    entity_id=employee_id,
                    entity_name=employee_name,
                    action_type='DELETE',
                    description=f"Funcionário {employee_name} excluído"
                )
                
                employee.delete()
                messages.success(request, f"Funcionário '{employee_name}' removido com sucesso!")
            except Http404:
                messages.error(request, "Erro: Funcionário não encontrado.")
            except Exception as e:
                messages.error(request, f"Erro ao remover funcionário: {e}")
        else:
            messages.error(request, "ID do funcionário não fornecido para remoção.")
        return redirect('pam:unified_management')
    
    # Contexto geral para o template
    context = {
        'active_tab': active_tab,
        # Salas
        'rooms': rooms,
        'room_form': room_form,
        # Ilhas
        'islands': islands,
        'rooms_for_island': rooms,  # Usar para o dropdown
        # Estações de trabalho
        'workstations': workstations,
        'islands_for_ws': islands_for_ws,
        'workstation_form': workstation_form,
        'rooms_for_ws': rooms,  # Usar para o dropdown
        'employees_for_ws': employees,  # Usar para o dropdown
        'available_employees': available_employees,
        # Funcionários
        'employees': employees,
        'employee_form': employee_form,
    }
    
    return render(request, 'pam/unified_management.html', context)

@user_passes_test(is_superuser)
@require_POST
def toggle_peripheral_view(request, workstation_id):
    """Toggle entre ligado/desligado para periféricos de uma workstation"""
    workstation = get_object_or_404(Workstation, pk=workstation_id)
    peripheral = request.POST.get('peripheral')
    
    if not peripheral:
        peripheral = request.POST.get('peripheral_type')  # Para compatibilidade com o front-end
        
    if peripheral not in ['monitor', 'keyboard', 'mouse', 'mousepad', 'headset']:
        return JsonResponse({'status': 'error', 'message': 'Periférico inválido'}, status=400)
    
    # Toggle o estado
    current_value = getattr(workstation, peripheral)
    setattr(workstation, peripheral, not current_value)
    
    # Registra no log a alteração do periférico
    peripheral_display = {
        'monitor': 'Monitor',
        'keyboard': 'Teclado',
        'mouse': 'Mouse',
        'mousepad': 'Mousepad',
        'headset': 'Fone de Ouvido'
    }.get(peripheral, peripheral)
    
    new_state = 'disponível' if getattr(workstation, peripheral) else 'indisponível'
    log_change(
        user=request.user,
        entity_type='WORKSTATION',
        entity_id=workstation.id,
        entity_name=f"PA {workstation.category} {workstation.sequence}",
        action_type='UPDATE',
        description=f"{peripheral_display} alterado para {new_state}"
    )
    
    # Salva com update_fields para garantir que apenas o campo específico seja atualizado
    workstation.save(update_fields=[peripheral, 'updated_at'])
    
    # O status pode ser afetado quando um periférico é alterado
    # Verifica o novo status
    new_status = workstation.status
    
    return JsonResponse({
        'status': 'success',
        'new_value': getattr(workstation, peripheral),
        'workstation_status': new_status,
        'workstation_status_display': dict(Workstation.STATUS_CHOICES)[new_status]
    })

@login_required
@user_passes_test(is_admin)
def history_view(request):
    """View principal para acesso às páginas de histórico."""
    employees = Employee.objects.all().order_by('name')
    
    context = {
        'employees': employees,
        'page_title': 'Histórico do Sistema'
    }
    
    return render(request, 'pam/history/history_main.html', context)

@login_required
@user_passes_test(is_admin)
def employee_history_view(request, employee_id):
    """View para exibir o histórico de posições de um funcionário específico."""
    employee = get_object_or_404(Employee, pk=employee_id)
    
    # Obtem parâmetros de filtragem
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Filtra o histórico do funcionário
    history_query = EmployeePositionHistory.objects.filter(employee=employee).select_related(
        'workstation', 'room', 'island', 'changed_by'
    )
    
    # Aplica filtros de data se fornecidos
    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            history_query = history_query.filter(start_date__gte=start_date_obj)
        except (ValueError, TypeError):
            messages.warning(request, "Formato de data inicial inválido. Usando todos os registros.")
    
    if end_date:
        try:
            from datetime import datetime
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            # Filtra por end_date se o registro tiver terminado ou start_date se ainda estiver ativo
            history_query = history_query.filter(
                models.Q(end_date__lte=end_date_obj) | 
                models.Q(end_date__isnull=True, start_date__lte=end_date_obj)
            )
        except (ValueError, TypeError):
            messages.warning(request, "Formato de data final inválido. Usando todos os registros.")
    
    # Executa a consulta
    employee_history = history_query.order_by('-start_date')
    
    context = {
        'employee': employee,
        'employee_history': employee_history,
        'page_title': f'Histórico de Posicionamento - {employee.name}'
    }
    
    return render(request, 'pam/history/employee_history.html', context)

@login_required
@user_passes_test(is_admin)
def change_log_view(request):
    """View para exibir o log de alterações no sistema."""
    # Obtem parâmetros de filtragem
    entity_type = request.GET.get('entity_type')
    action_type = request.GET.get('action_type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    user_id = request.GET.get('user_id')
    search = request.GET.get('search')
    
    # Cria a consulta base
    logs_query = ChangeLog.objects.all().select_related('user')
    
    # Aplica filtros
    if entity_type:
        logs_query = logs_query.filter(entity_type=entity_type)
    
    if action_type:
        logs_query = logs_query.filter(action_type=action_type)
    
    if user_id:
        try:
            user_id_int = int(user_id)
            logs_query = logs_query.filter(user_id=user_id_int)
        except (ValueError, TypeError):
            pass
    
    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            logs_query = logs_query.filter(created_at__gte=start_date_obj)
        except (ValueError, TypeError):
            messages.warning(request, "Formato de data inicial inválido. Usando todos os registros.")
    
    if end_date:
        try:
            from datetime import datetime, timedelta
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Inclui o final do dia
            logs_query = logs_query.filter(created_at__lt=end_date_obj)
        except (ValueError, TypeError):
            messages.warning(request, "Formato de data final inválido. Usando todos os registros.")
    
    if search:
        # Busca nos campos de texto
        logs_query = logs_query.filter(
            models.Q(entity_name__icontains=search) |
            models.Q(description__icontains=search)
        )
    
    # Paginação
    from django.core.paginator import Paginator
    paginator = Paginator(logs_query.order_by('-created_at'), 25)  # 25 logs por página
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(1)
    
    # Opções para os filtros
    entity_type_choices = ChangeLog.ENTITY_TYPES
    action_type_choices = ChangeLog.ACTION_TYPES
    users = User.objects.filter(
        id__in=ChangeLog.objects.values_list('user_id', flat=True).distinct()
    ).order_by('username')
    
    context = {
        'logs': page_obj,
        'entity_type_choices': entity_type_choices,
        'action_type_choices': action_type_choices,
        'users': users,
        'filters': {
            'entity_type': entity_type,
            'action_type': action_type,
            'start_date': start_date,
            'end_date': end_date,
            'user_id': user_id,
            'search': search,
        },
        'page_title': 'Log de Alterações do Sistema'
    }
    
    return render(request, 'pam/history/change_log.html', context)

@user_passes_test(is_superuser)
@require_POST
def delete_employee_view(request, employee_id):
    """View para deletar um funcionário."""
    employee = get_object_or_404(Employee, pk=employee_id)
    employee_name = employee.name
    
    # Registra a alteração no log
    log_change(
        user=request.user,
        entity_type='EMPLOYEE',
        entity_id=employee_id,
        entity_name=employee_name,
        action_type='DELETE',
        description=f"Funcionário {employee_name} excluído"
    )
    
    employee.delete()
    messages.success(request, f'Funcionário {employee_name} excluído com sucesso.')
    return redirect('pam:unified_management')

@user_passes_test(is_superuser)
@require_POST
def assign_employee_view(request, workstation_id):
    """View para atribuir um funcionário a uma estação de trabalho."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    workstation = get_object_or_404(Workstation, pk=workstation_id)
    employee_id = request.POST.get('employee_id')
    active_tab = request.POST.get('active_tab', '')
    
    result = {
        'success': False,
        'error': None,
        'message': '',
        'employee_name': '',
    }
    
    if employee_id:
        try:
            employee = Employee.objects.get(pk=employee_id)
            workstation.employee = employee
            workstation.status = 'OCCUPIED'
            workstation.save()
            
            # Registra a atribuição no log
            log_change(
                user=request.user,
                entity_type='WORKSTATION',
                entity_id=workstation_id,
                entity_name=f"PA {workstation.category} {workstation.sequence}",
                action_type='ASSIGNMENT',
                description=f"Funcionário {employee.name} atribuído à estação de trabalho"
            )
            
            success_message = f"Funcionário {employee.name} atribuído com sucesso à PA-{workstation.sequence}."
            
            if is_ajax:
                result['success'] = True
                result['message'] = success_message
                result['employee_name'] = employee.name
                return JsonResponse(result)
            else:
                messages.success(request, success_message)
        except Employee.DoesNotExist:
            error_message = "Funcionário não encontrado."
            if is_ajax:
                result['error'] = error_message
                return JsonResponse(result)
            else:
                messages.error(request, error_message)
        except Exception as e:
            error_message = f"Erro ao atribuir funcionário: {str(e)}"
            if is_ajax:
                result['error'] = error_message
                return JsonResponse(result)
            else:
                messages.error(request, error_message)
    
    # Para requisições não-AJAX, redireciona de volta para a página apropriada
    if active_tab == 'workstations':
        return redirect('pam:unified_management')
    else:
        return redirect('pam:manage_workstations')

@user_passes_test(is_superuser)
@require_POST
def remove_employee_view(request, workstation_id):
    """View para remover um funcionário de uma estação de trabalho."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    workstation = get_object_or_404(Workstation, pk=workstation_id)
    
    result = {
        'success': False,
        'error': None,
        'message': '',
    }
    
    if workstation.employee:
        try:
            employee_name = workstation.employee.name
            workstation.employee = None
            workstation.status = 'UNOCCUPIED'
            workstation.save()
            
            # Registra a remoção no log
            log_change(
                user=request.user,
                entity_type='WORKSTATION',
                entity_id=workstation_id,
                entity_name=f"PA {workstation.category} {workstation.sequence}",
                action_type='UNASSIGNMENT',
                description=f"Funcionário {employee_name} removido da estação de trabalho"
            )
            
            success_message = f"Funcionário {employee_name} removido com sucesso da PA-{workstation.sequence}."
            
            if is_ajax:
                result['success'] = True
                result['message'] = success_message
                return JsonResponse(result)
            else:
                messages.success(request, success_message)
        except Exception as e:
            error_message = f"Erro ao remover funcionário: {str(e)}"
            if is_ajax:
                result['error'] = error_message
                return JsonResponse(result)
            else:
                messages.error(request, error_message)
    else:
        error_message = "Esta estação de trabalho não tem funcionário atribuído."
        if is_ajax:
            result['error'] = error_message
            return JsonResponse(result)
        else:
            messages.error(request, error_message)
    
    # Para requisições não-AJAX, redireciona de volta para a página apropriada
    active_tab = request.POST.get('active_tab', '')
    if active_tab == 'workstations':
        return redirect('pam:unified_management')
    else:
        return redirect('pam:manage_workstations')

@user_passes_test(is_superuser)
def get_available_employees_view(request):
    """View para obter funcionários disponíveis (não atribuídos a nenhuma PA)."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if not is_ajax:
        return redirect('pam:manage_workstations')
    
    # Obtém ID da workstation a ser excluída da lista (para troca de funcionário)
    exclude_workstation_id = request.GET.get('exclude_workstation')
    
    # Busca todas as workstations com funcionários atribuídos
    workstations_with_employees = Workstation.objects.exclude(employee=None)
    
    # Se estamos trocando um funcionário, excluímos a workstation atual da lista
    if exclude_workstation_id:
        try:
            workstations_with_employees = workstations_with_employees.exclude(id=exclude_workstation_id)
        except (ValueError, TypeError):
            pass
    
    # Obtém os IDs dos funcionários já atribuídos
    assigned_employee_ids = workstations_with_employees.values_list('employee_id', flat=True)
    
    # Busca funcionários disponíveis
    available_employees = Employee.objects.exclude(id__in=assigned_employee_ids).order_by('name')
    
    # Formata a resposta
    employees_data = [{'id': emp.id, 'name': emp.name} for emp in available_employees]
    
    return JsonResponse({'employees': employees_data})

# --- AJAX CRUD para Funcionários ---
@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_employee_list(request):
    """API para listar funcionários"""
    try:
        employees = Employee.objects.all().order_by('name')
        data = [
            {
                'id': emp.id, 
                'name': emp.name, 
                'sector': emp.sector,
                'sector_display': emp.get_sector_display()
            } 
            for emp in employees
        ]
        return JsonResponse({'success': True, 'employees': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_employee_detail(request, employee_id):
    """API para obter detalhes de um funcionário"""
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        data = {
            'id': employee.id,
            'name': employee.name,
            'sector': employee.sector,
            'sector_display': employee.get_sector_display(),
            'created_at': employee.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': employee.updated_at.strftime('%d/%m/%Y %H:%M'),
        }
        return JsonResponse({'success': True, 'employee': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def api_employee_create(request):
    """API para criar funcionário"""
    try:
        data = json.loads(request.body)
        name = data.get('name')
        sector = data.get('sector')
        
        if not name:
            return JsonResponse({
                'success': False, 
                'error': 'Nome é obrigatório'
            }, status=400)
            
        employee = Employee.objects.create(
            name=name,
            sector=sector or 'INSS'  # Valor padrão se não for fornecido
        )
        
        # Registra a criação no log
        log_change(
            user=request.user,
            entity_type='EMPLOYEE',
            entity_id=employee.id,
            entity_name=employee.name,
            action_type='CREATE',
            description=f"Funcionário '{employee.name}' foi criado"
        )
        
        return JsonResponse({
            'success': True, 
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'sector': employee.sector,
                'sector_display': employee.get_sector_display()
            },
            'message': f'Funcionário {employee.name} criado com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["PUT", "PATCH"])
def api_employee_update(request, employee_id):
    """API para atualizar funcionário"""
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        data = json.loads(request.body)
        
        # Guarda valores originais para o log
        original_name = employee.name
        original_sector = employee.sector
        
        # Atualiza campos
        if 'name' in data and data['name']:
            employee.name = data['name']
        if 'sector' in data:
            employee.sector = data['sector']
            
        employee.save()
        
        # Registra a atualização no log
        changes = []
        if original_name != employee.name:
            changes.append(f"Nome alterado de '{original_name}' para '{employee.name}'")
        if original_sector != employee.sector:
            changes.append(f"Setor alterado de '{original_sector}' para '{employee.sector}'")
            
        if changes:
            log_change(
                user=request.user,
                entity_type='EMPLOYEE',
                entity_id=employee.id,
                entity_name=employee.name,
                action_type='UPDATE',
                description=f"Funcionário atualizado: {', '.join(changes)}"
            )
        
        return JsonResponse({
            'success': True, 
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'sector': employee.sector,
                'sector_display': employee.get_sector_display()
            },
            'message': f'Funcionário {employee.name} atualizado com sucesso'
        })
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Funcionário não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["DELETE"])
def api_employee_delete(request, employee_id):
    """API para excluir funcionário"""
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        name = employee.name  # Salva o nome para usar no log

        # Verifica se o funcionário está associado a alguma estação de trabalho
        if Workstation.objects.filter(employee=employee).exists():
            return JsonResponse({
                'success': False, 
                'error': f'Não é possível excluir {name}. Remova-o primeiro de todas as estações de trabalho.'
            }, status=400)
            
        # Registra a exclusão no log antes de excluir
        log_change(
            user=request.user,
            entity_type='EMPLOYEE',
            entity_id=employee_id,
            entity_name=name,
            action_type='DELETE',
            description=f"Funcionário '{name}' foi excluído"
        )
        
        employee.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Funcionário {name} excluído com sucesso'
        })
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Funcionário não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- AJAX CRUD para Salas ---
@login_required
@user_passes_test(is_superuser)
@require_http_methods(["GET"])
def api_room_list(request):
    """API para listar salas"""
    try:
        rooms = Room.objects.all().order_by('name')
        data = [
            {
                'id': room.id, 
                'name': room.name,
                'islands_count': room.islands.count(),
                'created_at': room.created_at.strftime('%d/%m/%Y %H:%M'),
            } 
            for room in rooms
        ]
        return JsonResponse({'success': True, 'rooms': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["GET"])
def api_room_detail(request, room_id):
    """API para obter detalhes de uma sala"""
    try:
        room = get_object_or_404(Room, id=room_id)
        data = {
            'id': room.id,
            'name': room.name,
            'islands_count': room.islands.count(),
            'islands': [
                {
                    'id': island.id,
                    'name': island.name,
                    'island_number': island.island_number,
                    'category': island.category,
                    'category_display': island.get_category_display(),
                    'workstations_count': island.workstations.count()
                } 
                for island in room.islands.all().order_by('island_number')
            ],
            'created_at': room.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': room.updated_at.strftime('%d/%m/%Y %H:%M'),
        }
        return JsonResponse({'success': True, 'room': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def api_room_create(request):
    """API para criar sala"""
    try:
        data = json.loads(request.body)
        name = data.get('name')
        
        if not name:
            return JsonResponse({
                'success': False, 
                'error': 'Nome da sala é obrigatório'
            }, status=400)
        
        # Verifica se já existe uma sala com esse nome
        if Room.objects.filter(name=name).exists():
            return JsonResponse({
                'success': False, 
                'error': f'Já existe uma sala com o nome "{name}"'
            }, status=400)
            
        room = Room.objects.create(name=name)
        
        # Registra a criação no log
        log_change(
            user=request.user,
            entity_type='ROOM',
            entity_id=room.id,
            entity_name=room.name,
            action_type='CREATE',
            description=f"Sala '{room.name}' foi criada"
        )
        
        return JsonResponse({
            'success': True, 
            'room': {
                'id': room.id,
                'name': room.name,
                'islands_count': 0,
                'created_at': room.created_at.strftime('%d/%m/%Y %H:%M'),
            },
            'message': f'Sala {room.name} criada com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["PUT", "PATCH"])
def api_room_update(request, room_id):
    """API para atualizar sala"""
    try:
        room = get_object_or_404(Room, id=room_id)
        data = json.loads(request.body)
        
        # Guarda valor original para o log
        original_name = room.name
        
        # Atualiza campo de nome se fornecido
        if 'name' in data and data['name']:
            # Verifica se já existe outra sala com o mesmo nome
            if Room.objects.filter(name=data['name']).exclude(id=room_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Já existe uma sala com o nome "{data["name"]}"'
                }, status=400)
                
            room.name = data['name']
            room.save()
        
            # Registra a atualização no log
            if original_name != room.name:
                log_change(
                    user=request.user,
                    entity_type='ROOM',
                    entity_id=room.id,
                    entity_name=room.name,
                    action_type='UPDATE',
                    description=f"Nome da sala alterado de '{original_name}' para '{room.name}'"
                )
        
        return JsonResponse({
            'success': True, 
            'room': {
                'id': room.id,
                'name': room.name,
                'islands_count': room.islands.count(),
                'updated_at': room.updated_at.strftime('%d/%m/%Y %H:%M'),
            },
            'message': f'Sala {room.name} atualizada com sucesso'
        })
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sala não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["DELETE"])
def api_room_delete(request, room_id):
    """API para excluir sala"""
    try:
        room = get_object_or_404(Room, id=room_id)
        name = room.name  # Salva o nome para usar no log
        island_count = room.islands.count()
        
        # Verifica se a sala possui ilhas
        if island_count > 0:
            return JsonResponse({
                'success': False, 
                'error': f'Não é possível excluir a sala {name}. Ela contém {island_count} ilha(s). Remova-as primeiro.'
            }, status=400)
            
        # Registra a exclusão no log antes de excluir
        log_change(
            user=request.user,
            entity_type='ROOM',
            entity_id=room_id,
            entity_name=name,
            action_type='DELETE',
            description=f"Sala '{name}' foi excluída"
        )
        
        room.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Sala {name} excluída com sucesso'
        })
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sala não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- AJAX CRUD para Ilhas ---
@login_required
@user_passes_test(is_superuser)
@require_http_methods(["GET"])
def api_island_list(request):
    """API para listar ilhas"""
    try:
        room_id = request.GET.get('room_id')
        
        # Filtra por sala se fornecido
        islands = Island.objects.select_related('room')
        if room_id:
            islands = islands.filter(room_id=room_id)
            
        islands = islands.order_by('room__name', 'island_number')
        
        data = [
            {
                'id': island.id, 
                'name': island.name,
                'island_number': island.island_number,
                'category': island.category,
                'category_display': island.get_category_display(),
                'room_id': island.room.id,
                'room_name': island.room.name,
                'workstations_count': island.workstations.count(),
                'created_at': island.created_at.strftime('%d/%m/%Y %H:%M'),
            } 
            for island in islands
        ]
        return JsonResponse({'success': True, 'islands': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["GET"])
def api_island_detail(request, island_id):
    """API para obter detalhes de uma ilha"""
    try:
        island = get_object_or_404(Island.objects.select_related('room'), id=island_id)
        
        workstations = island.workstations.select_related('employee').order_by('sequence')
        
        data = {
            'id': island.id,
            'name': island.name,
            'island_number': island.island_number,
            'category': island.category,
            'category_display': island.get_category_display(),
            'room_id': island.room.id,
            'room_name': island.room.name,
            'workstations': [
                {
                    'id': ws.id,
                    'sequence': ws.sequence,
                    'status': ws.status,
                    'status_display': ws.get_status_display(),
                    'category': ws.category,
                    'category_display': ws.get_category_display(),
                    'employee_id': ws.employee.id if ws.employee else None,
                    'employee_name': ws.employee.name if ws.employee else None,
                    'equipment': {
                        'monitor': ws.monitor,
                        'keyboard': ws.keyboard,
                        'mouse': ws.mouse,
                        'mousepad': ws.mousepad,
                        'headset': ws.headset,
                    }
                } 
                for ws in workstations
            ],
            'created_at': island.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': island.updated_at.strftime('%d/%m/%Y %H:%M'),
        }
        return JsonResponse({'success': True, 'island': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def api_island_create(request):
    """API para criar ilha"""
    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')
        island_number = data.get('island_number')
        name = data.get('name')
        category = data.get('category')
        
        # Validações
        if not room_id:
            return JsonResponse({'success': False, 'error': 'Sala é obrigatória'}, status=400)
            
        room = get_object_or_404(Room, id=room_id)
        
        # Se o número da ilha não foi fornecido, pega o próximo disponível
        if not island_number:
            max_island = Island.objects.filter(room=room).order_by('-island_number').first()
            island_number = max_island.island_number + 1 if max_island else 1
            
        # Verifica se já existe uma ilha com esse número na mesma sala
        if Island.objects.filter(room=room, island_number=island_number).exists():
            return JsonResponse({
                'success': False, 
                'error': f'Já existe uma ilha com o número {island_number} na sala {room.name}'
            }, status=400)
            
        # Cria a ilha
        island = Island.objects.create(
            room=room,
            island_number=island_number,
            name=name or str(island_number),  # Usa o número como nome se não fornecido
            category=category or 'INSS'  # Categoria padrão
        )
        
        # Registra a criação no log
        log_change(
            user=request.user,
            entity_type='ISLAND',
            entity_id=island.id,
            entity_name=f"Ilha {island.name} (Sala {room.name})",
            action_type='CREATE',
            description=f"Ilha '{island.name}' foi criada na sala '{room.name}'"
        )
        
        return JsonResponse({
            'success': True, 
            'island': {
                'id': island.id,
                'name': island.name,
                'island_number': island.island_number,
                'category': island.category,
                'category_display': island.get_category_display(),
                'room_id': room.id,
                'room_name': room.name,
                'workstations_count': 0,
                'created_at': island.created_at.strftime('%d/%m/%Y %H:%M'),
            },
            'message': f'Ilha {island.name} criada com sucesso na sala {room.name}'
        })
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sala não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["PUT", "PATCH"])
def api_island_update(request, island_id):
    """API para atualizar ilha"""
    try:
        island = get_object_or_404(Island.objects.select_related('room'), id=island_id)
        data = json.loads(request.body)
        
        # Guarda valores originais para o log
        original_name = island.name
        original_number = island.island_number
        original_category = island.category
        original_room = island.room
        
        # Campos que podem ser atualizados
        fields_updated = []
        
        # Atualiza o nome
        if 'name' in data and data['name'] and data['name'] != island.name:
            island.name = data['name']
            fields_updated.append(f"Nome alterado de '{original_name}' para '{island.name}'")
            
        # Atualiza o número da ilha
        if 'island_number' in data and data['island_number'] != island.island_number:
            # Verifica se o novo número já existe na mesma sala
            if Island.objects.filter(room=island.room, island_number=data['island_number']).exclude(id=island_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Já existe uma ilha com o número {data["island_number"]} na sala {island.room.name}'
                }, status=400)
                
            island.island_number = data['island_number']
            fields_updated.append(f"Número alterado de {original_number} para {island.island_number}")
            
        # Atualiza a categoria
        if 'category' in data and data['category'] != island.category:
            island.category = data['category']
            fields_updated.append(f"Categoria alterada de '{island.get_category_display()}' para '{Island.CATEGORY_CHOICES[next((i for i, v in enumerate(Island.CATEGORY_CHOICES) if v[0] == data['category']), 0)][1]}'")
            
        # Atualiza a sala
        if 'room_id' in data and data['room_id'] and data['room_id'] != island.room.id:
            new_room = get_object_or_404(Room, id=data['room_id'])
            
            # Verifica se já existe uma ilha com o mesmo número na nova sala
            if Island.objects.filter(room=new_room, island_number=island.island_number).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Já existe uma ilha com o número {island.island_number} na sala {new_room.name}'
                }, status=400)
                
            island.room = new_room
            fields_updated.append(f"Sala alterada de '{original_room.name}' para '{new_room.name}'")
        
        if fields_updated:
            island.save()
            
            # Registra a atualização no log
            log_change(
                user=request.user,
                entity_type='ISLAND',
                entity_id=island.id,
                entity_name=f"Ilha {island.name} (Sala {island.room.name})",
                action_type='UPDATE',
                description=f"Ilha atualizada: {', '.join(fields_updated)}"
            )
        
        return JsonResponse({
            'success': True, 
            'island': {
                'id': island.id,
                'name': island.name,
                'island_number': island.island_number,
                'category': island.category,
                'category_display': island.get_category_display(),
                'room_id': island.room.id,
                'room_name': island.room.name,
                'workstations_count': island.workstations.count(),
                'updated_at': island.updated_at.strftime('%d/%m/%Y %H:%M'),
            },
            'message': f'Ilha {island.name} atualizada com sucesso'
        })
    except Island.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ilha não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["DELETE"])
def api_island_delete(request, island_id):
    """API para excluir ilha"""
    try:
        island = get_object_or_404(Island.objects.select_related('room'), id=island_id)
        room_name = island.room.name
        island_name = island.name
        
        # Verifica se a ilha possui estações de trabalho
        workstations_count = island.workstations.count()
        if workstations_count > 0:
            return JsonResponse({
                'success': False, 
                'error': f'Não é possível excluir a ilha {island_name}. Ela contém {workstations_count} estação(ões) de trabalho. Remova-as primeiro.'
            }, status=400)
            
        # Registra a exclusão no log antes de excluir
        log_change(
            user=request.user,
            entity_type='ISLAND',
            entity_id=island_id,
            entity_name=f"Ilha {island_name} (Sala {room_name})",
            action_type='DELETE',
            description=f"Ilha '{island_name}' da sala '{room_name}' foi excluída"
        )
        
        island.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Ilha {island_name} da sala {room_name} excluída com sucesso'
        })
    except Island.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ilha não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- AJAX CRUD para Estações de Trabalho ---
@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_workstation_list(request):
    """API para listar estações de trabalho"""
    try:
        # Parâmetros de filtro opcionais
        island_id = request.GET.get('island_id')
        room_id = request.GET.get('room_id')
        status = request.GET.get('status')
        category = request.GET.get('category')
        
        # Consulta base com todas as relações necessárias
        workstations = Workstation.objects.select_related('employee', 'island', 'island__room')
        
        # Aplicação dos filtros
        if island_id:
            workstations = workstations.filter(island_id=island_id)
        if room_id:
            workstations = workstations.filter(island__room_id=room_id)
        if status:
            workstations = workstations.filter(status=status)
        if category:
            workstations = workstations.filter(category=category)
            
        # Ordenação
        workstations = workstations.order_by('island__room__name', 'island__island_number', 'sequence')
        
        data = [
            {
                'id': ws.id,
                'sequence': ws.sequence,
                'status': ws.status,
                'status_display': ws.get_status_display(),
                'category': ws.category,
                'category_display': ws.get_category_display(),
                'employee_id': ws.employee.id if ws.employee else None,
                'employee_name': ws.employee.name if ws.employee else None,
                'island_id': ws.island.id if ws.island else None,
                'island_name': f"{ws.island.name} (Sala {ws.island.room.name})" if ws.island else None,
                'room_id': ws.island.room.id if ws.island and ws.island.room else None,
                'room_name': ws.island.room.name if ws.island and ws.island.room else None,
                'equipment': {
                    'monitor': ws.monitor,
                    'keyboard': ws.keyboard,
                    'mouse': ws.mouse,
                    'mousepad': ws.mousepad,
                    'headset': ws.headset,
                },
                'created_at': ws.created_at.strftime('%d/%m/%Y %H:%M'),
            } 
            for ws in workstations
        ]
        return JsonResponse({'success': True, 'workstations': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_workstation_detail(request, workstation_id):
    """API para obter detalhes de uma estação de trabalho"""
    try:
        workstation = get_object_or_404(
            Workstation.objects.select_related('employee', 'island', 'island__room'), 
            id=workstation_id
        )
        
        # Histórico de atribuições
        history = EmployeePositionHistory.objects.filter(
            workstation=workstation
        ).select_related('employee', 'changed_by').order_by('-start_date')[:10]
        
        history_data = [
            {
                'employee_id': h.employee.id,
                'employee_name': h.employee.name,
                'start_date': h.start_date.strftime('%d/%m/%Y %H:%M'),
                'end_date': h.end_date.strftime('%d/%m/%Y %H:%M') if h.end_date else None,
                'changed_by': h.changed_by.username if h.changed_by else None,
            }
            for h in history
        ]
        
        data = {
            'id': workstation.id,
            'sequence': workstation.sequence,
            'status': workstation.status,
            'status_display': workstation.get_status_display(),
            'category': workstation.category,
            'category_display': workstation.get_category_display(),
            'employee': {
                'id': workstation.employee.id,
                'name': workstation.employee.name,
                'sector': workstation.employee.sector,
                'sector_display': workstation.employee.get_sector_display(),
            } if workstation.employee else None,
            'island': {
                'id': workstation.island.id,
                'name': workstation.island.name,
                'island_number': workstation.island.island_number,
                'room_id': workstation.island.room.id,
                'room_name': workstation.island.room.name,
            } if workstation.island else None,
            'equipment': {
                'monitor': workstation.monitor,
                'keyboard': workstation.keyboard,
                'mouse': workstation.mouse,
                'mousepad': workstation.mousepad,
                'headset': workstation.headset,
            },
            'history': history_data,
            'created_at': workstation.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': workstation.updated_at.strftime('%d/%m/%Y %H:%M'),
        }
        return JsonResponse({'success': True, 'workstation': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def api_workstation_create(request):
    """API para criar estação de trabalho"""
    try:
        data = json.loads(request.body)
        
        # Campos obrigatórios
        island_id = data.get('island_id')
        category = data.get('category')
        
        # Validações
        if not island_id:
            return JsonResponse({'success': False, 'error': 'Ilha é obrigatória'}, status=400)
            
        island = get_object_or_404(Island.objects.select_related('room'), id=island_id)
        
        # Se não houver categoria, usa a da ilha
        if not category:
            category = island.category
            
        # Determina a próxima sequência disponível na categoria
        sequence = data.get('sequence')
        if not sequence:
            max_workstation = Workstation.objects.filter(category=category).order_by('-sequence').first()
            sequence = max_workstation.sequence + 1 if max_workstation else 1
            
        # Verifica se a sequência já existe para a categoria
        if Workstation.objects.filter(category=category, sequence=sequence).exists():
            return JsonResponse({
                'success': False, 
                'error': f'Já existe uma estação de trabalho com a sequência {sequence} na categoria {category}'
            }, status=400)
            
        # Define equipamentos
        monitor = data.get('monitor', True)
        keyboard = data.get('keyboard', True)
        mouse = data.get('mouse', True)
        mousepad = data.get('mousepad', True)
        headset = data.get('headset', True)
        
        # Cria a estação de trabalho
        workstation = Workstation.objects.create(
            island=island,
            category=category,
            sequence=sequence,
            monitor=monitor,
            keyboard=keyboard,
            mouse=mouse,
            mousepad=mousepad,
            headset=headset
        )
        
        # Atribui funcionário, se fornecido
        employee_id = data.get('employee_id')
        if employee_id:
            try:
                employee = Employee.objects.get(id=employee_id)
                workstation.employee = employee
                workstation.save()
            except Employee.DoesNotExist:
                pass  # Ignora se o funcionário não existir
        
        # Registra a criação no log
        log_change(
            user=request.user,
            entity_type='WORKSTATION',
            entity_id=workstation.id,
            entity_name=f"PA {workstation.category} {workstation.sequence}",
            action_type='CREATE',
            description=f"Estação de trabalho criada na ilha {island.name} (Sala {island.room.name})"
        )
        
        return JsonResponse({
            'success': True, 
            'workstation': {
                'id': workstation.id,
                'sequence': workstation.sequence,
                'status': workstation.status,
                'status_display': workstation.get_status_display(),
                'category': workstation.category,
                'category_display': workstation.get_category_display(),
                'employee_id': workstation.employee.id if workstation.employee else None,
                'employee_name': workstation.employee.name if workstation.employee else None,
                'island_id': island.id,
                'island_name': island.name,
                'room_id': island.room.id,
                'room_name': island.room.name,
            },
            'message': f'Estação de trabalho PA{workstation.sequence} criada com sucesso'
        })
    except Island.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ilha não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["PUT", "PATCH"])
def api_workstation_update(request, workstation_id):
    """API para atualizar estação de trabalho"""
    try:
        workstation = get_object_or_404(
            Workstation.objects.select_related('employee', 'island', 'island__room'), 
            id=workstation_id
        )
        data = json.loads(request.body)
        
        # Guarda valores originais para o log
        original_status = workstation.status
        original_sequence = workstation.sequence
        original_category = workstation.category
        original_island = workstation.island
        original_employee = workstation.employee
        original_monitor = workstation.monitor
        original_keyboard = workstation.keyboard
        original_mouse = workstation.mouse
        original_mousepad = workstation.mousepad
        original_headset = workstation.headset
        
        # Campos que podem ser atualizados
        fields_updated = []
        
        # Atualiza a sequência
        if 'sequence' in data and data['sequence'] != workstation.sequence:
            # Verifica se a nova sequência já existe na mesma categoria
            if Workstation.objects.filter(category=workstation.category, sequence=data['sequence']).exclude(id=workstation_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Já existe uma estação de trabalho com a sequência {data["sequence"]} na categoria {workstation.category}'
                }, status=400)
                
            workstation.sequence = data['sequence']
            fields_updated.append(f"Sequência alterada de {original_sequence} para {workstation.sequence}")
            
        # Atualiza a categoria
        if 'category' in data and data['category'] != workstation.category:
            # Verifica se a sequência já existe na nova categoria
            if Workstation.objects.filter(category=data['category'], sequence=workstation.sequence).exclude(id=workstation_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Já existe uma estação de trabalho com a sequência {workstation.sequence} na categoria {data["category"]}'
                }, status=400)
                
            workstation.category = data['category']
            fields_updated.append(f"Categoria alterada de '{workstation.get_category_display()}' para '{dict(Workstation.CATEGORY_CHOICES).get(data['category'])}'")
            
        # Atualiza a ilha
        if 'island_id' in data and data['island_id'] and (not workstation.island or data['island_id'] != workstation.island.id):
            try:
                new_island = Island.objects.select_related('room').get(id=data['island_id'])
                workstation.island = new_island
                fields_updated.append(f"Ilha alterada de '{original_island.name if original_island else 'Nenhuma'}' para '{new_island.name}'")
            except Island.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Ilha não encontrada'}, status=404)
                
        # Atualiza o funcionário
        if 'employee_id' in data:
            if data['employee_id'] is None or data['employee_id'] == '':
                # Remover funcionário
                if workstation.employee:
                    old_employee_name = workstation.employee.name
                    workstation.employee = None
                    fields_updated.append(f"Funcionário '{old_employee_name}' removido")
            else:
                # Atribuir novo funcionário
                try:
                    new_employee = Employee.objects.get(id=data['employee_id'])
                    if not workstation.employee or workstation.employee.id != new_employee.id:
                        old_employee_name = workstation.employee.name if workstation.employee else 'Nenhum'
                        workstation.employee = new_employee
                        fields_updated.append(f"Funcionário alterado de '{old_employee_name}' para '{new_employee.name}'")
                except Employee.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Funcionário não encontrado'}, status=404)
                    
        # Atualiza equipamentos
        equipment_updates = []
        if 'monitor' in data and data['monitor'] != workstation.monitor:
            workstation.monitor = data['monitor']
            equipment_updates.append(f"Monitor: {'Sim' if data['monitor'] else 'Não'}")
            
        if 'keyboard' in data and data['keyboard'] != workstation.keyboard:
            workstation.keyboard = data['keyboard']
            equipment_updates.append(f"Teclado: {'Sim' if data['keyboard'] else 'Não'}")
            
        if 'mouse' in data and data['mouse'] != workstation.mouse:
            workstation.mouse = data['mouse']
            equipment_updates.append(f"Mouse: {'Sim' if data['mouse'] else 'Não'}")
            
        if 'mousepad' in data and data['mousepad'] != workstation.mousepad:
            workstation.mousepad = data['mousepad']
            equipment_updates.append(f"Mousepad: {'Sim' if data['mousepad'] else 'Não'}")
            
        if 'headset' in data and data['headset'] != workstation.headset:
            workstation.headset = data['headset']
            equipment_updates.append(f"Fone: {'Sim' if data['headset'] else 'Não'}")
            
        if equipment_updates:
            fields_updated.append(f"Equipamentos atualizados: {', '.join(equipment_updates)}")
            
        # Atualiza o status manualmente se solicitado
        if 'status' in data and data['status'] != workstation.status:
            workstation.status = data['status']
            fields_updated.append(f"Status alterado de '{dict(Workstation.STATUS_CHOICES).get(original_status)}' para '{dict(Workstation.STATUS_CHOICES).get(data['status'])}'")
        
        # Salva as alterações
        if fields_updated:
            workstation.save()
            
            # Registra a atualização no log
            log_change(
                user=request.user,
                entity_type='WORKSTATION',
                entity_id=workstation.id,
                entity_name=f"PA {workstation.category} {workstation.sequence}",
                action_type='UPDATE',
                description=f"Estação de trabalho atualizada: {', '.join(fields_updated)}"
            )
        
        # Obtém a estação de trabalho atualizada
        updated_workstation = Workstation.objects.select_related('employee', 'island', 'island__room').get(id=workstation_id)
        
        return JsonResponse({
            'success': True, 
            'workstation': {
                'id': updated_workstation.id,
                'sequence': updated_workstation.sequence,
                'status': updated_workstation.status,
                'status_display': updated_workstation.get_status_display(),
                'category': updated_workstation.category,
                'category_display': updated_workstation.get_category_display(),
                'employee_id': updated_workstation.employee.id if updated_workstation.employee else None,
                'employee_name': updated_workstation.employee.name if updated_workstation.employee else None,
                'island_id': updated_workstation.island.id if updated_workstation.island else None,
                'island_name': updated_workstation.island.name if updated_workstation.island else None,
                'room_id': updated_workstation.island.room.id if updated_workstation.island and updated_workstation.island.room else None,
                'room_name': updated_workstation.island.room.name if updated_workstation.island and updated_workstation.island.room else None,
            },
            'message': f'Estação de trabalho PA{updated_workstation.sequence} atualizada com sucesso'
        })
    except Workstation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Estação de trabalho não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["DELETE"])
def api_workstation_delete(request, workstation_id):
    """API para excluir estação de trabalho"""
    try:
        workstation = get_object_or_404(Workstation, id=workstation_id)
        description = f"PA {workstation.category} {workstation.sequence}"
        
        # Registra a exclusão no log antes de excluir
        log_change(
            user=request.user,
            entity_type='WORKSTATION',
            entity_id=workstation_id,
            entity_name=description,
            action_type='DELETE',
            description=f"Estação de trabalho '{description}' foi excluída"
        )
        
        workstation.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Estação de trabalho {description} excluída com sucesso'
        })
    except Workstation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Estação de trabalho não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

class HttpMethodMiddleware:
    """
    Middleware para processar métodos HTTP PUT e DELETE que não são nativamente
    suportados por todos os navegadores em formulários HTML.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Processa o método HTTP real a partir do X-HTTP-Method-Override header
        # ou do campo _method em POST
        if request.method == 'POST':
            http_method = request.META.get('HTTP_X_HTTP_METHOD_OVERRIDE')
            
            if not http_method and request.POST.get('_method'):
                http_method = request.POST.get('_method').upper()
                
            if http_method in ['PUT', 'PATCH', 'DELETE']:
                request.method = http_method
                
                # Para PUT/PATCH, precisamos processar o corpo da requisição
                if http_method in ['PUT', 'PATCH']:
                    request.PUT = request.POST.copy()
                    
                # Para DELETE, não precisamos de conteúdo
        
        # Continua com o processamento normal da requisição
        response = self.get_response(request)
        return response