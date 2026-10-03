import pandas as pd
from typing import Any
from decimal import Decimal

from apps.strategies.base import BaseStrategy, Signal

class SolanaScalpingStrategy(BaseStrategy):
    DISPLAY_NAME = 'Solana Scalping (EMA + RSI)'
    """
    Estrategia de Scalping diseñada para activos volátiles como Solana (SOL).
    - Usa cruce de EMA rápida y lenta para la dirección de la tendencia.
    - Filtra entradas usando RSI para evitar comprar en sobrecompra o vender en sobreventa.
    - Ideal para temporalidades cortas (1m, 5m, 15m).
    """

    def get_default_params(self) -> dict:
        return {
            'ema_fast_period': 9,
            'ema_slow_period': 21,
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
        }

    @classmethod
    def get_parameters_schema(cls) -> dict[str, dict[str, Any]]:
        return {
            'ema_fast_period': {
                'type': 'int', 'min': 3, 'max': 50, 'default': 9,
                'description': 'Periodo de la EMA rápida'
            },
            'ema_slow_period': {
                'type': 'int', 'min': 10, 'max': 200, 'default': 21,
                'description': 'Periodo de la EMA lenta'
            },
            'rsi_period': {
                'type': 'int', 'min': 2, 'max': 50, 'default': 14,
                'description': 'Periodo del RSI'
            },
            'rsi_overbought': {
                'type': 'int', 'min': 50, 'max': 100, 'default': 70,
                'description': 'Nivel de sobrecompra del RSI'
            },
            'rsi_oversold': {
                'type': 'int', 'min': 0, 'max': 50, 'default': 30,
                'description': 'Nivel de sobreventa del RSI'
            },
        }

    def get_min_data_points(self) -> int:
        # Requerimos suficientes datos para la EMA lenta y el RSI
        return max(self.params.get('ema_slow_period', 21), self.params.get('rsi_period', 14)) * 3

    def get_required_timeframe(self) -> str:
        return '5m' # Scalping default

    def analyze(self, data: pd.DataFrame) -> Signal:
        ema_fast_period = int(self.params.get('ema_fast_period', 9))
        ema_slow_period = int(self.params.get('ema_slow_period', 21))
        rsi_period = int(self.params.get('rsi_period', 14))
        rsi_overbought = int(self.params.get('rsi_overbought', 70))
        rsi_oversold = int(self.params.get('rsi_oversold', 30))

        df = data.copy()

        # Calcular EMAs
        df['ema_fast'] = df['close'].ewm(span=ema_fast_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=ema_slow_period, adjust=False).mean()

        # Calcular RSI manualmente con Pandas
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        avg_gain = gain.rolling(window=rsi_period, min_periods=rsi_period).mean()
        avg_loss = loss.rolling(window=rsi_period, min_periods=rsi_period).mean()
        
        # Usar ewm para los siguientes valores del RSI (estándar de Wilder)
        avg_gain = gain.ewm(alpha=1/rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/rsi_period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))

        current = df.iloc[-1]
        previous = df.iloc[-2]

        fast_over_slow_now = current['ema_fast'] > current['ema_slow']
        fast_over_slow_prev = previous['ema_fast'] > previous['ema_slow']
        
        current_rsi = current['rsi']

        close_price = Decimal(str(current['close']))
        timestamp = current['timestamp']
        symbol = df['symbol'].iloc[-1] if 'symbol' in df.columns else 'SOL/USDT'

        metadata = {
            'ema_fast': current['ema_fast'], 
            'ema_slow': current['ema_slow'],
            'rsi': current_rsi
        }

        # Lógica de compra: Cruce alcista de EMA + RSI no está sobrecomprado
        if fast_over_slow_now and not fast_over_slow_prev and current_rsi < rsi_overbought:
            return Signal(
                signal_type='buy',
                symbol=symbol,
                strength=0.85,
                price=close_price,
                reason='Cruce Alcista EMA y RSI óptimo',
                metadata=metadata,
                timestamp=timestamp
            )
        
        # Lógica de venta: Cruce bajista de EMA + RSI no está sobrevendido
        elif not fast_over_slow_now and fast_over_slow_prev and current_rsi > rsi_oversold:
            return Signal(
                signal_type='sell',
                symbol=symbol,
                strength=0.85,
                price=close_price,
                reason='Cruce Bajista EMA y RSI óptimo',
                metadata=metadata,
                timestamp=timestamp
            )

        # Si el RSI llega a extremos muy grandes y estamos posicionados, podríamos sugerir cierre, 
        # pero la estrategia base envía hold y asume que SL/TP del motor de trading manejan el riesgo.
        
        return Signal(
            signal_type='hold',
            symbol=symbol,
            price=close_price,
            reason='Esperando oportunidad clara de scalping',
            metadata=metadata,
            timestamp=timestamp
        )

    def get_chart_indicators(self, data: pd.DataFrame) -> dict:
        ema_fast_period = int(self.params.get('ema_fast_period', 9))
        ema_slow_period = int(self.params.get('ema_slow_period', 21))
        
        df = data.copy()
        df['ema_fast'] = df['close'].ewm(span=ema_fast_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=ema_slow_period, adjust=False).mean()
        
        fast_data = []
        slow_data = []
        
        for _, row in df.iterrows():
            time_val = int(row['timestamp'].timestamp())
            if pd.notna(row['ema_fast']):
                fast_data.append({'time': time_val, 'value': float(row['ema_fast'])})
            if pd.notna(row['ema_slow']):
                slow_data.append({'time': time_val, 'value': float(row['ema_slow'])})
                
        return {
            'ema_fast': {'name': f'EMA {ema_fast_period}', 'color': '#00E676', 'data': fast_data},
            'ema_slow': {'name': f'EMA {ema_slow_period}', 'color': '#FF1744', 'data': slow_data},
        }
