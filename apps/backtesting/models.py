"""
Modelos para almacenar resultados de backtesting.
"""
from django.db import models
from django.contrib.auth.models import User

from apps.core.models import TimeStampedModel, TimeFrame


class BacktestRun(TimeStampedModel):
    """
    Registro de una ejecución de backtesting.
    Almacena parámetros y resultados de cada test.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='backtest_runs',
        verbose_name='Usuario',
    )
    strategy = models.ForeignKey(
        'strategies.Strategy',
        on_delete=models.CASCADE,
        related_name='backtest_runs',
        verbose_name='Estrategia',
    )
    exchange_connection = models.ForeignKey(
        'connectors.ExchangeConnection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backtest_runs',
        verbose_name='Conexión',
    )
    symbol = models.CharField('Símbolo', max_length=20)
    timeframe = models.CharField(
        'Timeframe',
        max_length=10,
        choices=TimeFrame.choices,
    )
    start_date = models.DateTimeField('Fecha inicio')
    end_date = models.DateTimeField('Fecha fin')
    initial_capital = models.DecimalField(
        'Capital inicial',
        max_digits=15,
        decimal_places=2,
    )
    strategy_params = models.JSONField(
        'Parámetros de estrategia',
        default=dict,
    )

    # Resultados
    final_capital = models.DecimalField(
        'Capital final',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    total_return_pct = models.DecimalField(
        'Retorno total (%)',
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    max_drawdown_pct = models.DecimalField(
        'Drawdown máximo (%)',
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    sharpe_ratio = models.DecimalField(
        'Ratio de Sharpe',
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    total_trades = models.IntegerField('Total operaciones', default=0)
    winning_trades = models.IntegerField('Operaciones ganadoras', default=0)
    losing_trades = models.IntegerField('Operaciones perdedoras', default=0)
    profit_factor = models.DecimalField(
        'Profit Factor',
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('running', 'Ejecutando'),
            ('completed', 'Completado'),
            ('failed', 'Fallido'),
        ],
        default='pending',
    )
    error_message = models.TextField(
        'Mensaje de error',
        blank=True,
        default='',
    )
    results_data = models.JSONField(
        'Datos detallados',
        default=dict,
        blank=True,
        help_text='Resultados detallados: equity curve, trades, etc.',
    )

    class Meta:
        verbose_name = 'Ejecución de Backtest'
        verbose_name_plural = 'Ejecuciones de Backtest'
        ordering = ['-created_at']

    def __str__(self):
        return f'Backtest {self.strategy.name} - {self.symbol} ({self.status})'

    @property
    def win_rate(self) -> float:
        """Porcentaje de operaciones ganadoras."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
