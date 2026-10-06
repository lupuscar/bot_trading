"""
Clase base abstracta para todas las estrategias de trading.

Cada estrategia debe heredar de BaseStrategy e implementar el método
analyze() que recibe datos OHLCV y devuelve una señal de trading.

Uso:
    class MACrossoverStrategy(BaseStrategy):
        def analyze(self, data: pd.DataFrame) -> Signal:
            ...
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """
    Señal generada por una estrategia.
    Contiene toda la información necesaria para ejecutar la operación.
    """
    signal_type: str  # 'buy', 'sell', 'hold', 'close'
    symbol: str
    strength: float = 0.0  # 0.0 a 1.0 (confianza de la señal)
    price: Optional[Decimal] = None  # Precio sugerido de entrada
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    amount: Optional[Decimal] = None  # Cantidad sugerida
    reason: str = ''  # Motivo de la señal (para logs)
    metadata: dict = field(default_factory=dict)  # Datos extra (indicadores, etc.)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_actionable(self) -> bool:
        """Si la señal requiere acción (no es HOLD)."""
        return self.signal_type in ('buy', 'sell', 'close', 'short', 'cover')


class BaseStrategy(ABC):
    """
    Interfaz base para todas las estrategias de trading.

    Una estrategia analiza datos de mercado y genera señales de
    compra/venta que luego son procesadas por el motor de ejecución.
    """

    def __init__(self, name: str, version: str = '1.0', params: dict = None):
        """
        Args:
            name: Nombre de la estrategia (ej: 'MA Crossover')
            version: Versión de la estrategia
            params: Parámetros configurables de la estrategia
        """
        self.name = name
        self.version = version
        self.params = params or self.get_default_params()
        self.logger = logging.getLogger(f'{__name__}.{name}')

    # ------------------------------------------
    # Métodos abstractos (OBLIGATORIOS)
    # ------------------------------------------

    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> Signal:
        """
        Analizar datos de mercado y generar una señal de trading.

        Este es el método principal de la estrategia. Recibe un DataFrame
        con datos OHLCV y debe devolver una señal indicando qué hacer.

        Args:
            data: DataFrame con columnas [timestamp, open, high, low, close, volume]
                  Ordenado cronológicamente (más antiguo primero).

        Returns:
            Objeto Signal con la decisión de la estrategia.
        """
        pass

    @abstractmethod
    def get_default_params(self) -> dict:
        """
        Devolver los parámetros por defecto de la estrategia.

        Returns:
            Dict con los parámetros y sus valores por defecto.
            Ejemplo: {'fast_period': 10, 'slow_period': 20, 'rsi_period': 14}
        """
        pass

    # ------------------------------------------
    # Métodos opcionales (SOBREESCRIBIBLES)
    # ------------------------------------------

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validar que los datos de entrada son suficientes y correctos.

        Args:
            data: DataFrame a validar.

        Returns:
            True si los datos son válidos.
        """
        required_columns = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        if not required_columns.issubset(data.columns):
            missing = required_columns - set(data.columns)
            self.logger.error(f'Columnas faltantes en datos: {missing}')
            return False

        min_rows = self.get_min_data_points()
        if len(data) < min_rows:
            self.logger.warning(
                f'Datos insuficientes: {len(data)} filas, mínimo {min_rows}'
            )
            return False

        return True

    def get_min_data_points(self) -> int:
        """
        Número mínimo de velas necesarias para calcular la estrategia.

        Returns:
            Número mínimo de filas de datos requeridas.
        """
        return 50  # Por defecto

    def get_required_timeframe(self) -> str:
        """
        Timeframe requerido por la estrategia.

        Returns:
            Timeframe en formato string (ej: '1h', '4h', '1d')
        """
        return '1h'  # Por defecto

    @classmethod
    def get_parameters_schema(cls) -> dict[str, dict[str, Any]]:
        """
        Esquema de los parámetros configurables para la UI.

        Returns:
            Dict describiendo cada parámetro, su tipo, rango y valor por defecto.
            Ejemplo:
            {
                'fast_period': {
                    'type': 'int', 'min': 2, 'max': 100,
                    'default': 10, 'description': 'Periodo de la MA rápida'
                },
            }
        """
        return {}

    def on_init(self) -> None:
        """Hook ejecutado al inicializar la estrategia."""
        pass

    def on_stop(self) -> None:
        """Hook ejecutado al detener la estrategia."""
        pass

    def get_chart_indicators(self, data: pd.DataFrame) -> dict:
        """
        Calcula y devuelve los indicadores técnicos de la estrategia formateados
        para graficarlos en Lightweight Charts.
        
        Returns:
            Un diccionario donde las claves son los IDs de las líneas y el valor
            es un dict con 'color', 'name', y 'data' (lista de dicts con time y value).
        """
        return {}

    # ------------------------------------------
    # Métodos de utilidad (NO sobreescribir)
    # ------------------------------------------

    def safe_analyze(self, data: pd.DataFrame) -> Signal:
        """
        Wrapper seguro para analyze(). Valida datos y captura excepciones.
        Usar este método en vez de analyze() directamente.
        """
        try:
            if not self.validate_data(data):
                return Signal(
                    signal_type='hold',
                    symbol='',
                    reason='Datos inválidos o insuficientes',
                )
            return self.analyze(data)
        except Exception as e:
            self.logger.exception(f'Error en estrategia {self.name}: {e}')
            return Signal(
                signal_type='hold',
                symbol='',
                reason=f'Error: {str(e)}',
            )

    def update_params(self, new_params: dict) -> None:
        """Actualizar parámetros de la estrategia en caliente."""
        old_params = self.params.copy()
        self.params.update(new_params)
        self.logger.info(
            f'Parámetros actualizados: {old_params} -> {self.params}'
        )

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}(name={self.name}, v{self.version})>'
