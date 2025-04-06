from django.db import models
from django.core.validators import MinLengthValidator

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
        editable=False,
        null=True
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estação de Trabalho"
        verbose_name_plural = "Estações de Trabalho"
        unique_together = [['category', 'sequence']]
        ordering = ['category', 'sequence']

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
                
        if not self.sequence:
            last = Workstation.objects.filter(
                category=self.category
            ).order_by('-sequence').first()
            self.sequence = last.sequence + 1 if last else 1
            
        # If status is set to UNOCCUPIED, ensure no employee is assigned
        if self.status == 'UNOCCUPIED' and self.employee is not None:
            self.employee = None
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"PA {self.category}-{self.sequence} - {self.employee.name if self.employee else 'Sem funcionário'}"
