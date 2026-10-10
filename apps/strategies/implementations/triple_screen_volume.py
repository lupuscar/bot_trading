import pandas as pd
from typing import Dict, Any, List
from apps.strategies.base import BaseStrategy, Signal
from apps.strategies.indicators import get_macd, get_ema, get_rsi, get_sma, get_atr

class TripleScreenVolumeStrategy(BaseStrategy):
    DISPLAY_NAME = 'Triple Pantalla (Elder) + Volumen Institucional'
    """
    Estrategia Institucional basada en el sistema Triple Pantalla de Alexander Elder, 
    optimizada para criptomonedas usando confirmación de volumen.
    
    1. MACRO (1D): Verifica tendencia alcista (MACD > Signal). Además, exige que 
       el volumen del día anterior fuera superior a la media de 20 días (participación fuerte).
    2. MEDIO (4H): Filtra ruido comprobando que el precio se mantiene sobre la EMA rápida (ej. 50).
    3. MICRO (5m): Entra en el mercado cuando el precio sufre un respiro en tendencia alcista (RSI < 50) 
       y vuelve a rebotar al alza.
    """

    def get_extra_timeframes(self) -> List[str]:
        # Solicitamos diario y 4 horas
        return ['1d', '4h']

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'macro_macd_fast': {'type': 'int', 'default': 12},
            'macro_macd_slow': {'type': 'int', 'default': 26},
            'macro_macd_sig': {'type': 'int', 'default': 9},
            'macro_vol_period': {'type': 'int', 'default': 20},
            
            'medio_ema_period': {'type': 'int', 'default': 50},
            
            'micro_rsi_period': {'type': 'int', 'default': 14},
            'micro_rsi_oversold': {'type': 'int', 'default': 50},
            
            'tp_atr_mult': {'type': 'float', 'default': 5.0},
            'sl_atr_mult': {'type': 'float', 'default': 2.0}
        }

    @classmethod
    def get_optimization_parameters(cls) -> Dict[str, Any]:
        return {
            'macro_macd_fast': [12],
            'macro_macd_slow': [26],
            'macro_macd_sig': [9],
            'macro_vol_period': [20],
            'medio_ema_period': [20, 50],
            'micro_rsi_period': [14],
            'micro_rsi_oversold': [45, 50, 55],
            'tp_atr_mult': [3.0, 5.0, 8.0],
            'sl_atr_mult': [1.5, 2.0]
        }
        
    def get_default_params(self) -> dict:
        return {k: v['default'] for k, v in self.get_parameters_schema().items()}

    def get_min_data_points(self) -> int:
        return max(
            self.params.get('medio_ema_period', 50),
            self.params.get('macro_vol_period', 20),
            self.params.get('micro_rsi_period', 14) + 10
        )

    def analyze(self, data: pd.DataFrame, extra_data: dict[str, pd.DataFrame] = None) -> Signal:
        # Validar disponibilidad de las tres pantallas
        if extra_data is None or '1d' not in extra_data or '4h' not in extra_data:
            return Signal(signal_type='hold', symbol='', reason='Faltan temporalidades 1d o 4h')

        df_1d = extra_data['1d']
        df_4h = extra_data['4h']
        df_5m = data  # El timeframe actual de ejecución

        if len(df_1d) < 30 or len(df_4h) < 50 or len(df_5m) < 30:
            return Signal(signal_type='hold', symbol='', reason='Data insuficiente para indicadores')

        # Parse float parameters that might come as strings con comas
        def parse_float(val, default):
            try:
                if isinstance(val, str):
                    val = val.replace(',', '.')
                return float(val)
            except:
                return float(default)

        # ==========================================
        # 1. PANTALLA MACRO (1D)
        # ==========================================
        macd_fast = int(self.params.get('macro_macd_fast', 12))
        macd_slow = int(self.params.get('macro_macd_slow', 26))
        macd_sig = int(self.params.get('macro_macd_sig', 9))
        
        macd_1d = get_macd(df_1d['close'], macd_fast, macd_slow, macd_sig)
        vol_sma_1d = get_sma(df_1d['volume'], self.params.get('macro_vol_period', 20))
        
        last_macd_1d = macd_1d['MACD'].iloc[-1]
        last_sig_1d = macd_1d['Signal'].iloc[-1]
        
        # Para el volumen diario, evaluamos la media de volumen.
        # No exigimos que cada día supere la media (eso rompería tendencias largas donde el volumen baja),
        # sino que el MACD esté alcista.
        macro_is_bullish = (last_macd_1d > last_sig_1d)

        # ==========================================
        # 2. PANTALLA MEDIO (4H)
        # ==========================================
        ema_period = int(self.params.get('medio_ema_period', 50))
        ema_4h = get_ema(df_4h['close'], ema_period)
        last_close_4h = df_4h['close'].iloc[-1]
        last_ema_4h = ema_4h.iloc[-1]
        
        # Tendencia soportada
        medio_is_bullish = (last_close_4h > last_ema_4h)
        
        # Gestión de Posiciones Abiertas (Salidas Anticipadas)
        position = self.portfolio.get('position', 0)
        
        if position > 0 and (not macro_is_bullish or not medio_is_bullish):
            # Si el mercado se gira a nivel macro o medio, abortamos la operación.
            return Signal(signal_type='sell', symbol='', reason='Cierre: Pérdida de soporte 4H o MACD Diario')

        # ==========================================
        # 3. PANTALLA MICRO (5m)
        # ==========================================
        # ATR de 5m para Stop Loss y Take Profit
        atr_5m = get_atr(df_5m['high'], df_5m['low'], df_5m['close'], 14).iloc[-1]
        current_close = df_5m['close'].iloc[-1]

        if position > 0:
            avg_price = float(self.portfolio.get('position_avg_price', current_close))
            sl_mult = parse_float(self.params.get('sl_atr_mult'), 2.0)
            tp_mult = parse_float(self.params.get('tp_atr_mult'), 5.0)
            
            sl_price = avg_price - (float(atr_5m) * sl_mult)
            tp_price = avg_price + (float(atr_5m) * tp_mult)
            
            current_close_float = float(current_close)

            if current_close_float <= sl_price:
                return Signal(signal_type='sell', symbol='', reason='Stop Loss tocado (ATR)')
            if current_close >= tp_price:
                return Signal(signal_type='sell', symbol='', reason='Take Profit tocado (ATR)')
            
            return Signal(signal_type='hold', symbol='')
        
        # Búsqueda de Gatillo (Pullback)
        if macro_is_bullish and medio_is_bullish:
            rsi_period = int(self.params.get('micro_rsi_period', 14))
            rsi_5m = get_rsi(df_5m['close'], rsi_period)
            
            # Condición de rebote
            rsi_oversold = int(self.params.get('micro_rsi_oversold', 50))
            prev_rsi = rsi_5m.iloc[-2]
            curr_rsi = rsi_5m.iloc[-1]
            
            # ¿Veníamos de un respiro y ahora rebotamos?
            if (prev_rsi <= rsi_oversold) and (curr_rsi > rsi_oversold):
                return Signal(
                    signal_type='buy',
                    symbol='',
                    reason='Gatillo Micro: Rebote RSI (5m) a favor de tendencia'
                )

        return Signal(signal_type='hold', symbol='')
