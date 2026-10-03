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
        buy_prob = int(self.params.get('buy_probability', 40))
        sell_prob = int(self.params.get('sell_probability', 40))

        current = data.iloc[-1]
        close_price = Decimal(str(current['close']))
        timestamp = current['timestamp']
        symbol = data['symbol'].iloc[-1] if 'symbol' in data.columns else 'UNKNOWN'

        # Tirar los dados (1 a 100)
        roll = random.randint(1, 100)

        if roll <= buy_prob:
            return Signal(
                signal_type='buy',
                symbol=symbol,
                strength=1.0,
                price=close_price,
                reason=f'Aleatorio: Ha salido {roll} (Prob. Compra: {buy_prob}%)',
                timestamp=timestamp
            )
        elif roll <= (buy_prob + sell_prob):
            return Signal(
                signal_type='sell',
                symbol=symbol,
                strength=1.0,
                price=close_price,
                reason=f'Aleatorio: Ha salido {roll} (Prob. Venta: {sell_prob}%)',
                timestamp=timestamp
            )
        
        return Signal(
            signal_type='hold',
            symbol=symbol,
            price=close_price,
            reason=f'Aleatorio: Ha salido {roll} (HOLD)',
            timestamp=timestamp
        )
