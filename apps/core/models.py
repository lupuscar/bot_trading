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
