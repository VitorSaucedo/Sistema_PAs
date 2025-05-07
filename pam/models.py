from django.db import models
from django.core.validators import MinLengthValidator
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from threading import local

class Employee(models.Model):
    SECTOR_CHOICES = [
        ('INSS', 'INSS'),
        ('SIAPE_LEO', 'SIAPE Leo'),
        ('SIAPE_DION', 'SIAPE Dion'),
        ('ESTAGIO', 'Estágio'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Nome")
    sector = models.CharField(
        max_length=20,
        choices=SECTOR_CHOICES,
        verbose_name="Setor",
        default='INSS'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"
        ordering = ['name']

    def __str__(self):
        # Display only the name, sector is handled elsewhere
        return self.name


class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome da Sala")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = ['name']

    def __str__(self):
        return self.name

class Island(models.Model):
    CATEGORY_CHOICES = [
        ('ESTAGIO', 'Estágio'),
        ('INSS', 'INSS'),
        ('SIAPE_DION', 'SIAPE Dion'),
        ('SIAPE_LEO', 'SIAPE Leo'),
    ]
    
    room = models.ForeignKey(Room, related_name='islands', on_delete=models.CASCADE, verbose_name='Sala')
    island_number = models.PositiveIntegerField(verbose_name='Número da Ilha')
    name = models.CharField(max_length=100, verbose_name='Nome da Ilha', default='')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='INSS', verbose_name='Categoria da Ilha')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ilha"
        verbose_name_plural = "Ilhas"
        unique_together = ('room', 'island_number')
        ordering = ['room', 'island_number']

    def __str__(self):
        return f"Ilha {self.name}"

    def save(self, *args, **kwargs):
        # Se não foi fornecido um nome, usa o número da ilha
        if not self.name:
            self.name = str(self.island_number)
        super().save(*args, **kwargs)


class Workstation(models.Model):
    STATUS_CHOICES = [
        ('OCCUPIED', 'Ocupada'),
        ('UNOCCUPIED', 'Vaga'),
        ('MAINTENANCE', 'Manutenção'),
    ]
    
    CATEGORY_CHOICES = [
        ('ESTAGIO', 'Estágio'),
        ('INSS', 'INSS'),
        ('SIAPE_DION', 'SIAPE Dion'),
        ('SIAPE_LEO', 'SIAPE Leo'),
    ]
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="Categoria",
        default='ESTAGIO'
    )
    sequence = models.PositiveIntegerField(
        verbose_name="Sequência",
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name="Status",
        default='UNOCCUPIED'
    )
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Funcionário"
    )
    monitor = models.BooleanField(default=True, verbose_name="Monitor")
    keyboard = models.BooleanField(default=True, verbose_name="Teclado")
    mouse = models.BooleanField(default=True, verbose_name="Mouse")
    mousepad = models.BooleanField(default=True, verbose_name="Mousepad")
    headset = models.BooleanField(default=True, verbose_name="Fone de Ouvido")
    island = models.ForeignKey(
        Island,
        on_delete=models.CASCADE,
        related_name='workstations',
        verbose_name="Ilha",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estação de Trabalho"
        verbose_name_plural = "Estações de Trabalho"
        unique_together = [['category', 'sequence']]
        ordering = ['island__room__name', 'island__island_number', 'sequence']

    def save(self, *args, **kwargs):
        # Só atualiza status automaticamente se não foi definido manualmente
        if not self.pk or 'status' not in kwargs.get('update_fields', []):
            if self.status != 'MAINTENANCE':
                if not self.employee:
                    self.status = 'UNOCCUPIED'
                elif not all([self.monitor, self.keyboard, self.mouse]):
                    self.status = 'MAINTENANCE'
                else:
                    self.status = 'OCCUPIED'
        
        # Atualiza o setor do funcionário baseado na categoria da workstation
        if self.employee: # Removed hasattr check
            # Mapeia categoria da workstation para setor do funcionário
            sector_map = {
                'INSS': 'INSS',
                'SIAPE_LEO': 'SIAPE_LEO',
                'SIAPE_DION': 'SIAPE_DION',
                'ESTAGIO': 'ESTAGIO'
            }
            new_sector = sector_map.get(self.category, 'INSS') # Default to INSS if category not found
            if self.employee.sector != new_sector:
                self.employee.sector = new_sector
                self.employee.save(update_fields=['sector'])
                
        if not self.sequence and self.category:
            last = Workstation.objects.filter(
                category=self.category
            ).order_by('-sequence').first()
            self.sequence = last.sequence + 1 if last else 1
            
        # If status is set to UNOCCUPIED, ensure no employee is assigned
        if self.status == 'UNOCCUPIED' and self.employee is not None:
            self.employee = None
            
        super().save(*args, **kwargs)

    def __str__(self):
        location = f"Sala {self.island.room.name}, Ilha {self.island.name}" if self.island else f"Categoria {self.category}"
        return f"PA {location} Seq {self.sequence} - {self.employee.name if self.employee else 'Sem funcionário'}"

@receiver(pre_delete, sender=Room)
def room_delete_handler(sender, instance, **kwargs):
    # Custom logic before a room is deleted, if necessary
    pass

# Signals para registrar histórico de posicionamento de funcionários
@receiver(models.signals.pre_save, sender=Workstation)
def track_employee_position_change(sender, instance, **kwargs):
    """Detecta mudanças de funcionário em uma estação de trabalho."""
    if not instance.pk:  # Novo objeto sendo criado
        return
    
    try:
        # Obtém o estado anterior da estação de trabalho
        old_instance = Workstation.objects.get(pk=instance.pk)
        
        # Se o funcionário mudou (atribuição, desatribuição ou troca)
        if old_instance.employee != instance.employee:
            # Se havia um funcionário antes, encerra o registro antigo
            if old_instance.employee:
                # Busca o registro ativo mais recente e encerra-o
                try:
                    history = EmployeePositionHistory.objects.filter(
                        employee=old_instance.employee,
                        workstation=old_instance,
                        end_date__isnull=True
                    ).latest('start_date')
                    
                    history.end_date = timezone.now()
                    # Tenta obter o usuário do request atual
                    try:
                        _thread_locals = local()
                        history.changed_by = getattr(_thread_locals, 'user', None)
                    except:
                        pass
                    history.save()
                except EmployeePositionHistory.DoesNotExist:
                    pass  # Não encontrou histórico ativo
            
            # Se há um novo funcionário sendo atribuído, cria um novo registro
            if instance.employee:
                # Cria um novo registro para o novo funcionário
                EmployeePositionHistory.objects.create(
                    employee=instance.employee,
                    workstation=instance,
                    room=instance.island.room if instance.island else None,
                    island=instance.island,
                    # Tenta obter o usuário do request atual
                    changed_by=getattr(_thread_locals, 'user', None) if '_thread_locals' in locals() else None
                )
    except Workstation.DoesNotExist:
        pass  # Objeto não existe no banco ainda

# Funções para registrar logs de alterações
def log_change(user, entity_type, entity_id, entity_name, action_type, description):
    """Função utilitária para criar registros de log."""
    ChangeLog.objects.create(
        user=user,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        action_type=action_type,
        description=description
    )

# Middleware para capturar o usuário da requisição atual
_thread_locals = local()

class CurrentUserMiddleware(MiddlewareMixin):
    """Middleware para armazenar o usuário atual na thread local."""
    def process_request(self, request):
        _thread_locals.user = getattr(request, 'user', None)
    
    def process_response(self, request, response):
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user
        return response

class ChangeLog(models.Model):
    """Modelo para registrar alterações em objetos do sistema."""
    ENTITY_TYPES = [
        ('WORKSTATION', 'Estação de Trabalho'),
        ('EMPLOYEE', 'Funcionário'),
        ('ISLAND', 'Ilha'),
        ('ROOM', 'Sala'),
    ]
    
    ACTION_TYPES = [
        ('CREATE', 'Criação'),
        ('UPDATE', 'Atualização'),
        ('DELETE', 'Exclusão'),
        ('ASSIGNMENT', 'Atribuição de Funcionário'),
        ('UNASSIGNMENT', 'Remoção de Funcionário'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuário")
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES, verbose_name="Tipo de Entidade")
    entity_id = models.PositiveIntegerField(verbose_name="ID da Entidade")
    entity_name = models.CharField(max_length=255, verbose_name="Nome da Entidade")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="Tipo de Ação")
    description = models.TextField(verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data da Alteração")
    
    class Meta:
        verbose_name = "Log de Alteração"
        verbose_name_plural = "Logs de Alterações"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_action_type_display()} de {self.get_entity_type_display()} {self.entity_name} por {self.user.username if self.user else 'Sistema'}"

class EmployeePositionHistory(models.Model):
    """Modelo para rastrear histórico de posicionamento de funcionários."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='position_history', verbose_name="Funcionário")
    workstation = models.ForeignKey(Workstation, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_history', verbose_name="Estação de Trabalho")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sala")
    island = models.ForeignKey(Island, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ilha")
    start_date = models.DateTimeField(auto_now_add=True, verbose_name="Data de Início")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Data de Término")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Alterado por")
    
    class Meta:
        verbose_name = "Histórico de Posição"
        verbose_name_plural = "Históricos de Posições"
        ordering = ['-start_date']
    
    def __str__(self):
        location = f"PA {self.workstation.category} {self.workstation.sequence}" if self.workstation else "Sem estação"
        if self.island and self.room:
            location += f" (Sala {self.room.name}, Ilha {self.island.name})"
        return f"{self.employee.name} em {location} desde {self.start_date.strftime('%d/%m/%Y')}"
