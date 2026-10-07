import logging
from celery import shared_task
from django.utils import timezone
from .models import OptimizationRun, OptimizationResult
from apps.strategies.registry import discover_strategies
from apps.backtesting.engine import BacktestEngine
from django.utils.module_loading import import_string
from decimal import Decimal
import itertools

logger = logging.getLogger(__name__)

class MockBacktestRun:
    def __init__(self, symbol, timeframe, start_date, end_date, trade_risk_pct=5.0):
        self.id = 'mock'
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = Decimal('10000.0')
        self.trade_risk_pct = Decimal(str(trade_risk_pct))
        self.commission_pct = Decimal('0.1')
        self.allow_pyramiding = False
        
        # Add strategy mock
        class MockStrategy:
            name = 'Optimizer Strategy'
        self.strategy = MockStrategy()
        self.strategy_params = {}
        self.error_message = ''
        
        # Results to be populated
        self.final_capital = None
        self.total_return_pct = None
        self.max_drawdown_pct = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.status = 'pending'
        self.results_data = {}
        
    def save(self, *args, **kwargs):
        # Do not save to DB
        pass

@shared_task(time_limit=3600, soft_time_limit=3500)
def run_optimization_task(run_id):
    try:
        opt_run = OptimizationRun.objects.get(id=run_id)
        opt_run.status = 'running'
        opt_run.save()
        
        strategies = discover_strategies() # list of tuples (path, name)
        timeframes = opt_run.selected_timeframes if opt_run.selected_timeframes else ['15m', '1h', '4h', '1d']
        
        # We don't want to run the AI strategy in backtests because it uses the API and takes forever.
        # Filter out the AI Agent strategy.
        safe_strategies = [s for s in strategies if 'AIAgent' not in s[0]]
        
        if opt_run.selected_strategies:
            safe_strategies = [s for s in safe_strategies if s[0] in opt_run.selected_strategies]

        logger.info(f"Starting optimization run {run_id} for {opt_run.symbol} over {len(safe_strategies)} strategies and {len(timeframes)} timeframes.")
        
        # 1. Pre-calcular el total de ejecuciones
        total_runs = 0
        strategy_combinations_map = {}
        for strategy_path, strategy_name in safe_strategies:
            StrategyClass = import_string(strategy_path)
            opt_params = getattr(StrategyClass, 'get_optimization_parameters', lambda: {})()
            if not opt_params:
                # Fallback if the strategy hasn't implemented it yet
                schema = getattr(StrategyClass, 'get_parameters_schema', lambda: {})()
                opt_params = {k: [v.get('default')] for k, v in schema.items()}
            param_keys = list(opt_params.keys())
            param_values = list(opt_params.values())
            combinations = [dict(zip(param_keys, v)) for v in itertools.product(*param_values)] if param_keys else [{}]
            strategy_combinations_map[strategy_path] = (StrategyClass, combinations)
            total_runs += len(combinations) * len(timeframes)

        completed_runs = 0

        # 2. Ejecutar las optimizaciones
        for strategy_path, strategy_name in safe_strategies:
            StrategyClass, combinations = strategy_combinations_map[strategy_path]

            for tf in timeframes:
                # --- PRELOAD DATA FOR THIS TIMEFRAME ---
                cached_df = None
                try:
                    mock_run_preload = MockBacktestRun(
                        symbol=opt_run.symbol,
                        timeframe=tf,
                        start_date=opt_run.start_date,
                        end_date=opt_run.end_date,
                        trade_risk_pct=opt_run.trade_risk_pct
                    )
                    preload_engine = BacktestEngine(mock_run_preload)
                    
                    # Force a large warmup to cover any parameter combination (e.g. SMA 200)
                    class MaxWarmupStrategy(StrategyClass):
                        def get_min_data_points(self): return 300
                        
                    preload_engine.set_strategy_class(MaxWarmupStrategy)
                    preload_engine.strategy_instance = MaxWarmupStrategy(name=strategy_name)
                    preload_engine.load_data()
                    cached_df = preload_engine.df
                    cached_extra_dfs = preload_engine.extra_dfs
                    logger.info(f"Preloaded {len(cached_df)} candles for {tf}.")
                except Exception as e:
                    logger.error(f"Failed to preload data for {strategy_name} on {tf}: {e}")
                    continue
                # ----------------------------------------
                
                for params in combinations:
                    # Crear un nombre descriptivo para los parámetros en el podio
                    params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                    display_name = f"{strategy_name} ({params_str})" if params_str else strategy_name
                    
                    # Mock a BacktestRun
                    mock_run = MockBacktestRun(
                        symbol=opt_run.symbol,
                        timeframe=tf,
                        start_date=opt_run.start_date,
                        end_date=opt_run.end_date,
                        trade_risk_pct=opt_run.trade_risk_pct
                    )
                    mock_run.strategy_params = params
                    
                    # Initialize Strategy con la combinación actual
                    strategy_instance = StrategyClass(name=strategy_name, params=params)
                    
                    # Run Engine
                    engine = BacktestEngine(mock_run)
                    engine.set_strategy_class(StrategyClass)
                    engine.strategy_instance = strategy_instance
                    if cached_df is not None:
                        engine.df = cached_df.copy()
                        engine.extra_dfs = {k: v.copy() for k, v in cached_extra_dfs.items()}
                    
                    try:
                        engine.run()
                        
                        if mock_run.status == 'completed':
                            OptimizationResult.objects.create(
                                run=opt_run,
                                strategy_name=display_name,
                                strategy_class=strategy_path,
                                timeframe=tf,
                                parameters=params,
                                total_return_pct=mock_run.total_return_pct,
                                max_drawdown_pct=mock_run.max_drawdown_pct,
                                total_trades=mock_run.total_trades,
                                winning_trades=mock_run.winning_trades,
                                losing_trades=mock_run.losing_trades
                            )
                    except Exception as e:
                        logger.error(f"Error optimizing {display_name} on {tf}: {e}")
                        
                    # Actualizar progreso
                    completed_runs += 1
                    if total_runs > 0:
                        opt_run.progress = int((completed_runs / total_runs) * 100)
                        opt_run.save(update_fields=['progress'])
                    
        opt_run.progress = 100
        opt_run.status = 'completed'
        opt_run.save()
        
    except Exception as e:
        logger.error(f"Optimization run failed: {e}")
        if 'opt_run' in locals():
            opt_run.status = 'failed'
            opt_run.save()
