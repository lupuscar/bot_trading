import pandas as pd
from typing import Dict, Any, List
from apps.strategies.base import BaseStrategy, Signal
from apps.strategies.indicators import get_ema, get_macd, get_atr

class TrendFollowingMACDStrategy(BaseStrategy):
    DISPLAY_NAME = 'Seguimiento de Tendencia (MACD + EMA)'
    """
    Estrategia diseñada específicamente para activos de fuerte tendencia como Bitcoin.
    
    Lógica:
    1. MACRO (4H): Identifica la dirección general usando EMA 200.
    2. MICRO (Actual):
       - COMPRA: Si el MACD cruza al alza la señal (Histograma pasa a positivo) y el precio está sobre una EMA rápida (ej. EMA 50).
       - VENTA CORTA: Si el MACD cruza a la baja la señal y el precio está bajo la EMA rápida.
    3. SALIDAS:
       - Stop Loss usando ATR para adaptarse a la volatilidad.
       - Take Profit agresivo (tendencial) o salida cuando el MACD se cruza en contra.
    """

    def get_extra_timeframes(self) -> List[str]:
        return ['4h']

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'ema_fast': {'type': 'int', 'default': 50},
            'macd_fast': {'type': 'int', 'default': 12},
            'macd_slow': {'type': 'int', 'default': 26},
            'macd_signal': {'type': 'int', 'default': 9},
            'macro_ema': {'type': 'int', 'default': 200},
            'tp_atr_mult': {'type': 'float', 'default': 5.0},
            'sl_atr_mult': {'type': 'float', 'default': 2.0}
        }

    @classmethod
    def get_optimization_parameters(cls) -> Dict[str, Any]:
        return {
            'ema_fast': [20, 50],
            'macd_fast': [12],
            'macd_slow': [26],
            'macd_signal': [9],
            'macro_ema': [100, 200],
            'tp_atr_mult': [3.0, 5.0, 7.0], # TP más amplio para dejar correr la tendencia
            'sl_atr_mult': [1.5, 2.0]
        }
        
    def get_default_params(self) -> dict:
        return {
            'ema_fast': 50,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'macro_ema': 200,
            'tp_atr_mult': 5.0,
            'sl_atr_mult': 2.0
        }

    def get_min_data_points(self) -> int:
        return 200

    def analyze(self, data: pd.DataFrame, extra_data: Dict[str, pd.DataFrame] = None) -> Signal:
        if extra_data is None or '4h' not in extra_data or extra_data['4h'].empty:
            return Signal(signal_type='hold', symbol='', reason='Faltan datos 4H')

        # Parámetros
        ema_fast_p = int(self.params.get('ema_fast', 50))
        m_fast = int(self.params.get('macd_fast', 12))
        m_slow = int(self.params.get('macd_slow', 26))
        m_sig = int(self.params.get('macd_signal', 9))
        macro_ema_p = int(self.params.get('macro_ema', 200))
        tp_mult = float(self.params.get('tp_atr_mult', 5.0))
        sl_mult = float(self.params.get('sl_atr_mult', 2.0))

        current_price = data['close'].iloc[-1]
        
        # Portfolio
        portfolio = getattr(self, 'portfolio', {})
        position = float(portfolio.get('position', 0))
        avg_price = float(portfolio.get('position_avg_price', 0))

        # 1. MACRO
        df_4h = extra_data['4h']
        if len(df_4h) < macro_ema_p:
            return Signal(signal_type='hold', symbol='', reason='Warmup Macro insuficiente')
        ema_macro = get_ema(df_4h['close'], macro_ema_p).iloc[-1]
        is_bull_market = df_4h['close'].iloc[-1] > ema_macro

        # 2. RIESGO / SALIDAS
        atr = get_atr(data['high'], data['low'], data['close'], period=14).iloc[-1]
        macd_df = get_macd(data['close'], m_fast, m_slow, m_sig)
        current_hist = macd_df['Histogram'].iloc[-1]
        prev_hist = macd_df['Histogram'].iloc[-2]

        if position > 0 and avg_price > 0:
            sl_price = avg_price - (atr * sl_mult)
            tp_price = avg_price + (atr * tp_mult)
            
            # Salida táctica si se pierde momentum fuerte en contra
            if current_hist < 0 and prev_hist >= 0:
                return Signal(signal_type='sell', symbol='', reason='MACD cruzó a la baja (Cierre de Largos)')
                
            if current_price <= sl_price:
                return Signal(signal_type='sell', symbol='', reason='Stop Loss (ATR)')
            if current_price >= tp_price:
                return Signal(signal_type='sell', symbol='', reason='Take Profit (ATR)')

        elif position < 0 and avg_price > 0:
            sl_price = avg_price + (atr * sl_mult)
            tp_price = avg_price - (atr * tp_mult)
            
            if current_hist > 0 and prev_hist <= 0:
                return Signal(signal_type='cover', symbol='', reason='MACD cruzó al alza (Cierre de Cortos)')

            if current_price >= sl_price:
                return Signal(signal_type='cover', symbol='', reason='Stop Loss (ATR)')
            if current_price <= tp_price:
                return Signal(signal_type='cover', symbol='', reason='Take Profit (ATR)')

        # 3. ENTRADAS
        if position == 0:
            ema_fast = get_ema(data['close'], ema_fast_p).iloc[-1]
            
            # Cruce de MACD al alza (Histograma pasa a positivo)
            macd_bullish_cross = current_hist > 0 and prev_hist <= 0
            # Cruce de MACD a la baja
            macd_bearish_cross = current_hist < 0 and prev_hist >= 0

            # Filtros de tendencia
            price_above_ema = current_price > ema_fast
            price_below_ema = current_price < ema_fast

            if is_bull_market and price_above_ema and macd_bullish_cross:
                return Signal(signal_type='buy', symbol='', reason='Tendencia MACD (Bull Market)')
                
            if not is_bull_market and price_below_ema and macd_bearish_cross:
                return Signal(signal_type='short', symbol='', reason='Tendencia MACD (Bear Market)')

        return Signal(signal_type='hold', symbol='')
