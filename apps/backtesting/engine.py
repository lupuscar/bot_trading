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

    def __init__(self, run_id_or_obj):
        """
        Inicializa el motor usando un ID de ejecución de BacktestRun o un objeto simulado.
        """
        if isinstance(run_id_or_obj, (int, str)):
            self.run_obj = BacktestRun.objects.get(id=int(run_id_or_obj))
        else:
            self.run_obj = run_id_or_obj
        self.strategy_cls = None
        self.strategy_instance = None
        self.df = None
        self.extra_dfs = {}
        
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

    def _get_warmup_start(self, timeframe: str):
        """Calcula el fetch_start necesario para este timeframe (250 velas previas)"""
        tf_minutes = {'m': 1, 'h': 60, 'd': 1440, 'w': 10080}
        unit = timeframe[-1]
        try:
            val = int(timeframe[:-1])
            mins = val * tf_minutes.get(unit, 60)
        except:
            mins = 60
        warmup_delta = timezone.timedelta(minutes=mins * 250)
        return self.run_obj.start_date - warmup_delta

    def _ensure_data_in_db(self, timeframe: str):
        """Asegura que los datos existan en la BD para el rango y timeframe dados."""
        from apps.core.models import Candle
        fetch_start = self._get_warmup_start(timeframe)

        candles = Candle.objects.filter(
            symbol=self.run_obj.symbol,
            timeframe=timeframe,
            timestamp__gte=fetch_start,
            timestamp__lte=self.run_obj.end_date
        ).order_by('timestamp')
        
        needs_download = False
        if not candles.exists():
            needs_download = True
        else:
            first_candle = candles.first().timestamp
            last_candle = candles.last().timestamp
            if first_candle > fetch_start + timezone.timedelta(days=1) or \
               last_candle < self.run_obj.end_date - timezone.timedelta(days=1):
                needs_download = True

        if needs_download:
            logger.info(f"Descargando histórico para {self.run_obj.symbol} ({timeframe})...")
            self._download_historical_data(timeframe, fetch_start)
            
        return Candle.objects.filter(
            symbol=self.run_obj.symbol,
            timeframe=timeframe,
            timestamp__gte=fetch_start,
            timestamp__lte=self.run_obj.end_date
        ).order_by('timestamp')

    def load_data(self):
        """Cargar datos históricos de la BD (principal y extras). Si faltan, los descarga."""
        # 1. Cargar Timeframe Principal
        candles = self._ensure_data_in_db(self.run_obj.timeframe)
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
            raise ValueError("No se pudieron obtener datos para el timeframe principal.")

        # 2. Cargar Timeframes Extra
        self.extra_dfs = {}
        if self.strategy_instance:
            extra_tfs = getattr(self.strategy_instance, 'get_extra_timeframes', lambda: [])()
            for tf in extra_tfs:
                tf_candles = self._ensure_data_in_db(tf)
                tf_data = []
                for c in tf_candles:
                    tf_data.append({
                        'timestamp': c.timestamp,
                        'open': float(c.open),
                        'high': float(c.high),
                        'low': float(c.low),
                        'close': float(c.close),
                        'volume': float(c.volume),
                        'symbol': c.symbol
                    })
                df_extra = pd.DataFrame(tf_data)
                if not df_extra.empty:
                    # Índice por timestamp para búsqueda rápida O(log N)
                    df_extra.set_index('timestamp', drop=False, inplace=True)
                self.extra_dfs[tf] = df_extra
            
        self.run_obj.status = 'running'
        self.run_obj.save(update_fields=['status'])

    def _download_historical_data(self, timeframe: str, fetch_start):
        """Descarga datos desde Binance usando el conector público y los guarda en BD"""
        from apps.connectors.crypto.binance import BinanceConnector
        from apps.core.models import Candle
        
        connector = BinanceConnector(
            name='backtest_downloader',
            market_type='crypto',
            config={'testnet': False}
        )
        if not connector.connect():
            logger.error("No se pudo conectar a Binance.")
            return

        try:
            df = connector.get_historical_data(
                symbol=self.run_obj.symbol,
                timeframe=timeframe,
                start=fetch_start,
                end=self.run_obj.end_date,
                limit=2000
            )
            if df.empty:
                logger.warning(f"Binance devolvió 0 velas ({timeframe})")
                return

            candles_to_create = []
            for _, row in df.iterrows():
                candles_to_create.append(Candle(
                    symbol=self.run_obj.symbol,
                    timeframe=timeframe,
                    timestamp=timezone.make_aware(row['timestamp'].to_pydatetime()) if timezone.is_naive(row['timestamp'].to_pydatetime()) else row['timestamp'].to_pydatetime(),
                    open=Decimal(str(row['open'])),
                    high=Decimal(str(row['high'])),
                    low=Decimal(str(row['low'])),
                    close=Decimal(str(row['close'])),
                    volume=Decimal(str(row['volume']))
                ))
            
            Candle.objects.bulk_create(candles_to_create, ignore_conflicts=True)
            logger.info(f"Guardadas {len(candles_to_create)} velas ({timeframe}) en BD.")
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
            current_slice = self.df.iloc[:i+1]
            current_row = current_slice.iloc[-1]
            current_price = Decimal(str(current_row['close']))
            current_time = current_row['timestamp']
            
            # Solo analizamos y operamos si estamos dentro de la ventana real de backtest
            # Las velas anteriores (warmup) solo sirven para que 'current_slice' tenga histórico
            if current_time >= self.run_obj.start_date:
                # Slicing de extra timeframes (cortamos hasta el current_time)
                # Al estar el index seteado a timestamp, .loc[:current_time] es muy rápido
                sliced_extra_dfs = {}
                for tf, df_ext in self.extra_dfs.items():
                    sliced_extra_dfs[tf] = df_ext.loc[:current_time]
                
                # Actualizar el portfolio de la estrategia
                self.strategy_instance.portfolio = {
                    'position': float(self.position),
                    'position_avg_price': float(self.position_avg_price),
                    'cash': float(self.cash)
                }
                
                # 1. Obtener Señal
                signal = self.strategy_instance.safe_analyze(current_slice, extra_data=sliced_extra_dfs)
                
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
            self._execute_trade('sell', last_price, self.position, last_time, 'Cierre de fin de backtest (Largo)')
        elif self.position < 0:
            self._execute_trade('cover', last_price, abs(self.position), last_time, 'Cierre de fin de backtest (Corto)')

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
            
            self._execute_trade('sell', current_price, amount_to_sell, current_time, signal.reason, commission)
            
        elif signal.signal_type == 'short' and self.cash > 0:
            if self.position != 0 and not self.run_obj.allow_pyramiding:
                return
                
            risk_multiplier = Decimal(str(self.run_obj.trade_risk_pct)) / Decimal('100.0')
            cash_to_risk = self.cash * risk_multiplier
            
            usable_cash = cash_to_risk / (Decimal('1') + self.commission_rate)
            amount_to_short = usable_cash / current_price
            
            value = amount_to_short * current_price
            commission = value * self.commission_rate
            
            self._execute_trade('short', current_price, amount_to_short, current_time, signal.reason, commission)
            
        elif signal.signal_type == 'cover' and self.position < 0:
            amount_to_cover = abs(self.position)
            cost = amount_to_cover * current_price
            commission = cost * self.commission_rate
            
            self._execute_trade('cover', current_price, amount_to_cover, current_time, signal.reason, commission)

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
        elif side == 'short':
            revenue = (amount * price) - commission
            self.cash += revenue
            self.position -= amount
            self.position_avg_price = price
            
            self.trades.append({
                'side': 'short',
                'price': float(price),
                'amount': float(amount),
                'commission': float(commission),
                'timestamp': timestamp.isoformat(),
                'reason': reason
            })
        elif side == 'cover':
            cost = (amount * price) + commission
            # En un short, profit = precio_entrada - precio_salida
            # revenue inicial = amount * avg_price
            revenue_initial = amount * self.position_avg_price
            pnl = revenue_initial - cost
            pnl_pct = (pnl / revenue_initial) * 100 if revenue_initial > 0 else 0
            
            self.cash -= cost
            self.position += amount
            
            if self.position == 0:
                self.position_avg_price = Decimal('0')
                
            self.trades.append({
                'side': 'cover',
                'price': float(price),
                'amount': float(amount),
                'commission': float(commission),
                'timestamp': timestamp.isoformat(),
                'reason': reason,
                'pnl': float(pnl),
                'pnl_pct': float(pnl_pct)
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
            
            # Extraer trades cerrados (sell para long, cover para short)
            closed_trades = [t for t in self.trades if t['side'] in ('sell', 'cover')]
            total_trades = len(closed_trades)
            winning_trades = sum(1 for t in closed_trades if t.get('pnl', 0) > 0)
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
