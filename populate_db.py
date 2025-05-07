#!/usr/bin/env python
"""
Script para popular o banco de dados com funcionários dos setores SIAPE Leo e SIAPE Dion.
"""

import os
import django
import random
from datetime import datetime

# Configurar as configurações do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pas.settings')
django.setup()

# Importar o modelo Employee após a configuração do Django
from pam.models import Employee

# Nomes fictícios para os funcionários
nomes_masculinos = [
    "João", "Pedro", "Carlos", "Paulo", "José", "Roberto", "Antônio", "Francisco", 
    "Fernando", "Ricardo", "Rafael", "Marcelo", "Luiz", "Alexandre", "André", "Rodrigo",
    "Sérgio", "Eduardo", "Guilherme", "Felipe"
]

nomes_femininos = [
    "Maria", "Ana", "Juliana", "Fernanda", "Patrícia", "Sandra", "Camila", "Amanda", 
    "Beatriz", "Luciana", "Carla", "Márcia", "Mônica", "Tatiana", "Cristina", "Débora",
    "Fabiana", "Gabriela", "Helena", "Isabela"
]

sobrenomes = [
    "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa", "Rodrigues", "Almeida", 
    "Nascimento", "Lima", "Araújo", "Ribeiro", "Martins", "Ferreira", "Carvalho", "Gomes",
    "Barbosa", "Dias", "Mendes", "Cardoso", "Correia", "Soares", "Vieira", "Moreira"
]

def gerar_nome_completo():
    """Gera um nome completo aleatório."""
    if random.choice([True, False]):
        # Nome masculino
        primeiro_nome = random.choice(nomes_masculinos)
    else:
        # Nome feminino
        primeiro_nome = random.choice(nomes_femininos)
    
    # Adiciona um ou dois sobrenomes
    if random.choice([True, False]):
        # Dois sobrenomes
        sobrenome1 = random.choice(sobrenomes)
        sobrenome2 = random.choice(sobrenomes)
        while sobrenome1 == sobrenome2:  # Evita sobrenomes repetidos
            sobrenome2 = random.choice(sobrenomes)
        return f"{primeiro_nome} {sobrenome1} {sobrenome2}"
    else:
        # Um sobrenome
        return f"{primeiro_nome} {random.choice(sobrenomes)}"

def criar_funcionarios():
    """Cria 12 funcionários para cada setor: SIAPE_LEO e SIAPE_DION."""
    # Verificar funcionários existentes
    funcionarios_leo = Employee.objects.filter(sector='SIAPE_LEO').count()
    funcionarios_dion = Employee.objects.filter(sector='SIAPE_DION').count()
    
    # Criar funcionários para SIAPE_LEO
    print(f"Criando funcionários para o setor SIAPE Leo (existentes: {funcionarios_leo})...")
    for i in range(12 - funcionarios_leo):
        if funcionarios_leo + i >= 12:
            break
        
        nome = gerar_nome_completo()
        funcionario = Employee.objects.create(
            name=nome,
            sector='SIAPE_LEO'
        )
        print(f"Criado: {funcionario}")
    
    # Criar funcionários para SIAPE_DION
    print(f"Criando funcionários para o setor SIAPE Dion (existentes: {funcionarios_dion})...")
    for i in range(12 - funcionarios_dion):
        if funcionarios_dion + i >= 12:
            break
        
        nome = gerar_nome_completo()
        funcionario = Employee.objects.create(
            name=nome,
            sector='SIAPE_DION'
        )
        print(f"Criado: {funcionario}")

if __name__ == '__main__':
    print("Iniciando população da base de dados...")
    inicio = datetime.now()
    
    criar_funcionarios()
    
    fim = datetime.now()
    tempo_execucao = fim - inicio
    print(f"Processo concluído em {tempo_execucao.total_seconds():.2f} segundos.") 