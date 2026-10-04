import random
import pandas as pd
from typing import Any
from decimal import Decimal

from apps.strategies.base import BaseStrategy, Signal

class RandomTesterStrategy(BaseStrategy):
    DISPLAY_NAME = 'Probador Aleatorio (Test)'
    """
    Estrategia que genera señales de compra/venta de forma aleatoria.
    Útil exclusivamente para realizar pruebas rápidas en Paper Trading
    sin tener que esperar a que se cumplan condiciones técnicas reales.
    """

    def get_default_params(self) -> dict:
        return {
            'buy_probability': 40,
            'sell_probability': 40,
        }

    @classmethod
    def get_parameters_schema(cls) -> dict[str, dict[str, Any]]:
        return {
            'buy_probability': {
                'type': 'int',
                'min': 0,
                'max': 100,
                'default': 40,
                'description': 'Probabilidad de emitir señal de COMPRA (en %)'
            },
            'sell_probability': {
                'type': 'int',
                'min': 0,
                'max': 100,
                'default': 40,
                'description': 'Probabilidad de emitir señal de VENTA (en %)'
            },
        }

    def get_min_data_points(self) -> int:
        return 1

    def analyze(self, data: pd.DataFrame) -> Signal:
        current = data.iloc[-1]
        close_price = Decimal(str(current['close']))
        timestamp = current['timestamp']
        symbol = data['symbol'].iloc[-1] if 'symbol' in data.columns else 'UNKNOWN'

        # Usamos el minuto actual para alternar (par = compra, impar = venta)
        # Asegurándonos de que alterne de forma exacta cada minuto.
        current_minute = timestamp.minute

        if current_minute % 2 == 0:
            return Signal(
                signal_type='buy',
                symbol=symbol,
                strength=1.0,
                price=close_price,
                reason=f'Minuto Par ({current_minute}): Comprando',
                timestamp=timestamp
            )
        else:
            return Signal(
                signal_type='sell',
                symbol=symbol,
                strength=1.0,
                price=close_price,
                reason=f'Minuto Impar ({current_minute}): Vendiendo',
                timestamp=timestamp
            )
