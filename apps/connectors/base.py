"""
Clase base abstracta para todos los conectores de exchanges y brokers.

Cualquier conector nuevo (Binance, Kraken, OANDA, Interactive Brokers, etc.)
debe heredar de BaseConnector e implementar todos los métodos abstractos.

Uso:
    class BinanceConnector(BaseConnector):
        def connect(self) -> bool:
            ...
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================
# Dataclasses para tipos de retorno
# ============================================

@dataclass
class Ticker:
    """Precio actual de un símbolo."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal
    timestamp: datetime

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2


@dataclass
class Balance:
    """Balance de una moneda/divisa en la cuenta."""
    currency: str
    total: Decimal
    available: Decimal
    reserved: Decimal


@dataclass
class Order:
    """Orden de trading."""
    id: str
    symbol: str
    side: str  # 'buy' o 'sell'
    order_type: str  # 'market', 'limit', 'stop', etc.
    amount: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    filled: Decimal = Decimal('0')
    remaining: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    status: str = 'pending'
    timestamp: Optional[datetime] = None
    raw: dict = field(default_factory=dict)  # Respuesta cruda del exchange


@dataclass
class Position:
    """Posición abierta."""
    symbol: str
    side: str
    amount: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    timestamp: datetime


# ============================================
# Clase base abstracta
# ============================================

class BaseConnector(ABC):
    """
    Interfaz base para todos los conectores de exchanges y brokers.

    Cada conector debe implementar estos métodos para garantizar
    compatibilidad con el resto del sistema (estrategias, backtesting,
    paper trading, live trading).
    """

    def __init__(self, name: str, market_type: str, config: dict = None):
        """
        Args:
            name: Nombre identificador del conector (ej: 'binance', 'oanda')
            market_type: Tipo de mercado ('crypto', 'forex', 'stocks', etc.)
            config: Diccionario con API keys y configuración específica
        """
        self.name = name
        self.market_type = market_type
        self.config = config or {}
        self._connected = False
        self.logger = logging.getLogger(f'{__name__}.{name}')

    @property
    def is_connected(self) -> bool:
        """Verificar si el conector está conectado."""
        return self._connected

    # ------------------------------------------
    # Conexión
    # ------------------------------------------

    @abstractmethod
    def connect(self) -> bool:
        """
        Establecer conexión con el exchange/broker.

        Returns:
            True si la conexión fue exitosa.

        Raises:
            ConnectionError: Si no se puede conectar.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Cerrar la conexión limpiamente."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Verificar que la conexión y las credenciales son válidas.

        Returns:
            True si las credenciales son correctas y la API responde.
        """
        pass

    # ------------------------------------------
    # Datos de mercado
    # ------------------------------------------

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """
        Obtener el precio actual de un símbolo.

        Args:
            symbol: Par de trading (ej: 'BTC/USDT', 'EUR/USD')

        Returns:
            Objeto Ticker con precios actuales.
        """
        pass

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Obtener datos históricos OHLCV.

        Args:
            symbol: Par de trading
            timeframe: Intervalo ('5m', '15m', '1h', '4h', '1d')
            start: Fecha de inicio
            end: Fecha de fin (por defecto: ahora)
            limit: Número máximo de velas

        Returns:
            DataFrame con columnas: [timestamp, open, high, low, close, volume]
        """
        pass

    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """
        Obtener lista de símbolos disponibles para operar.

        Returns:
            Lista de símbolos (ej: ['BTC/USDT', 'ETH/USDT', ...])
        """
        pass

    # ------------------------------------------
    # Cuenta
    # ------------------------------------------

    @abstractmethod
    def get_balance(self) -> dict[str, Balance]:
        """
        Obtener el balance de la cuenta.

        Returns:
            Diccionario {moneda: Balance}
        """
        pass

    # ------------------------------------------
    # Órdenes
    # ------------------------------------------

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: Decimal,
        price: Decimal = None,
        stop_price: Decimal = None,
        params: dict = None,
    ) -> Order:
        """
        Colocar una orden.

        Args:
            symbol: Par de trading
            side: 'buy' o 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            amount: Cantidad a operar
            price: Precio límite (obligatorio para limit orders)
            stop_price: Precio de stop (obligatorio para stop orders)
            params: Parámetros adicionales específicos del exchange

        Returns:
            Objeto Order con los detalles de la orden creada.

        Raises:
            OrderError: Si la orden no se puede crear.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str = None) -> bool:
        """
        Cancelar una orden abierta.

        Args:
            order_id: ID de la orden a cancelar
            symbol: Par de trading (requerido por algunos exchanges)

        Returns:
            True si la orden fue cancelada exitosamente.
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str, symbol: str = None) -> Order:
        """
        Obtener el estado actual de una orden.

        Args:
            order_id: ID de la orden
            symbol: Par de trading

        Returns:
            Objeto Order actualizado.
        """
        pass

    @abstractmethod
    def get_open_orders(self, symbol: str = None) -> list[Order]:
        """
        Obtener todas las órdenes abiertas.

        Args:
            symbol: Filtrar por símbolo (None = todas)

        Returns:
            Lista de órdenes abiertas.
        """
        pass

    # ------------------------------------------
    # Posiciones
    # ------------------------------------------

    @abstractmethod
    def get_positions(self, symbol: str = None) -> list[Position]:
        """
        Obtener posiciones abiertas.

        Args:
            symbol: Filtrar por símbolo (None = todas)

        Returns:
            Lista de posiciones abiertas.
        """
        pass

    # ------------------------------------------
    # Métodos de utilidad (no abstractos)
    # ------------------------------------------

    def _validate_symbol(self, symbol: str) -> bool:
        """Validar que un símbolo existe en el exchange."""
        try:
            symbols = self.get_available_symbols()
            return symbol in symbols
        except Exception:
            return False

    def _log_order(self, order: Order, action: str = 'PLACED') -> None:
        """Registrar una orden en el log de trading."""
        self.logger.info(
            f'[{action}] {order.side.upper()} {order.amount} {order.symbol} '
            f'@ {order.price or "MARKET"} | ID: {order.id} | Status: {order.status}'
        )

    def __repr__(self) -> str:
        status = 'connected' if self._connected else 'disconnected'
        return f'<{self.__class__.__name__}(name={self.name}, market={self.market_type}, {status})>'
