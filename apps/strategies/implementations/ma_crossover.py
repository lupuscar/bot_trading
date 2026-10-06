import pandas as pd
from typing import Any
from decimal import Decimal

from apps.strategies.base import BaseStrategy, Signal

class MACrossoverStrategy(BaseStrategy):
    DISPLAY_NAME = 'Cruce de Medias Móviles (SMA)'
    """
    Estrategia simple de Cruce de Medias Móviles (SMA).
    - Compra cuando la MA rápida cruza por encima de la MA lenta.
    - Vende cuando la MA rápida cruza por debajo de la MA lenta.
    """

    def get_default_params(self) -> dict:
        return {
            'fast_period': 10,
            'slow_period': 20,
        }

    @classmethod
    def get_parameters_schema(cls) -> dict[str, dict[str, Any]]:
        return {
            'fast_period': {
                'type': 'int',
                'min': 2,
                'max': 50,
                'default': 10,
                'description': 'Periodo de la SMA rápida'
            },
            'slow_period': {
                'type': 'int',
                'min': 5,
                'max': 200,
                'default': 20,
                'description': 'Periodo de la SMA lenta'
            },
        }

    @classmethod
    def get_optimization_parameters(cls) -> dict[str, list]:
        """Devuelve los rangos de parámetros para el Optimizador."""
        return {
            'fast_period': [5, 10, 20],
            'slow_period': [20, 50, 100]
        }

    def get_min_data_points(self) -> int:
        return self.params.get('slow_period', 20) + 1

    def analyze(self, data: pd.DataFrame) -> Signal:
        fast_period = int(self.params.get('fast_period', 10))
        slow_period = int(self.params.get('slow_period', 20))

        # Copiamos para no mutar el original (o asumimos que podemos añadir columnas)
        df = data.copy()

        # Calcular SMAs
        df['sma_fast'] = df['close'].rolling(window=fast_period).mean()
        df['sma_slow'] = df['close'].rolling(window=slow_period).mean()

        # Miramos los dos últimos períodos completados
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Comprobar cruces
        fast_over_slow_now = current['sma_fast'] > current['sma_slow']
        fast_over_slow_prev = previous['sma_fast'] > previous['sma_slow']

        # Precios
        close_price = Decimal(str(current['close']))
        timestamp = current['timestamp']
        # No symbol inside DataFrame if it's not grouped by, but we can return symbol=''
        # as it will be filled by the motor if needed, but wait, Signal requires symbol.
        symbol = df['symbol'].iloc[-1] if 'symbol' in df.columns else 'UNKNOWN'

        if fast_over_slow_now and not fast_over_slow_prev:
            # Golden Cross -> Buy
            return Signal(
                signal_type='buy',
                symbol=symbol,
                strength=0.8,
                price=close_price,
                reason='Golden Cross (SMA rápida cruzó por encima de SMA lenta)',
                metadata={'sma_fast': current['sma_fast'], 'sma_slow': current['sma_slow']},
                timestamp=timestamp
            )
        elif not fast_over_slow_now and fast_over_slow_prev:
            # Death Cross -> Sell/Close
            return Signal(
                signal_type='sell',
                symbol=symbol,
                strength=0.8,
                price=close_price,
                reason='Death Cross (SMA rápida cruzó por debajo de SMA lenta)',
                metadata={'sma_fast': current['sma_fast'], 'sma_slow': current['sma_slow']},
                timestamp=timestamp
            )
        
        # Ningún cruce
        return Signal(
            signal_type='hold',
            symbol=symbol,
            price=close_price,
            reason='Sin cruce de medias',
            metadata={'sma_fast': current['sma_fast'], 'sma_slow': current['sma_slow']},
            timestamp=timestamp
        )

    def get_chart_indicators(self, data: pd.DataFrame) -> dict:
        fast_period = int(self.params.get('fast_period', 10))
        slow_period = int(self.params.get('slow_period', 20))
        
        df = data.copy()
        df['sma_fast'] = df['close'].rolling(window=fast_period).mean()
        df['sma_slow'] = df['close'].rolling(window=slow_period).mean()
        
        fast_data = []
        slow_data = []
        
        for _, row in df.iterrows():
            time_val = int(row['timestamp'].timestamp())
            if pd.notna(row['sma_fast']):
                fast_data.append({'time': time_val, 'value': float(row['sma_fast'])})
            if pd.notna(row['sma_slow']):
                slow_data.append({'time': time_val, 'value': float(row['sma_slow'])})
                
        return {
            'sma_fast': {'name': f'SMA {fast_period}', 'color': '#2962FF', 'data': fast_data},
            'sma_slow': {'name': f'SMA {slow_period}', 'color': '#FF6D00', 'data': slow_data},
        }
