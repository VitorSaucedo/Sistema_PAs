import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pas.settings')
django.setup()

from pam.models import Employee, Workstation

def clear_data():
    """Limpa os dados existentes"""
    Workstation.objects.all().delete()
    Employee.objects.all().delete()

def populate():
    # Limpa dados existentes
    clear_data()
    
    # Cria funcionários com numeração específica
    employees = [
        {'name': 'Ana Maria', 'pa_number': 1},
        {'name': 'Maria Souza', 'pa_number': 2}, 
        {'name': 'Carlos Oliveira', 'pa_number': 3},
        {'name': 'Ana Santos', 'pa_number': 4},
        {'name': 'Pedro Costa', 'pa_number': 5},
        {'name': 'Mariana Lima', 'pa_number': 6},
        {'name': 'Lucas Pereira', 'pa_number': 7},
        {'name': 'Juliana Almeida', 'pa_number': 8},
        {'name': 'Ricardo Fernandes', 'pa_number': 9},
        {'name': 'Patrícia Gomes', 'pa_number': 10}
    ]
    
    # Cria e salva funcionários
    created_employees = []
    for emp in employees:
        e = Employee.objects.create(name=emp['name'])
        created_employees.append({'obj': e, 'pa_number': emp['pa_number']})
    
    # Cria 12 estações (6x2) com numeração correta
    categories = ['ESTAGIO', 'INSS', 'SIAPE_DION', 'SIAPE_LEO']
    
    for i in range(1, 13):
        cat = categories[i % len(categories)]
        # Encontra funcionário com PA correspondente
        emp = next((e for e in created_employees if e['pa_number'] == i), None)
        
        Workstation.objects.create(
            category=cat,
            sequence=i,
            employee=emp['obj'] if emp else None,
            monitor=i != 3,  # Estação 3 sem monitor
            keyboard=i != 5, # Estação 5 sem teclado
            mouse=i != 8,    # Estação 8 sem mouse
            headset=i % 2 == 0  # Headset nas estações pares
        )
    
    print("Dados populados com sucesso!")
    print(f"- {len(created_employees)} funcionários criados")
    print("- 12 estações de trabalho criadas com numeração específica")

if __name__ == '__main__':
    print("Populando banco de dados...")
    populate()