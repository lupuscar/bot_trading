"""
Modelos de base de datos para las estrategias.
"""
from django.db import models
from django.contrib.auth.models import User

from apps.core.models import ActivatableModel, TimeFrame


class Strategy(ActivatableModel):
    """
    Registro de una estrategia de trading en la base de datos.
    Almacena la clase Python asociada y sus parámetros configurables.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='strategies',
        verbose_name='Usuario',
    )
    name = models.CharField(
        'Nombre',
        max_length=100,
    )
    description = models.TextField(
        'Descripción',
        blank=True,
        default='',
    )
    strategy_class = models.CharField(
        'Clase Python',
        max_length=255,
        help_text='Ruta completa de la clase (ej: apps.strategies.ma_crossover.MACrossoverStrategy)',
    )
    version = models.CharField(
        'Versión',
        max_length=20,
        default='1.0',
    )
    timeframe = models.CharField(
        'Timeframe',
        max_length=10,
        choices=TimeFrame.choices,
        default=TimeFrame.H1,
    )
    parameters = models.JSONField(
        'Parámetros',
        default=dict,
        blank=True,
        help_text='Parámetros de configuración de la estrategia en JSON',
    )

    class Meta:
        verbose_name = 'Estrategia'
        verbose_name_plural = 'Estrategias'
        unique_together = ['user', 'name']
        ordering = ['name']

    def __str__(self):
        return f'{self.name} v{self.version} ({self.get_timeframe_display()})'
