"""
Modelos para el módulo de trading en vivo.
"""
from django.db import models
from django.contrib.auth.models import User

from apps.core.models import (
    ActivatableModel, TimeStampedModel,
    TradingMode, OrderSide, OrderType, OrderStatus, TimeFrame,
)


class TradingBot(ActivatableModel):
    """
    Instancia de un bot de trading.
    Combina un conector + estrategia + configuración de ejecución.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bots',
        verbose_name='Usuario',
    )
    name = models.CharField('Nombre', max_length=100)
    description = models.TextField('Descripción', blank=True, default='')

    # Componentes
    exchange_connection = models.ForeignKey(
        'connectors.ExchangeConnection',
        on_delete=models.CASCADE,
        related_name='bots',
        verbose_name='Conexión al Exchange',
    )
    strategy = models.ForeignKey(
        'strategies.Strategy',
        on_delete=models.CASCADE,
        related_name='bots',
        verbose_name='Estrategia',
    )

    # Configuración de trading
    symbol = models.CharField('Símbolo', max_length=20)
    timeframe = models.CharField(
        'Timeframe',
        max_length=10,
        choices=TimeFrame.choices,
        default=TimeFrame.H1,
    )
    mode = models.CharField(
        'Modo',
        max_length=20,
        choices=TradingMode.choices,
        default=TradingMode.PAPER,
    )

    # Gestión de riesgo
    max_position_size = models.DecimalField(
        'Tamaño máximo de posición',
        max_digits=20,
        decimal_places=8,
        help_text='Cantidad máxima por operación',
    )
    risk_per_trade_pct = models.DecimalField(
        'Riesgo por operación (%)',
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text='Porcentaje del capital a arriesgar por operación',
    )
    max_open_positions = models.IntegerField(
        'Máximo posiciones abiertas',
        default=3,
    )
    daily_loss_limit_pct = models.DecimalField(
        'Límite pérdida diaria (%)',
        max_digits=5,
        decimal_places=2,
        default=5.00,
    )

    # Estado
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=[
            ('stopped', 'Detenido'),
            ('running', 'Ejecutando'),
            ('paused', 'Pausado'),
            ('error', 'Error'),
        ],
        default='stopped',
    )
    last_signal = models.JSONField(
        'Última señal',
        null=True,
        blank=True,
    )
    last_run_at = models.DateTimeField(
        'Última ejecución',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Bot de Trading'
        verbose_name_plural = 'Bots de Trading'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.symbol} - {self.get_mode_display()}) [{self.status}]'


class TradeRecord(TimeStampedModel):
    """
    Registro histórico de una operación real ejecutada por un bot.
    """
    bot = models.ForeignKey(
        TradingBot,
        on_delete=models.CASCADE,
        related_name='trades',
        verbose_name='Bot',
    )
    symbol = models.CharField('Símbolo', max_length=20)
    side = models.CharField('Lado', max_length=10, choices=OrderSide.choices)
    order_type = models.CharField('Tipo', max_length=20, choices=OrderType.choices)
    amount = models.DecimalField('Cantidad', max_digits=20, decimal_places=8)
    price = models.DecimalField('Precio', max_digits=20, decimal_places=8)
    cost = models.DecimalField('Coste total', max_digits=20, decimal_places=8)
    fee = models.DecimalField('Comisión', max_digits=20, decimal_places=8, default=0)
    status = models.CharField('Estado', max_length=20, choices=OrderStatus.choices)
    exchange_order_id = models.CharField(
        'ID orden exchange',
        max_length=255,
        blank=True,
        default='',
    )
    raw_response = models.JSONField(
        'Respuesta raw',
        default=dict,
        blank=True,
    )
    pnl = models.DecimalField(
        'P&L',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    signal_data = models.JSONField(
        'Datos de la señal',
        default=dict,
        blank=True,
        help_text='Señal que generó esta operación',
    )

    class Meta:
        verbose_name = 'Operación Real'
        verbose_name_plural = 'Operaciones Reales'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.side} {self.amount} {self.symbol} @ {self.price}'
