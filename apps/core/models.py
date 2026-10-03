"""
Modelos base del proyecto BotTrading.
Clases abstractas que proporcionan campos comunes a todos los modelos.
"""
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Modelo abstracto que añade campos de auditoría de tiempo.
    Todos los modelos del proyecto deben heredar de este.
    """
    created_at = models.DateTimeField(
        'Fecha de creación',
        default=timezone.now,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        'Última actualización',
        auto_now=True,
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']


class ActivatableModel(TimeStampedModel):
    """
    Modelo abstracto para entidades que pueden activarse/desactivarse.
    Útil para bots, estrategias y conectores.
    """
    is_active = models.BooleanField(
        'Activo',
        default=True,
        db_index=True,
    )

    class Meta:
        abstract = True

    def activate(self):
        """Activar la entidad."""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])

    def deactivate(self):
        """Desactivar la entidad."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


# ============================================
# Enumeraciones del sistema
# ============================================

class MarketType(models.TextChoices):
    """Tipos de mercado soportados."""
    CRYPTO = 'crypto', 'Criptomonedas'
    FOREX = 'forex', 'Divisas (Forex)'
    STOCKS = 'stocks', 'Acciones'
    ETF = 'etf', 'ETFs'
    INDEX = 'index', 'Índices'
    FUTURES = 'futures', 'Futuros'


class OrderSide(models.TextChoices):
    """Dirección de la orden."""
    BUY = 'buy', 'Compra'
    SELL = 'sell', 'Venta'


class OrderType(models.TextChoices):
    """Tipos de orden."""
    MARKET = 'market', 'Mercado'
    LIMIT = 'limit', 'Límite'
    STOP = 'stop', 'Stop'
    STOP_LIMIT = 'stop_limit', 'Stop Limit'
    TRAILING_STOP = 'trailing_stop', 'Trailing Stop'


class OrderStatus(models.TextChoices):
    """Estado de una orden."""
    PENDING = 'pending', 'Pendiente'
    OPEN = 'open', 'Abierta'
    PARTIALLY_FILLED = 'partially_filled', 'Parcialmente ejecutada'
    FILLED = 'filled', 'Ejecutada'
    CANCELLED = 'cancelled', 'Cancelada'
    REJECTED = 'rejected', 'Rechazada'
    EXPIRED = 'expired', 'Expirada'


class SignalType(models.TextChoices):
    """Señales de trading generadas por las estrategias."""
    BUY = 'buy', 'Comprar'
    SELL = 'sell', 'Vender'
    HOLD = 'hold', 'Mantener'
    CLOSE = 'close', 'Cerrar posición'


class TimeFrame(models.TextChoices):
    """Timeframes soportados para velas OHLCV."""
    M5 = '5m', '5 Minutos'
    M15 = '15m', '15 Minutos'
    M30 = '30m', '30 Minutos'
    H1 = '1h', '1 Hora'
    H4 = '4h', '4 Horas'
    D1 = '1d', '1 Día'
    W1 = '1w', '1 Semana'


class TradingMode(models.TextChoices):
    """Modos de operación del bot."""
    BACKTEST = 'backtest', 'Backtesting'
    PAPER = 'paper', 'Paper Trading (Simulado)'
    LIVE = 'live', 'Trading en Vivo'


# ============================================
# Datos de Mercado
# ============================================

class Candle(models.Model):
    """
    Datos OHLCV (Velas japonesas) históricos.
    Idealmente manejado como una hypertable en TimescaleDB.
    """
    symbol = models.CharField('Símbolo', max_length=20, db_index=True)
    timeframe = models.CharField('Timeframe', max_length=10, choices=TimeFrame.choices, db_index=True)
    timestamp = models.DateTimeField('Fecha y hora', db_index=True)
    open = models.DecimalField('Open', max_digits=20, decimal_places=8)
    high = models.DecimalField('High', max_digits=20, decimal_places=8)
    low = models.DecimalField('Low', max_digits=20, decimal_places=8)
    close = models.DecimalField('Close', max_digits=20, decimal_places=8)
    volume = models.DecimalField('Volumen', max_digits=20, decimal_places=8)

    class Meta:
        verbose_name = 'Vela (Candle)'
        verbose_name_plural = 'Velas (Candles)'
        unique_together = ['symbol', 'timeframe', 'timestamp']
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['symbol', 'timeframe', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.symbol} {self.timeframe} @ {self.timestamp}: {self.close}'

# ============================================
# Configuración del Sistema
# ============================================

class SystemSetting(models.Model):
    """
    Configuraciones globales del sistema y claves API.
    Guarda pares clave-valor (ej: OPENAI_API_KEY, GEMINI_API_KEY).
    """
    key = models.CharField('Clave', max_length=100, unique=True, db_index=True)
    value = models.CharField('Valor', max_length=500, blank=True)
    description = models.CharField('Descripción', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Configuración del Sistema'
        verbose_name_plural = 'Configuraciones del Sistema'

    def __str__(self):
        return self.key
