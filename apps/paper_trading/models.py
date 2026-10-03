"""
Modelos para el módulo de Paper Trading (trading simulado).
"""
from django.db import models
from django.contrib.auth.models import User

from apps.core.models import (
    ActivatableModel, TimeStampedModel,
    MarketType, OrderSide, OrderType, OrderStatus, TradingMode,
)


class PaperAccount(ActivatableModel):
    """
    Cuenta virtual para paper trading.
    Simula una cuenta real con capital ficticio.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='paper_accounts',
        verbose_name='Usuario',
    )
    bot = models.OneToOneField(
        'live_trading.TradingBot',
        on_delete=models.CASCADE,
        related_name='paper_account',
        verbose_name='Bot Asociado',
        null=True,
        blank=True
    )
    name = models.CharField('Nombre', max_length=100)
    initial_balance = models.DecimalField(
        'Balance inicial',
        max_digits=15,
        decimal_places=2,
    )
    current_balance = models.DecimalField(
        'Balance actual',
        max_digits=15,
        decimal_places=2,
    )
    currency = models.CharField(
        'Moneda base',
        max_length=10,
        default='USDT',
    )

    class Meta:
        verbose_name = 'Cuenta Paper'
        verbose_name_plural = 'Cuentas Paper'

    def __str__(self):
        return f'{self.name} ({self.current_balance} {self.currency})'

    @property
    def total_pnl(self):
        return self.current_balance - self.initial_balance

    @property
    def total_return_pct(self):
        if self.initial_balance == 0:
            return 0
        return ((self.current_balance - self.initial_balance) / self.initial_balance) * 100


class PaperTrade(TimeStampedModel):
    """
    Registro de operación simulada.
    """
    account = models.ForeignKey(
        PaperAccount,
        on_delete=models.CASCADE,
        related_name='trades',
        verbose_name='Cuenta',
    )
    strategy = models.ForeignKey(
        'strategies.Strategy',
        on_delete=models.SET_NULL,
        null=True,
        related_name='paper_trades',
        verbose_name='Estrategia',
    )
    symbol = models.CharField('Símbolo', max_length=20)
    side = models.CharField(
        'Lado',
        max_length=10,
        choices=OrderSide.choices,
    )
    order_type = models.CharField(
        'Tipo de orden',
        max_length=20,
        choices=OrderType.choices,
    )
    amount = models.DecimalField('Cantidad', max_digits=20, decimal_places=8)
    entry_price = models.DecimalField('Precio de entrada', max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(
        'Precio de salida',
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
    )
    stop_loss = models.DecimalField(
        'Stop Loss',
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
    )
    take_profit = models.DecimalField(
        'Take Profit',
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.OPEN,
    )
    pnl = models.DecimalField(
        'P&L',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    closed_at = models.DateTimeField('Cerrada en', null=True, blank=True)

    class Meta:
        verbose_name = 'Operación Paper'
        verbose_name_plural = 'Operaciones Paper'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.side} {self.amount} {self.symbol} @ {self.entry_price}'
