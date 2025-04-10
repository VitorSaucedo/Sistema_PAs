import os
import sys
import django
import random
from faker import Faker
import argparse

# Configura o ambiente Django
# Ajuste 'Sistema_PAs.settings' se o nome do seu projeto for diferente
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Se o script estiver na raiz, o diretório do projeto é o próprio project_path
sys.path.append(project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pas.settings') # <- Corrigido para minúsculas
django.setup()

# Importa o modelo APÓS configurar o Django
from pam.models import Employee
from django.db import IntegrityError

def format_phone_number(digits):
    """Formata 11 dígitos no padrão (XX) XXXXX-XXXX."""
    if len(digits) == 11:
        return f'({digits[:2]}) {digits[2:7]}-{digits[7:]}'
    elif len(digits) == 10: # Para números fixos antigos
         return f'({digits[:2]}) {digits[2:6]}-{digits[6:]}'
    return "".join(digits) # Retorna original se não tiver 10 ou 11

def populate(N=10):
    """Cria N funcionários fictícios."""
    fake = Faker('pt_BR')
    created_count = 0

    print(f"Populando banco de dados com {N} funcionários...")

    # Pega as opções válidas do modelo
    sector_choices = [choice[0] for choice in Employee.SECTOR_CHOICES]

    for _ in range(N):
        try:
            name = fake.name()
            cpf = fake.cpf()
            # Usar fake.unique para reduzir colisões iniciais, mas o try/except é a garantia
            email = fake.unique.email()
            # Gerar 10 ou 11 dígitos aleatórios para o telefone
            phone_digits = ''.join([str(random.randint(0, 9)) for _ in range(random.choice([10, 11]))])
            phone = format_phone_number(phone_digits)
            sector = random.choice(sector_choices)

            Employee.objects.create(
                name=name,
                cpf=cpf,
                email=email,
                phone=phone,
                sector=sector
            )
            created_count += 1
            # Limpa o histórico do unique.email para permitir mais variedade se N for grande
            # Isso pode aumentar a chance de IntegrityError, mas evita esgotar emails únicos rapidamente
            if created_count % 100 == 0: 
                fake.unique.clear()

        except IntegrityError as e:
            # Erro comum se CPF ou Email já existir
            print(f"Aviso: Não foi possível criar funcionário (possível duplicata de CPF/Email): {e}")
            # Limpa o unique.email se a falha foi por ele
            if 'email' in str(e).lower():
                 fake.unique.clear()
            pass # Continua para o próximo
        except Exception as e:
             print(f"Erro inesperado ao criar funcionário: {e}")
             pass

    print(f"População concluída. {created_count} funcionários criados.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Popula o banco de dados com funcionários fictícios.')
    parser.add_argument('count', type=int, default=10, nargs='?',
                        help='Número de funcionários a serem criados (padrão: 10)')
    args = parser.parse_args()

    populate(args.count) 