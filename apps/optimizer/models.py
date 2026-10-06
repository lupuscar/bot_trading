from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimeStampedModel

class OptimizationRun(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='optimization_runs')
    symbol = models.CharField(max_length=20, default='BTC/USDT')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    trade_risk_pct = models.FloatField(default=5.0)
    selected_strategies = models.JSONField(default=list, blank=True)
    
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('running', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Optimizador {self.symbol} ({self.created_at.strftime('%Y-%m-%d')})"

class OptimizationResult(TimeStampedModel):
    run = models.ForeignKey(OptimizationRun, on_delete=models.CASCADE, related_name='results')
    strategy_name = models.CharField(max_length=255)
    strategy_class = models.CharField(max_length=255)
    timeframe = models.CharField(max_length=10)
    parameters = models.JSONField(default=dict, blank=True)
    
    total_return_pct = models.FloatField(default=0.0)
    max_drawdown_pct = models.FloatField(default=0.0)
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-total_return_pct']

    def __str__(self):
        return f"{self.strategy_name} ({self.timeframe}) -> {self.total_return_pct:.2f}%"
