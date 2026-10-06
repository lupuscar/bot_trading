import pandas as pd
from apps.strategies.base import BaseStrategy, Signal
from apps.strategies.indicators import get_rsi, get_ema

class RSIReversionStrategy(BaseStrategy):
    """
    Estrategia Evolucionada de Reversión a la Media (RSI + Trend Filter).
    - Entra en LARGO (Long) cuando el RSI cruza por debajo del umbral de sobreventa (ej. 30).
    - Entra en CORTO (Short) cuando el RSI cruza por encima del umbral de sobrecompra (ej. 70).
    - Cierra la posición cuando el RSI vuelve a la zona neutral (ej. 50).
    """
    
    DISPLAY_NAME = 'RSI Mean Reversion (Long & Short)'

    @classmethod
    def get_optimization_parameters(cls) -> dict[str, list]:
        """Devuelve los rangos de parámetros para el Optimizador."""
        return {
            'rsi_period': [10, 14],
            'oversold_level': [25, 30],
            'overbought_level': [70, 75],
            'ema_period': [100, 200],
            'take_profit_pct': [2.0, 4.0, 6.0],
            'stop_loss_pct': [2.0, 3.0]
        }
        
    def get_default_params(self) -> dict:
        return {
            'rsi_period': 14,
            'oversold_level': 30,
            'overbought_level': 70,
            'ema_period': 200,
            'take_profit_pct': 4.0,
            'stop_loss_pct': 2.0
        }

    def get_min_data_points(self) -> int:
        return self.params.get('ema_period', 200) + 5

    def analyze(self, data: pd.DataFrame) -> Signal:
        period = int(self.params.get('rsi_period', 14))
        oversold = float(self.params.get('oversold_level', 30))
        overbought = float(self.params.get('overbought_level', 70))
        ema_period = int(self.params.get('ema_period', 200))
        tp_pct = float(self.params.get('take_profit_pct', 4.0)) / 100.0
        sl_pct = float(self.params.get('stop_loss_pct', 2.0)) / 100.0
        
        close_prices = data['close']
        current_price = close_prices.iloc[-1]
        timestamp = data.iloc[-1]['timestamp']
        
        # Portfolio state
        portfolio = getattr(self, 'portfolio', {})
        position = float(portfolio.get('position', 0))
        avg_price = float(portfolio.get('position_avg_price', 0))
        
        # 1. Calcular EMA Macro (Trend Filter)
        data['EMA'] = get_ema(close_prices, ema_period)
        current_ema = data['EMA'].iloc[-1]
        is_bull_market = current_price > current_ema
        
        # 2. Calcular RSI
        data['RSI'] = get_rsi(data['close'], period)
        rsi = data['RSI']
        
        if rsi is None or len(rsi) < 2 or pd.isna(rsi.iloc[-1]):
            return Signal(signal_type='hold', symbol='')
            
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        
        # 3. Lógica de Salida (TP / SL)
        if position > 0 and avg_price > 0:
            profit_pct = (current_price - avg_price) / avg_price
            if profit_pct >= tp_pct:
                return Signal(signal_type='sell', symbol='', reason=f"Take Profit Long ({profit_pct*100:.2f}%)")
            elif profit_pct <= -sl_pct:
                return Signal(signal_type='sell', symbol='', reason=f"Stop Loss Long ({profit_pct*100:.2f}%)")
                
        elif position < 0 and avg_price > 0:
            # En corto, ganamos si el precio baja
            profit_pct = (avg_price - current_price) / avg_price
            if profit_pct >= tp_pct:
                return Signal(signal_type='cover', symbol='', reason=f"Take Profit Short ({profit_pct*100:.2f}%)")
            elif profit_pct <= -sl_pct:
                return Signal(signal_type='cover', symbol='', reason=f"Stop Loss Short ({profit_pct*100:.2f}%)")
        
        # 4. Lógica de Entrada
        # Long solo en Bull Market (precio > EMA200) cuando cae el RSI
        if position == 0 and is_bull_market and prev_rsi >= oversold and current_rsi < oversold:
            return Signal(
                signal_type='buy',
                symbol='',
                reason=f"Bull Market: RSI cruzó Sobreventa ({current_rsi:.1f} < {oversold})"
            )
            
        # Short solo en Bear Market (precio < EMA200) cuando sube el RSI
        if position == 0 and not is_bull_market and prev_rsi <= overbought and current_rsi > overbought:
            return Signal(
                signal_type='short',
                symbol='',
                reason=f"Bear Market: RSI cruzó Sobrecompra ({current_rsi:.1f} > {overbought})"
            )

        return Signal(signal_type='hold', symbol='')
