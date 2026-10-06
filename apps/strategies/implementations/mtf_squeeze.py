import pandas as pd
from typing import Dict, Any, List
from apps.strategies.base import BaseStrategy, Signal
from apps.strategies.indicators import get_bollinger_bands, get_keltner_channels, get_ema, get_atr

class MTFSqueezeStrategy(BaseStrategy):
    DISPLAY_NAME = 'MTF Volatility Squeeze (Institucional)'
    """
    Estrategia Institucional Multi-Timeframe basada en el Squeeze de Volatilidad.
    
    1. MACRO (4H): Evalúa la tendencia principal usando una EMA 200.
    2. MICRO (Actual, ej 15m): 
       - Busca una compresión de volatilidad (Bollinger Bands dentro de Keltner Channels).
       - Espera a que el Squeeze "explote" (las BB salen de los KC).
       - Dispara una entrada solo si la explosión va a favor de la tendencia MACRO.
    3. RIESGO: SL y TP basados en el Average True Range (ATR) para adaptarse al mercado.
    """

    def get_extra_timeframes(self) -> List[str]:
        # Solicitamos siempre el histórico de 4h al motor para el contexto macro
        return ['4h']

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'squeeze_period': [20],
            'bb_std': [2.0],
            'kc_mult': [1.5],
            'macro_ema_period': [200],
            'tp_atr_mult': [2.0, 3.0, 4.0],
            'sl_atr_mult': [1.0, 1.5, 2.0]
        }
        
    def get_default_params(self) -> dict:
        return {
            'squeeze_period': 20,
            'bb_std': 2.0,
            'kc_mult': 1.5,
            'macro_ema_period': 200,
            'tp_atr_mult': 3.0,
            'sl_atr_mult': 1.5
        }

    def get_min_data_points(self) -> int:
        return 200 # Suficiente para el EMA 200 de macro si los arrays vinieran vacíos, aunque el motor precalienta

    def analyze(self, data: pd.DataFrame, extra_data: Dict[str, pd.DataFrame] = None) -> Signal:
        if extra_data is None or '4h' not in extra_data or extra_data['4h'].empty:
            return Signal(signal_type='hold', symbol='', reason='Faltan datos 4H')

        # Parámetros
        period = int(self.params.get('squeeze_period', 20))
        bb_std = float(self.params.get('bb_std', 2.0))
        kc_mult = float(self.params.get('kc_mult', 1.5))
        macro_ema_period = int(self.params.get('macro_ema_period', 200))
        tp_mult = float(self.params.get('tp_atr_mult', 3.0))
        sl_mult = float(self.params.get('sl_atr_mult', 1.5))

        current_price = data['close'].iloc[-1]
        
        # Portfolio
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
        current_macro_ema = ema_macro.iloc[-1]
        is_bull_market = df_4h['close'].iloc[-1] > current_macro_ema

        # ========================================================
        # 2. GESTIÓN DE RIESGO (Salidas)
        # ========================================================
        atr_series = get_atr(data['high'], data['low'], data['close'], period=14)
        current_atr = atr_series.iloc[-1]

        # Si tenemos posición abierta, calculamos TP y SL dinámicamente si no lo guardamos antes
        if position > 0 and avg_price > 0:
            sl_price = avg_price - (current_atr * sl_mult)
            tp_price = avg_price + (current_atr * tp_mult)
            if current_price <= sl_price:
                return Signal(signal_type='sell', symbol='', reason='Stop Loss Dinámico (ATR)')
            if current_price >= tp_price:
                return Signal(signal_type='sell', symbol='', reason='Take Profit Dinámico (ATR)')

        elif position < 0 and avg_price > 0:
            sl_price = avg_price + (current_atr * sl_mult)
            tp_price = avg_price - (current_atr * tp_mult)
            if current_price >= sl_price:
                return Signal(signal_type='cover', symbol='', reason='Stop Loss Dinámico (ATR)')
            if current_price <= tp_price:
                return Signal(signal_type='cover', symbol='', reason='Take Profit Dinámico (ATR)')

        # ========================================================
        # 3. GATILLO MICRO (Squeeze)
        # ========================================================
        if len(data) < period:
            return Signal(signal_type='hold', symbol='')

        bb = get_bollinger_bands(data['close'], period, bb_std)
        kc = get_keltner_channels(data, period, kc_mult)

        # ¿Está en Squeeze? (Bollinger dentro de Keltner)
        squeeze_on = (bb['Lower'] > kc['Lower']) & (bb['Upper'] < kc['Upper'])
        
        curr_sqz = squeeze_on.iloc[-1]
        prev_sqz = squeeze_on.iloc[-2]
        
        # Momentum direccional (usando la pendiente del EMA de corto plazo o el cierre vs EMA)
        momentum_up = current_price > kc['EMA'].iloc[-1]

        # ========================================================
        # 4. EJECUCIÓN DE ENTRADA
        # ========================================================
        # Solo disparamos cuando el Squeeze acaba de romperse (OFF) viniendo de (ON)
        squeeze_fired = prev_sqz and not curr_sqz

        if position == 0 and squeeze_fired:
            if is_bull_market and momentum_up:
                return Signal(signal_type='buy', symbol='', reason='Squeeze Fired UP (Bull Market)')
            elif not is_bull_market and not momentum_up:
                return Signal(signal_type='short', symbol='', reason='Squeeze Fired DOWN (Bear Market)')

        return Signal(signal_type='hold', symbol='')
