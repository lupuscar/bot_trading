import pandas as pd
from typing import Dict, Any
from apps.strategies.base import BaseStrategy, Signal

class BuyTheDipStrategy(BaseStrategy):
    DISPLAY_NAME = 'Buy The Dip (Tendencia + Pánico)'
    """
    Estrategia híbrida ganadora clásica en criptomonedas.
    Filtra el mercado a través de una media móvil de largo plazo (EMA 200) para asegurar 
    que estamos en tendencia alcista. Luego, busca correcciones bruscas (pánico) 
    utilizando el RSI (oversold) para comprar barato y salir rápido en el rebote.
    """

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'ema_period': {
                'type': 'number',
                'default': 200,
                'description': 'Periodo de la EMA macro (Ej: 200)'
            },
            'rsi_period': {
                'type': 'number',
                'default': 14,
                'description': 'Periodo del RSI'
            },
            'rsi_buy_level': {
                'type': 'number',
                'default': 30,
                'description': 'RSI de compra (sobreventa)'
            },
            'take_profit_pct': {
                'type': 'number',
                'default': 5.0,
                'description': 'Take Profit (%) - Objetivo de ganancias'
            },
            'stop_loss_pct': {
                'type': 'number',
                'default': 3.0,
                'description': 'Stop Loss (%) - Máxima pérdida permitida'
            }
        }

    def get_default_params(self) -> dict:
        return {
            'ema_period': 200,
            'rsi_period': 14,
            'rsi_buy_level': 30,
            'take_profit_pct': 5.0,
            'stop_loss_pct': 3.0
        }

    def set_portfolio_state(self, state: Dict[str, Any]):
        self.portfolio = state

    def get_min_data_points(self) -> int:
        return max(
            int(self.params.get('ema_period', 200)), 
            int(self.params.get('rsi_period', 14))
        ) + 10

    def analyze(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.get_min_data_points():
            return Signal(
                signal_type='hold', 
                symbol='',
                timestamp=df.iloc[-1]['timestamp'], 
                reason=f"Esperando datos (necesita {self.get_min_data_points()} velas)"
            )

        ema_period = int(self.params.get('ema_period', 200))
        rsi_period = int(self.params.get('rsi_period', 14))
        rsi_buy = float(self.params.get('rsi_buy_level', 30.0))
        tp_pct = float(self.params.get('take_profit_pct', 5.0)) / 100.0
        sl_pct = float(self.params.get('stop_loss_pct', 3.0)) / 100.0

        close_prices = df['close']
        current_price = close_prices.iloc[-1]
        timestamp = df.iloc[-1]['timestamp']
        
        # Estado del portfolio
        portfolio = getattr(self, 'portfolio', {})
        position = float(portfolio.get('position', 0))
        avg_price = float(portfolio.get('position_avg_price', 0))

        # 1. Calcular EMA Macro
        df['EMA_Macro'] = close_prices.ewm(span=ema_period, adjust=False).mean()
        current_ema = df['EMA_Macro'].iloc[-1]
        is_bull_market = current_price > current_ema

        # 2. Calcular RSI
        delta = close_prices.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=rsi_period - 1, adjust=False).mean()
        ema_down = down.ewm(com=rsi_period - 1, adjust=False).mean()
        rs = ema_up / ema_down
        df['RSI'] = 100 - (100 / (1 + rs))
        current_rsi = df['RSI'].iloc[-1]

        # 3. Lógica de Salida (Take Profit / Stop Loss)
        if position > 0 and avg_price > 0:
            profit_pct = (current_price - avg_price) / avg_price
            
            if profit_pct >= tp_pct:
                return Signal(
                    signal_type='sell',
                    symbol='',
                    timestamp=timestamp,
                    price=current_price,
                    reason=f"Take Profit alcanzado. Ganancia: {profit_pct*100:.2f}% (Comprado a {avg_price:.2f})"
                )
            elif profit_pct <= -sl_pct:
                return Signal(
                    signal_type='sell',
                    symbol='',
                    timestamp=timestamp,
                    price=current_price,
                    reason=f"Stop Loss activado. Pérdida: {profit_pct*100:.2f}% (Comprado a {avg_price:.2f})"
                )

        # 4. Lógica de Entrada
        if position == 0 and is_bull_market and current_rsi <= rsi_buy:
            return Signal(
                signal_type='buy',
                symbol='',
                timestamp=timestamp,
                price=current_price,
                reason=f"Pánico alcista (Precio > EMA{ema_period}, RSI = {current_rsi:.2f})"
            )
        
        estado_tendencia = "Alcista" if is_bull_market else "Bajista"
        estado_pos = f"Hold (Entrada: {avg_price:.2f})" if position > 0 else "Buscando entrada"
        return Signal(
            signal_type='hold',
            symbol='',
            timestamp=timestamp,
            price=current_price,
            reason=f"{estado_pos}. Tendencia: {estado_tendencia}, RSI: {current_rsi:.2f}."
        )

    def get_chart_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        indicators = {}
        ema_period = int(self.params.get('ema_period', 200))
        
        # EMA en el panel principal (pane: 0)
        if len(df) >= ema_period:
            df['EMA_Macro'] = df['close'].ewm(span=ema_period, adjust=False).mean()
            ema_data = []
            for _, row in df.iterrows():
                if not pd.isna(row['EMA_Macro']):
                    ts = int(row['timestamp'].timestamp())
                    ema_data.append({'time': ts, 'value': float(row['EMA_Macro'])})
            
            indicators[f'EMA_{ema_period}'] = {
                'type': 'line',
                'title': f'EMA {ema_period}',
                'color': '#f59e0b', # Naranja (Golden)
                'data': ema_data,
                'pane': 0 
            }

        # RSI en un panel secundario (pane: 1)
        rsi_period = int(self.params.get('rsi_period', 14))
        if len(df) >= rsi_period:
            delta = df['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=rsi_period - 1, adjust=False).mean()
            ema_down = down.ewm(com=rsi_period - 1, adjust=False).mean()
            rs = ema_up / ema_down
            df['RSI'] = 100 - (100 / (1 + rs))

            rsi_data = []
            for _, row in df.iterrows():
                if not pd.isna(row['RSI']):
                    ts = int(row['timestamp'].timestamp())
                    rsi_data.append({'time': ts, 'value': float(row['RSI'])})

            indicators['RSI'] = {
                'type': 'line',
                'title': f'RSI ({rsi_period})',
                'color': '#8b5cf6', # Morado
                'data': rsi_data,
                'pane': 1 
            }

        return indicators
