from django.db import models
from django.core.validators import MinLengthValidator

class Employee(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.id})"


class Workstation(models.Model):
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
    
    employee = models.OneToOneField(
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
        if not self.sequence:  # Só gera nova sequência se não tiver definida
            last = Workstation.objects.filter(
                category=self.category
            ).order_by('-sequence').first()
            self.sequence = last.sequence + 1 if last else 1
        super().save(*args, **kwargs)

    def clean(self):
        if self.sequence and Workstation.objects.filter(
            category=self.category,
            sequence=self.sequence
        ).exclude(pk=self.pk).exists():
            raise ValidationError('Já existe uma estação com esta sequência nesta categoria')

    def __str__(self):
        return f"PA {self.category}-{self.sequence} - {self.employee.name if self.employee else 'Sem funcionário'}"
