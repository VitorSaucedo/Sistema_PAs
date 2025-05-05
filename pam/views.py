from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from .models import Workstation, Employee, Room, Island
from .forms import WorkstationForm, RoomForm, EmployeeForm, LoginForm
from django.http import JsonResponse
from django.db.models import Prefetch
from django.views.decorators.http import require_POST
from django.http import Http404 # Import Http404
import math # Add math import
from django.db.models.query import Prefetch
from django.db import transaction

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
                        elif submitted_employee_id:
                            try:
                                submitted_employee_id_int = int(submitted_employee_id)
                                if original_employee is None or original_employee.id != submitted_employee_id_int:
                                    # Busca o funcionário SE houver mudança ou for nova atribuição
                                    # Idealmente, ter um cache de funcionários aqui seria mais eficiente se muitos forem alterados
                                    selected_employee = Employee.objects.get(pk=submitted_employee_id_int)
                                    workstation.employee = selected_employee
                                    employee_changed = True
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
                        else:
                             errors_found.append(f"Erro: Status '{submitted_status}' inválido para PA {ws_id}.")
                             continue # Não processa mais esta PA se status for inválido

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
                                category=island_category, # *** NOVO: Usa a categoria da ilha ***
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
    employees = Employee.objects.all().order_by('name')
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
    
    if request.method == 'POST':
        form = WorkstationForm(request.POST)
        
        # Vamos verificar se a ilha pertence à sala selecionada
        island_id = request.POST.get('island')
        room_id = request.POST.get('room')
        
        if island_id and room_id:
            try:
                island = Island.objects.get(id=island_id)
                if str(island.room_id) != room_id:
                    messages.error(request, "A ilha selecionada não pertence à sala selecionada!")
                    form.add_error('island', "A ilha selecionada não pertence à sala selecionada.")
            except Island.DoesNotExist:
                form.add_error('island', "Ilha não encontrada.")
        
        if form.is_valid():
            try:
                workstation = form.save(commit=False)
                
                # Encontrar o próximo número de sequência disponível para a categoria
                last_workstation = Workstation.objects.filter(
                    category=workstation.category
                ).order_by('-sequence').first()
                
                workstation.sequence = 1
                if last_workstation:
                    workstation.sequence = last_workstation.sequence + 1
                
                workstation.save()
                messages.success(request, "Estação de trabalho adicionada com sucesso!")
                return redirect('pam:manage_workstations')
            except Exception as e:
                messages.error(request, f"Erro ao adicionar estação de trabalho: {str(e)}")
    else:
        form = WorkstationForm()
    
    context = {
        'workstations': workstations,
        'islands': islands,
        'employees': employees,
        'form': form,
        'rooms': rooms
    }
    return render(request, 'pam/manage_workstations.html', context)

@user_passes_test(is_superuser)
@require_POST
def delete_room_view(request, room_id):
    """View para deletar uma sala."""
    room = get_object_or_404(Room, id=room_id)
    room.delete()
    messages.success(request, "Sala removida com sucesso!")
    return redirect('pam:manage_rooms')

@user_passes_test(is_superuser)
@require_POST
def delete_island_view(request, island_id):
    """View para deletar uma ilha."""
    island = get_object_or_404(Island, id=island_id)
    island.delete()
    messages.success(request, "Ilha removida com sucesso!")
    return redirect('pam:manage_islands')

@user_passes_test(is_superuser)
@require_POST
def delete_workstation_view(request, workstation_id):
    """View para deletar uma estação de trabalho."""
    workstation = get_object_or_404(Workstation, id=workstation_id)
    workstation.delete()
    messages.success(request, "Estação de trabalho removida com sucesso!")
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
    
    if request.method == 'POST' and 'workstation_submit' in request.POST:
        form_submitted = True
        active_tab = 'workstations'
        workstation_form = WorkstationForm(request.POST)
        
        # Verificar se a ilha pertence à sala selecionada
        island_id = request.POST.get('island')
        room_id = request.POST.get('room')
        
        if island_id and room_id:
            try:
                island = Island.objects.get(id=island_id)
                if str(island.room_id) != room_id:
                    messages.error(request, "A ilha selecionada não pertence à sala selecionada!")
                    workstation_form.add_error('island', "A ilha selecionada não pertence à sala selecionada.")
            except Island.DoesNotExist:
                workstation_form.add_error('island', "Ilha não encontrada.")
        
        if workstation_form.is_valid():
            try:
                workstation = workstation_form.save(commit=False)
                last_workstation = Workstation.objects.filter(
                    category=workstation.category
                ).order_by('-sequence').first()
                
                workstation.sequence = 1
                if last_workstation:
                    workstation.sequence = last_workstation.sequence + 1
                
                workstation.save()
                messages.success(request, "Estação de trabalho adicionada com sucesso!")
                return redirect('pam:unified_management')
            except Exception as e:
                messages.error(request, f"Erro ao adicionar estação de trabalho: {str(e)}")
    
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
        # Funcionários
        'employees': employees,
        'employee_form': employee_form,
    }
    
    return render(request, 'pam/unified_management.html', context)

@user_passes_test(is_superuser)
@require_POST
def toggle_peripheral_view(request, workstation_id):
    """
    View para alternar o estado de um periférico (monitor, teclado, mouse, mousepad, headset)
    em uma estação de trabalho específica.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Requisição inválida.'}, status=400)
    
    try:
        workstation = get_object_or_404(Workstation, id=workstation_id)
        peripheral_type = request.POST.get('peripheral_type')
        
        if peripheral_type not in ['monitor', 'keyboard', 'mouse', 'mousepad', 'headset']:
            return JsonResponse({
                'success': False, 
                'error': 'Tipo de periférico inválido.'
            }, status=400)
        
        # Inverte o estado atual do periférico
        current_value = getattr(workstation, peripheral_type)
        setattr(workstation, peripheral_type, not current_value)
        
        # Salva a workstation com o campo atualizado
        workstation.save(update_fields=[peripheral_type])
        
        # Retorna o novo estado do periférico
        return JsonResponse({
            'success': True,
            'peripheral_type': peripheral_type,
            'new_state': getattr(workstation, peripheral_type),
            'workstation_id': workstation.id
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erro ao atualizar periférico: {str(e)}'
        }, status=500)
