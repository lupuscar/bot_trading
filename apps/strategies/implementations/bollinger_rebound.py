import pandas as pd
from typing import Dict, Any
from apps.strategies.base import BaseStrategy, Signal

class BollingerReboundStrategy(BaseStrategy):
    DISPLAY_NAME = 'Bollinger Rebound (Rango Lateral)'
    """
    Estrategia de reversión a la media perfecta para mercados laterales.
    Compra cuando el precio rebota en la Banda de Bollinger inferior 
    y vende al tocar la banda superior o alcanzar el Take Profit.
    """

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'bb_period': {
                'type': 'number',
                'default': 20,
                'description': 'Periodo de la SMA central (Ej: 20)'
            },
            'bb_std': {
                'type': 'number',
                'default': 2.0,
                'description': 'Desviaciones estándar para las bandas (Ej: 2.0 o 2.5)'
            },
            'take_profit_pct': {
                'type': 'number',
                'default': 5.0,
                'description': 'Take Profit (%) de seguridad'
            },
            'stop_loss_pct': {
                'type': 'number',
                'default': 4.0,
                'description': 'Stop Loss (%) de seguridad'
            }
        }

    def get_default_params(self) -> dict:
        return {
            'bb_period': 20,
            'bb_std': 2.0,
            'take_profit_pct': 5.0,
            'stop_loss_pct': 4.0
        }

    def set_portfolio_state(self, state: Dict[str, Any]):
        self.portfolio = state

    def get_min_data_points(self) -> int:
        return int(self.params.get('bb_period', 20)) + 5

    def analyze(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.get_min_data_points():
            return Signal(
                signal_type='hold', 
                symbol='',
                timestamp=df.iloc[-1]['timestamp'], 
                reason=f"Esperando datos ({self.get_min_data_points()} velas)"
            )

        bb_period = int(self.params.get('bb_period', 20))
        bb_std = float(self.params.get('bb_std', 2.0))
        tp_pct = float(self.params.get('take_profit_pct', 5.0)) / 100.0
        sl_pct = float(self.params.get('stop_loss_pct', 4.0)) / 100.0

        close_prices = df['close']
        timestamp = df.iloc[-1]['timestamp']
        current_price = close_prices.iloc[-1]
        previous_price = close_prices.iloc[-2]

        # Estado del portfolio
        portfolio = getattr(self, 'portfolio', {})
        position = float(portfolio.get('position', 0))
        avg_price = float(portfolio.get('position_avg_price', 0))

        # 1. Calcular Bandas de Bollinger
        df['SMA'] = close_prices.rolling(window=bb_period).mean()
        df['STD'] = close_prices.rolling(window=bb_period).std()
        df['Upper'] = df['SMA'] + (df['STD'] * bb_std)
        df['Lower'] = df['SMA'] - (df['STD'] * bb_std)

        curr_lower = df['Lower'].iloc[-1]
        prev_lower = df['Lower'].iloc[-2]
        curr_upper = df['Upper'].iloc[-1]

        # 2. Lógica de Salida (Gestión de Riesgo y Banda Superior)
        if position > 0 and avg_price > 0:
            profit_pct = (current_price - avg_price) / avg_price
            
            # Salida 1: Take Profit por porcentaje
            if profit_pct >= tp_pct:
                return Signal(
                    signal_type='sell',
                    symbol='',
                    timestamp=timestamp,
                    price=current_price,
                    reason=f"Take Profit ({profit_pct*100:.2f}%). Comprado a {avg_price:.2f}"
                )
            # Salida 2: Stop Loss por porcentaje
            elif profit_pct <= -sl_pct:
                return Signal(
                    signal_type='sell',
                    symbol='',
                    timestamp=timestamp,
                    price=current_price,
                    reason=f"Stop Loss ({profit_pct*100:.2f}%). Comprado a {avg_price:.2f}"
                )
            # Salida 3: Dinámica (Toca banda superior)
            elif current_price >= curr_upper:
                return Signal(
                    signal_type='sell',
                    symbol='',
                    timestamp=timestamp,
                    price=current_price,
                    reason=f"Precio tocó Banda Superior ({curr_upper:.2f}). PnL: {profit_pct*100:.2f}%"
                )

        # 3. Lógica de Entrada
        # Compramos SOLO si el precio acaba de cruzar hacia arriba la banda inferior 
        # (confirmando que el rebote ha empezado tras tocar fondo).
        if position == 0:
            bounce_confirmed = previous_price <= prev_lower and current_price > curr_lower
            
            if bounce_confirmed:
                return Signal(
                    signal_type='buy',
                    symbol='',
                    timestamp=timestamp,
                    price=current_price,
                    reason=f"Rebote confirmado en Banda Inferior ({curr_lower:.2f})"
                )

        estado_pos = f"Hold (Comprado: {avg_price:.2f})" if position > 0 else "Buscando rebote"
        return Signal(
            signal_type='hold',
            symbol='',
            timestamp=timestamp,
            price=current_price,
            reason=f"{estado_pos}. Limites BB: [{curr_lower:.2f} - {curr_upper:.2f}]"
        )

    def get_chart_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        indicators = {}
        bb_period = int(self.params.get('bb_period', 20))
        bb_std = float(self.params.get('bb_std', 2.0))
        
        if len(df) >= bb_period:
            sma = df['close'].rolling(window=bb_period).mean()
            std = df['close'].rolling(window=bb_period).std()
            upper = sma + (std * bb_std)
            lower = sma - (std * bb_std)
            
            # Banda Superior
            upper_data = []
            lower_data = []
            for i, row in df.iterrows():
                if not pd.isna(upper[i]):
                    ts = int(row['timestamp'].timestamp())
                    upper_data.append({'time': ts, 'value': float(upper[i])})
                    lower_data.append({'time': ts, 'value': float(lower[i])})
            
            indicators['BB_Upper'] = {
                'type': 'line',
                'title': f'BB Upper ({bb_std}σ)',
                'color': '#ef4444', # Rojo
                'data': upper_data,
                'pane': 0 
            }
            indicators['BB_Lower'] = {
                'type': 'line',
                'title': f'BB Lower ({bb_std}σ)',
                'color': '#10b981', # Verde
                'data': lower_data,
                'pane': 0 
            }

        return indicators
