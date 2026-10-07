import pandas as pd
from typing import Dict, Any, List
from apps.strategies.base import BaseStrategy, Signal
from apps.strategies.indicators import get_bollinger_bands, get_rsi, get_ema, get_atr

class MeanReversionBBRSIStrategy(BaseStrategy):
    DISPLAY_NAME = 'Reversión a la Media (RSI + BB)'
    """
    Estrategia de Reversión a la Media combinando RSI y Bandas de Bollinger.
    
    Lógica:
    1. MACRO (4H): Identifica la tendencia principal (EMA 200). Solo operamos a favor de la tendencia.
       - Si el precio está por encima de la EMA 200 -> Buscamos compras (rebotes alcistas).
       - Si está por debajo -> Buscamos ventas/cortos (rebotes bajistas).
    2. MICRO (Actual):
       - COMPRA: El precio toca o rompe la Banda Inferior de Bollinger Y el RSI está sobrevendido.
       - VENTA CORTA: El precio toca o rompe la Banda Superior Y el RSI está sobrecomprado.
    3. SALIDAS:
       - Take Profit (TP) y Stop Loss (SL) dinámicos basados en ATR.
       - Salida alternativa: Retorno a la Banda Central (SMA) de Bollinger.
    """

    def get_extra_timeframes(self) -> List[str]:
        return ['4h']

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'rsi_period': {'type': 'int', 'default': 14},
            'rsi_oversold': {'type': 'int', 'default': 30},
            'rsi_overbought': {'type': 'int', 'default': 70},
            'bb_period': {'type': 'int', 'default': 20},
            'bb_std': {'type': 'float', 'default': 2.0},
            'macro_ema_period': {'type': 'int', 'default': 200},
            'tp_atr_mult': {'type': 'float', 'default': 2.0},
            'sl_atr_mult': {'type': 'float', 'default': 1.5}
        }

    @classmethod
    def get_optimization_parameters(cls) -> Dict[str, Any]:
        return {
            'rsi_period': [14],
            'rsi_oversold': [25, 30, 35],
            'rsi_overbought': [65, 70, 75],
            'bb_period': [20, 30],
            'bb_std': [2.0, 2.5],
            'macro_ema_period': [100, 200],
            'tp_atr_mult': [1.5, 2.0, 3.0],
            'sl_atr_mult': [1.0, 1.5, 2.0]
        }
        
    def get_default_params(self) -> dict:
        return {
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'bb_period': 20,
            'bb_std': 2.0,
            'macro_ema_period': 200,
            'tp_atr_mult': 2.0,
            'sl_atr_mult': 1.5
        }

    def get_min_data_points(self) -> int:
        return 200

    def analyze(self, data: pd.DataFrame, extra_data: Dict[str, pd.DataFrame] = None) -> Signal:
        if extra_data is None or '4h' not in extra_data or extra_data['4h'].empty:
            return Signal(signal_type='hold', symbol='', reason='Faltan datos 4H')

        # Parámetros
        rsi_period = int(self.params.get('rsi_period', 14))
        rsi_oversold = int(self.params.get('rsi_oversold', 30))
        rsi_overbought = int(self.params.get('rsi_overbought', 70))
        bb_period = int(self.params.get('bb_period', 20))
        bb_std = float(self.params.get('bb_std', 2.0))
        macro_ema_period = int(self.params.get('macro_ema_period', 200))
        tp_mult = float(self.params.get('tp_atr_mult', 2.0))
        sl_mult = float(self.params.get('sl_atr_mult', 1.5))

        current_price = data['close'].iloc[-1]
        
        # Estado de la Cartera
        portfolio = getattr(self, 'portfolio', {})
        position = float(portfolio.get('position', 0))
        avg_price = float(portfolio.get('position_avg_price', 0))

        # ========================================================
        # 1. CONTEXTO MACRO (4H)
        # ========================================================
        df_4h = extra_data['4h']
        if len(df_4h) < macro_ema_period:
            return Signal(signal_type='hold', symbol='', reason='Warmup Macro 4H insuficiente')

        ema_macro = get_ema(df_4h['close'], macro_ema_period)
        is_bull_market = df_4h['close'].iloc[-1] > ema_macro.iloc[-1]

        # ========================================================
        # 2. GESTIÓN DE RIESGO Y SALIDAS (Posición Abierta)
        # ========================================================
        atr_series = get_atr(data['high'], data['low'], data['close'], period=14)
        current_atr = atr_series.iloc[-1]
        
        bb = get_bollinger_bands(data['close'], bb_period, bb_std)
        bb_sma = bb['SMA'].iloc[-1]

        if position > 0 and avg_price > 0:
            sl_price = avg_price - (current_atr * sl_mult)
            tp_price = avg_price + (current_atr * tp_mult)
            
            # Salida de emergencia: Trailing a la media (SMA central)
            # En reversión a la media, si tocamos la media, suele ser buen punto para asegurar al menos parciales.
            if current_price >= bb_sma and avg_price < bb_sma:
                return Signal(signal_type='sell', symbol='', reason='Mean Reversion Completada (Vuelta a SMA)')
                
            if current_price <= sl_price:
                return Signal(signal_type='sell', symbol='', reason='Stop Loss (ATR)')
            if current_price >= tp_price:
                return Signal(signal_type='sell', symbol='', reason='Take Profit (ATR)')

        elif position < 0 and avg_price > 0:
            sl_price = avg_price + (current_atr * sl_mult)
            tp_price = avg_price - (current_atr * tp_mult)
            
            if current_price <= bb_sma and avg_price > bb_sma:
                return Signal(signal_type='cover', symbol='', reason='Mean Reversion Completada (Vuelta a SMA)')

            if current_price >= sl_price:
                return Signal(signal_type='cover', symbol='', reason='Stop Loss (ATR)')
            if current_price <= tp_price:
                return Signal(signal_type='cover', symbol='', reason='Take Profit (ATR)')

        # ========================================================
        # 3. GATILLO MICRO (Entradas)
        # ========================================================
        if position == 0:
            rsi = get_rsi(data['close'], rsi_period)
            current_rsi = rsi.iloc[-1]
            current_bb_lower = bb['Lower'].iloc[-1]
            current_bb_upper = bb['Upper'].iloc[-1]
            current_low = data['low'].iloc[-1]
            current_high = data['high'].iloc[-1]
            
            # ¿Estamos fuera/tocando las bandas con las mechas?
            touching_lower = current_low <= current_bb_lower
            touching_upper = current_high >= current_bb_upper
            
            # COMPRA LARGOS: En tendencia alcista macro, el precio cae fuerte a la banda inferior y RSI está sobrevendido
            if is_bull_market and touching_lower and current_rsi <= rsi_oversold:
                return Signal(signal_type='buy', symbol='', reason='Rebote RSI/BB Alcista (Bull Market)')
                
            # VENTA CORTOS: En tendencia bajista macro, el precio sube a la banda superior y RSI está sobrecomprado
            if not is_bull_market and touching_upper and current_rsi >= rsi_overbought:
                return Signal(signal_type='short', symbol='', reason='Rechazo RSI/BB Bajista (Bear Market)')

        return Signal(signal_type='hold', symbol='')
