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

def populate():
    """Cria funcionários fictícios com base em contagens por categoria."""
    fake = Faker('pt_BR')
    created_count = 0
    total_attempted = 0

    # Define as categorias e quantos funcionários criar para cada uma
    categories_to_populate = {
        "INSS": 10,
        "Estágio": 8,
        "SIAPE Dion": 12,
        "SIAPE Leo": 10,
    }

    print("Populando banco de dados com funcionários...")

    # Pega as opções válidas do modelo (para validação, se necessário, mas não para escolha aleatória)
    # sector_choices = [choice[0] for choice in Employee.SECTOR_CHOICES]

    for sector, count in categories_to_populate.items():
        print(f"  Criando {count} funcionários para o setor: {sector}...")
        sector_created_count = 0
        attempts = 0
        max_attempts = count * 2 # Tenta no máximo o dobro para evitar loop infinito com muitas colisões

        while sector_created_count < count and attempts < max_attempts:
            total_attempted += 1
            attempts += 1
            try:
                name = fake.name()
                cpf = fake.cpf()
                email = fake.unique.email() # Tenta gerar email único
                phone_digits = ''.join([str(random.randint(0, 9)) for _ in range(random.choice([10, 11]))])
                phone = format_phone_number(phone_digits)
                # sector é definido pelo loop externo

                Employee.objects.create(
                    name=name,
                    cpf=cpf,
                    email=email,
                    phone=phone,
                    sector=sector # Define o setor específico
                )
                created_count += 1
                sector_created_count += 1
                
                # Limpa unique email com menos frequência, pois agora tentamos por setor
                if created_count % 200 == 0:
                    fake.unique.clear()

            except IntegrityError as e:
                print(f"  Aviso: Não foi possível criar funcionário para {sector} (possível duplicata): {e}")
                if 'email' in str(e).lower():
                    fake.unique.clear() # Limpa se o email for o problema
                pass # Continua para a próxima tentativa
            except Exception as e:
                 print(f"  Erro inesperado ao criar funcionário para {sector}: {e}")
                 pass
        
        if sector_created_count < count:
             print(f"  Aviso: Foram criados apenas {sector_created_count} de {count} funcionários para {sector} após {max_attempts} tentativas.")

    print(f"\nPopulação concluída. {created_count} funcionários criados no total (de {total_attempted} tentativas).")

if __name__ == '__main__':
    # Remove a lógica de argumentos, pois as contagens são fixas
    # parser = argparse.ArgumentParser(description='Popula o banco de dados com funcionários fictícios.')
    # parser.add_argument('count', type=int, default=10, nargs='?',
    #                     help='Número de funcionários a serem criados (padrão: 10)')
    # args = parser.parse_args()
    # populate(args.count)
    populate() 