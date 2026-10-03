import logging
from decimal import Decimal
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any

from django.utils import timezone
from apps.core.models import Candle
from apps.strategies.base import BaseStrategy
from apps.backtesting.models import BacktestRun

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Motor de backtesting iterativo.
    Simula la ejecución de una estrategia a través de datos históricos.
    """

    def __init__(self, run_id: int):
        """
        Inicializa el motor usando un ID de ejecución de BacktestRun
        """
        self.run_obj = BacktestRun.objects.get(id=run_id)
        self.strategy_cls = None
        self.strategy_instance = None
        self.df = None
        
        # Portfolio state
        self.initial_capital = self.run_obj.initial_capital
        self.cash = self.initial_capital
        self.position = Decimal('0.0')  # Cantidad de activo
        self.position_avg_price = Decimal('0.0')
        self.trades = []  # Registro de operaciones completadas
        self.equity_curve = []  # Evolución del capital
        
        self.commission_rate = Decimal('0.001')  # 0.1% de comisión simulada

    def set_strategy_class(self, strategy_cls):
        """Asignar la clase de estrategia a instanciar"""
        self.strategy_cls = strategy_cls
        self.strategy_instance = strategy_cls(
            name=self.run_obj.strategy.name,
            params=self.run_obj.strategy_params
        )

    def load_data(self):
        """Cargar datos históricos de la BD en un DataFrame. Si faltan, los descarga."""
        # 1. Calcular fecha de inicio extendida para "calentar" indicadores (warmup)
        # Asumimos que 200 velas previas son suficientes para casi cualquier indicador estándar
        tf_minutes = {'m': 1, 'h': 60, 'd': 1440, 'w': 10080}
        unit = self.run_obj.timeframe[-1]
        try:
            val = int(self.run_obj.timeframe[:-1])
            mins = val * tf_minutes.get(unit, 60)
        except:
            mins = 60
        warmup_delta = timezone.timedelta(minutes=mins * 250)
        fetch_start = self.run_obj.start_date - warmup_delta

        # Comprobar si tenemos datos en la BD
        candles = Candle.objects.filter(
            symbol=self.run_obj.symbol,
            timeframe=self.run_obj.timeframe,
            timestamp__gte=fetch_start,
            timestamp__lte=self.run_obj.end_date
        ).order_by('timestamp')
        
        # Validación de cobertura (simplificada: miramos primer y último registro)
        needs_download = False
        if not candles.exists():
            needs_download = True
        else:
            first_candle = candles.first().timestamp
            last_candle = candles.last().timestamp
            # Si el gap al inicio o al final es mayor a un margen razonable, descargamos
            if first_candle > fetch_start + timezone.timedelta(days=1) or \
               last_candle < self.run_obj.end_date - timezone.timedelta(days=1):
                needs_download = True

        if needs_download:
            logger.info(f"Descargando datos históricos faltantes para {self.run_obj.symbol} (incluyendo warmup)...")
            self._download_historical_data(fetch_start)
            # Volver a consultar
            candles = Candle.objects.filter(
                symbol=self.run_obj.symbol,
                timeframe=self.run_obj.timeframe,
                timestamp__gte=fetch_start,
                timestamp__lte=self.run_obj.end_date
            ).order_by('timestamp')

        data = []
        for c in candles:
            data.append({
                'timestamp': c.timestamp,
                'open': float(c.open),
                'high': float(c.high),
                'low': float(c.low),
                'close': float(c.close),
                'volume': float(c.volume),
                'symbol': c.symbol
            })
            
        self.df = pd.DataFrame(data)
        if self.df.empty:
            raise ValueError("No se pudieron obtener datos para las fechas seleccionadas.")
            
        self.run_obj.status = 'running'
        self.run_obj.save(update_fields=['status'])

    def _download_historical_data(self, fetch_start):
        """Descarga datos desde Binance usando el conector público y los guarda en BD"""
        from apps.connectors.crypto.binance import BinanceConnector
        from apps.core.models import Candle
        
        connector = BinanceConnector(
            name='backtest_downloader',
            market_type='crypto',
            config={'testnet': False}
        )
        if not connector.connect():
            logger.error("No se pudo conectar a Binance para descargar histórico.")
            return

        try:
            # Pedimos todo el rango extendido
            df = connector.get_historical_data(
                symbol=self.run_obj.symbol,
                timeframe=self.run_obj.timeframe,
                start=fetch_start,
                end=self.run_obj.end_date,
                limit=2000
            )
            
            if df.empty:
                logger.warning(f"Binance devolvió 0 velas para {self.run_obj.symbol}")
                return

            # Bulk create ignoring conflicts
            candles_to_create = []
            for _, row in df.iterrows():
                candles_to_create.append(Candle(
                    symbol=self.run_obj.symbol,
                    timeframe=self.run_obj.timeframe,
                    timestamp=timezone.make_aware(row['timestamp'].to_pydatetime()) if timezone.is_naive(row['timestamp'].to_pydatetime()) else row['timestamp'].to_pydatetime(),
                    open=Decimal(str(row['open'])),
                    high=Decimal(str(row['high'])),
                    low=Decimal(str(row['low'])),
                    close=Decimal(str(row['close'])),
                    volume=Decimal(str(row['volume']))
                ))
            
            # Usar ignore_conflicts para no fallar si ya existen algunas velas en el rango
            Candle.objects.bulk_create(candles_to_create, ignore_conflicts=True)
            logger.info(f"Guardadas {len(candles_to_create)} velas en BD para {self.run_obj.symbol}.")
            
        except Exception as e:
            logger.error(f"Error descargando datos: {e}")
        finally:
            connector.disconnect()

    def run(self):
        """Ejecutar el loop de simulación"""
        if self.df is None or self.df.empty:
            self.load_data()
            
        if not self.strategy_instance:
            raise ValueError("Estrategia no definida.")

        min_rows = self.strategy_instance.get_min_data_points()
        if len(self.df) < min_rows:
            raise ValueError(f"Datos insuficientes. Se requieren al menos {min_rows} velas.")

        logger.info(f"Iniciando backtest para {self.run_obj.symbol} con {len(self.df)} velas.")

        # Iterar simulando el paso del tiempo
        for i in range(min_rows, len(self.df)):
            current_slice = self.df.iloc[:i+1].copy()
            current_row = current_slice.iloc[-1]
            current_price = Decimal(str(current_row['close']))
            current_time = current_row['timestamp']
            
            # Solo analizamos y operamos si estamos dentro de la ventana real de backtest
            # Las velas anteriores (warmup) solo sirven para que 'current_slice' tenga histórico
            if current_time >= self.run_obj.start_date:
                # 1. Obtener Señal
                signal = self.strategy_instance.safe_analyze(current_slice)
                
                # 2. Ejecutar Señal
                self._process_signal(signal, current_price, current_time)
                
                # 3. Registrar Equity
                current_equity = self.cash + (self.position * current_price)
                self.equity_curve.append({
                    'timestamp': current_time.isoformat(),
                    'equity': float(current_equity),
                    'close': float(current_price)
                })

        # 4. Finalizar y cerrar posiciones abiertas al último precio
        last_price = Decimal(str(self.df.iloc[-1]['close']))
        last_time = self.df.iloc[-1]['timestamp']
        if self.position > 0:
            self._execute_trade('sell', last_price, self.position, last_time, 'Cierre de fin de backtest')

        self._calculate_results()

    def _process_signal(self, signal, current_price: Decimal, current_time):
        if not signal.is_actionable:
            return

        if signal.signal_type == 'buy' and self.cash > 0:
            if self.position > 0 and not self.run_obj.allow_pyramiding:
                return  # No comprar de nuevo si ya hay posición y pyramiding está desactivado

            # Calculamos cuánto capital arriesgar basado en el porcentaje configurado
            risk_multiplier = Decimal(str(self.run_obj.trade_risk_pct)) / Decimal('100.0')
            cash_to_risk = self.cash * risk_multiplier

            # Compramos reservando dinero para la comisión
            usable_cash = cash_to_risk / (Decimal('1') + self.commission_rate)
            amount_to_buy = usable_cash / current_price
            
            # Coste y comisión
            cost = amount_to_buy * current_price
            commission = cost * self.commission_rate
            
            # Comprar
            self._execute_trade('buy', current_price, amount_to_buy, current_time, signal.reason, commission)
            
        elif signal.signal_type == 'sell' and self.position > 0:
            # Vendemos todo
            amount_to_sell = self.position
            value = amount_to_sell * current_price
            commission = value * self.commission_rate
            
            # Vender
            self._execute_trade('sell', current_price, amount_to_sell, current_time, signal.reason, commission)

    def _execute_trade(self, side: str, price: Decimal, amount: Decimal, timestamp, reason: str, commission: Decimal = Decimal('0')):
        if side == 'buy':
            cost = (amount * price) + commission
            if self.cash >= cost:
                self.cash -= cost
                self.position += amount
                self.position_avg_price = price
                
                self.trades.append({
                    'side': 'buy',
                    'price': float(price),
                    'amount': float(amount),
                    'commission': float(commission),
                    'timestamp': timestamp.isoformat(),
                    'reason': reason
                })
        elif side == 'sell':
            revenue = (amount * price) - commission
            if self.position >= amount:
                # Calcular PnL de este trade (comprado a avg_price, vendido a price)
                cost_basis = amount * self.position_avg_price
                pnl = revenue - cost_basis
                pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
                
                self.cash += revenue
                self.position -= amount
                
                if self.position == 0:
                    self.position_avg_price = Decimal('0')

                self.trades.append({
                    'side': 'sell',
                    'price': float(price),
                    'amount': float(amount),
                    'commission': float(commission),
                    'timestamp': timestamp.isoformat(),
                    'reason': reason,
                    'pnl': float(pnl),
                    'pnl_pct': float(pnl_pct)
                })

    def _calculate_results(self):
        """Calcular métricas finales y guardar en BD"""
        try:
            final_capital = self.cash
            total_return_pct = ((final_capital - self.initial_capital) / self.initial_capital) * 100
            
            # Extraer trades de venta (que tienen el PnL cerrado)
            sell_trades = [t for t in self.trades if t['side'] == 'sell']
            total_trades = len(sell_trades)
            winning_trades = sum(1 for t in sell_trades if t.get('pnl', 0) > 0)
            losing_trades = total_trades - winning_trades
            
            # Calcular Drawdown
            equity_values = [e['equity'] for e in self.equity_curve]
            max_drawdown = 0
            if equity_values:
                peak = equity_values[0]
                for eq in equity_values:
                    if eq > peak:
                        peak = eq
                    dd = (peak - eq) / peak * 100 if peak > 0 else 0
                    if dd > max_drawdown:
                        max_drawdown = dd

            # Guardar en modelo
            self.run_obj.final_capital = final_capital
            self.run_obj.total_return_pct = total_return_pct
            self.run_obj.max_drawdown_pct = max_drawdown
            self.run_obj.total_trades = total_trades
            self.run_obj.winning_trades = winning_trades
            self.run_obj.losing_trades = losing_trades
            self.run_obj.status = 'completed'
            self.run_obj.results_data = {
                'equity_curve': self.equity_curve,
                'trades': self.trades
            }
            self.run_obj.save()
            logger.info(f"Backtest {self.run_obj.id} completado. Retorno: {total_return_pct:.2f}%")
            
        except Exception as e:
            self.run_obj.status = 'failed'
            self.run_obj.error_message = str(e)
            self.run_obj.save()
            logger.error(f"Error calculando resultados: {e}")
