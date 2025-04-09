from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from .models import Workstation, Employee, Room, Island
from .forms import WorkstationForm, RoomForm
from django.http import JsonResponse
from django.db.models import Prefetch
from django.views.decorators.http import require_POST
from django.http import Http404 # Import Http404
import math # Add math import

def is_admin(user):
    return user.is_authenticated and user.is_staff

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

@user_passes_test(is_admin)
def admin_office_view(request):
    """Visualização administrativa do escritório, organizada por Salas e Ilhas"""
    error_message = None # Keep error message handling

    # --- POST Logic (Handling Workstation Updates) ---
    # This logic remains largely the same, targeting individual workstations
    if request.method == 'POST':
        modified_pa_id = request.POST.get('modified_pa')
        if modified_pa_id:
            try:
                # Use select_related for efficiency when getting workstation
                workstation = Workstation.objects.select_related('employee', 'island', 'island__room').get(id=modified_pa_id)
                form = WorkstationForm(request.POST, instance=workstation, prefix=modified_pa_id)
                if form.is_valid():
                    # Save form first (might update employee)
                    workstation = form.save(commit=False) # Don't commit yet
                    
                    # Get submitted status
                    submitted_status = request.POST.get(f'{modified_pa_id}-status')
                    
                    # Apply status logic
                    if submitted_status == 'UNOCCUPIED':
                        workstation.employee = None
                        workstation.status = 'UNOCCUPIED'
                    elif submitted_status == 'MAINTENANCE':
                        workstation.status = 'MAINTENANCE'
                    elif submitted_status == 'OCCUPIED':
                         # Ensure employee is assigned if status is OCCUPIED
                        if not workstation.employee:
                             raise ValueError("Não é possível definir o status como 'Ocupado' sem um funcionário atribuído.")
                        workstation.status = 'OCCUPIED'
                    elif submitted_status in dict(Workstation.STATUS_CHOICES): # Allow other valid statuses
                        workstation.status = submitted_status
                    else:
                        # Keep original status if submitted is invalid? Or raise error?
                        # Let's keep original for now if invalid status submitted
                        pass # Keep workstation.status as is

                    # Save the final state
                    # Specify fields to update for efficiency and avoid accidental overwrites
                    update_fields = ['employee', 'status']
                    # Include equipment fields if they are editable via the form
                    # equipment_fields = ['monitor', 'keyboard', 'mouse', 'headset']
                    # update_fields.extend(equipment_fields)
                    workstation.save(update_fields=update_fields)
                    messages.success(request, 'Alterações salvas com sucesso!')

                else: # Form is invalid
                    error_message = 'Erro ao salvar: Dados inválidos no formulário.'
                    # Log detailed errors (optional but helpful)
                    print(f"Form errors for PA {modified_pa_id}: {form.errors.as_json()}")
            except Workstation.DoesNotExist:
                error_message = 'Erro: Estação de trabalho não encontrada.'
            except ValueError as ve: # Catch specific error for OCCUPIED without employee
                 error_message = f'Erro ao salvar: {str(ve)}'
            except Exception as e:
                error_message = f'Erro inesperado ao salvar alterações: {str(e)}'
                print(f"Unexpected error saving workstation {modified_pa_id}: {str(e)}") # Log unexpected errors
        else:
            error_message = 'Nenhuma estação de trabalho foi identificada para modificação.'
        
        # Redirect after POST processing
        if error_message:
            messages.error(request, error_message)
        return redirect('pam:admin_office_view') # Always redirect after POST

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
    workstations_per_island_str = [
        request.POST.get(f'island_{i}_workstations', '0')
        for i in range(1, int(num_islands_str) + 1) # Cuidado com conversão aqui
    ]

    errors = {}
    try:
        num_islands = int(num_islands_str)
        if num_islands <= 0:
             errors['counts'] = ['Número de ilhas deve ser positivo.']

        workstations_per_island = []
        for count_str in workstations_per_island_str:
            count = int(count_str)
            if count <= 0:
                 errors.setdefault('counts', []).append('Número de workstations por ilha deve ser positivo.')
            workstations_per_island.append(count)

        if not errors and room_form.is_valid():
            room = room_form.save() # Salva a sala

            # Cria ilhas e workstations
            for i in range(num_islands):
                island_num = i + 1
                num_workstations = workstations_per_island[i]
                island = Island.objects.create(
                    room=room,
                    island_number=island_num
                )
                for j in range(num_workstations):
                    # Lógica de criação da workstation (manter simples por agora)
                    Workstation.objects.create(
                        island=island,
                        status='UNOCCUPIED',
                         # Definir sequence/category aqui se necessário
                         # sequence = j + 1,
                         # category = 'DEFAULT',
                    )
            return JsonResponse({'success': True}) # Sucesso!

        else:
            # Coleta erros do RoomForm
            for field, field_errors in room_form.errors.items():
                 errors[field] = field_errors
            # Adiciona outros erros já coletados
            return JsonResponse({'success': False, 'errors': errors})

    except ValueError: # Erro na conversão de números
        errors.setdefault('counts', []).append('Valores inválidos para número de ilhas ou workstations.')
        return JsonResponse({'success': False, 'errors': errors})
    except Exception as e: # Erro inesperado no banco ou outro
        print(f"Erro inesperado em add_room_ajax_view: {e}") # Log do erro
        errors['__all__'] = ['Ocorreu um erro interno ao salvar a sala.']
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
