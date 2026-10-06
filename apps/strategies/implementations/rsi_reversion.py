import pandas as pd
from apps.strategies.base import BaseStrategy, Signal

class RSIReversionStrategy(BaseStrategy):
    """
    Estrategia Clásica de Reversión a la Media usando RSI.
    - Entra en LARGO (Long) cuando el RSI cruza por debajo del umbral de sobreventa (ej. 30).
    - Entra en CORTO (Short) cuando el RSI cruza por encima del umbral de sobrecompra (ej. 70).
    - Cierra la posición cuando el RSI vuelve a la zona neutral (ej. 50).
    """
    
    DISPLAY_NAME = 'RSI Mean Reversion (Long & Short)'

    @classmethod
    def get_optimization_parameters(cls) -> dict[str, list]:
        """Devuelve los rangos de parámetros para el Optimizador."""
        return {
            'rsi_period': [10, 14, 21],
            'oversold_level': [25, 30, 35],
            'overbought_level': [65, 70, 75],
            'neutral_level': [50]
        }
        
    def get_default_params(self) -> dict:
        return {
            'rsi_period': 14,
            'oversold_level': 30,
            'overbought_level': 70,
            'neutral_level': 50
        }

    def get_min_data_points(self) -> int:
        return self.params.get('rsi_period', 14) + 5

    def analyze(self, data: pd.DataFrame) -> Signal:
        period = self.params.get('rsi_period', 14)
        oversold = self.params.get('oversold_level', 30)
        overbought = self.params.get('overbought_level', 70)
        neutral = self.params.get('neutral_level', 50)
        
        # Calcular RSI manualmente con pandas
        delta = data['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=period - 1, adjust=False).mean()
        ema_down = down.ewm(com=period - 1, adjust=False).mean()
        rs = ema_up / ema_down
        data['RSI'] = 100 - (100 / (1 + rs))
        
        rsi = data['RSI']
        
        if rsi is None or len(rsi) < 2 or pd.isna(rsi.iloc[-1]):
            return Signal(signal_type='hold', symbol='')
            
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        
        # Lógica Long
        if prev_rsi >= oversold and current_rsi < oversold:
            return Signal(
                signal_type='buy',
                symbol='',
                reason=f"RSI {current_rsi:.1f} cruzó por debajo de Sobreventa ({oversold})"
            )
            
        # Lógica Short
        if prev_rsi <= overbought and current_rsi > overbought:
            return Signal(
                signal_type='short',
                symbol='',
                reason=f"RSI {current_rsi:.1f} cruzó por encima de Sobrecompra ({overbought})"
            )
            
        # Cierre de posiciones al volver a la neutralidad
        if prev_rsi < neutral and current_rsi >= neutral:
            # Cruzó hacia arriba la línea neutral, cerramos largos
            return Signal(
                signal_type='sell',
                symbol='',
                reason=f"RSI volvió a la neutralidad ({neutral})"
            )
            
        if prev_rsi > neutral and current_rsi <= neutral:
            # Cruzó hacia abajo la línea neutral, cubrimos cortos
            return Signal(
                signal_type='cover',
                symbol='',
                reason=f"RSI volvió a la neutralidad ({neutral})"
            )

        return Signal(signal_type='hold', symbol='')
