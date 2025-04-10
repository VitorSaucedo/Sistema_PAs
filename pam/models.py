from django.db import models
from django.core.validators import MinLengthValidator
from django.db.models.signals import pre_delete
from django.dispatch import receiver

class Employee(models.Model):
    SECTOR_CHOICES = [
        ('INSS', 'INSS'),
        ('SIAPE_LEO', 'SIAPE Leo'),
        ('SIAPE_DION', 'SIAPE Dion'),
        ('ESTAGIO', 'Estágio'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Nome")
    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF", validators=[MinLengthValidator(11)], help_text="Formato: 123.456.789-00 ou 12345678900")
    email = models.EmailField(max_length=254, unique=True, null=True, blank=True, verbose_name="Email")
    phone = models.CharField(max_length=15, verbose_name="Telefone", help_text="Formato: (XX) XXXXX-XXXX")
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
    room = models.ForeignKey(Room, related_name='islands', on_delete=models.CASCADE, verbose_name='Sala')
    island_number = models.PositiveIntegerField(verbose_name='Número da Ilha')
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name='Categoria da Ilha')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ilha"
        verbose_name_plural = "Ilhas"
        unique_together = ('room', 'island_number')
        ordering = ['room', 'island_number']

    def __str__(self):
        return f"Sala {self.room.name} - Ilha {self.island_number}"


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
        location = f"Sala {self.island.room.name}, Ilha {self.island.island_number}" if self.island else f"Categoria {self.category}"
        return f"PA {location} Seq {self.sequence} - {self.employee.name if self.employee else 'Sem funcionário'}"

# Signal to handle related objects upon Room deletion if needed more granularly than CASCADE
# (Optional, CASCADE should handle basic deletion)
# @receiver(pre_delete, sender=Room)
# def room_delete_handler(sender, instance, **kwargs):
#     # Custom logic before a room is deleted, if necessary
#     pass
