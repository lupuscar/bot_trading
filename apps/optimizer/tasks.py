import logging
from celery import shared_task
from django.utils import timezone
from .models import OptimizationRun, OptimizationResult
from apps.strategies.registry import discover_strategies
from apps.backtesting.engine import BacktestEngine
from django.utils.module_loading import import_string
from decimal import Decimal

logger = logging.getLogger(__name__)

class MockBacktestRun:
    def __init__(self, symbol, timeframe, start_date, end_date):
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = Decimal('10000.0')
        self.trade_risk_pct = Decimal('10.0')
        self.commission_pct = Decimal('0.1')
        self.allow_pyramiding = False
        
        # Results to be populated
        self.final_capital = None
        self.total_return_pct = None
        self.max_drawdown_pct = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.status = 'pending'
        self.results_data = {}
        
    def save(self):
        # Do not save to DB
        pass

@shared_task
def run_optimization_task(run_id):
    try:
        opt_run = OptimizationRun.objects.get(id=run_id)
        opt_run.status = 'running'
        opt_run.save()
        
        strategies = discover_strategies() # list of tuples (path, name)
        timeframes = ['15m', '1h', '4h', '1d']
        
        # We don't want to run the AI strategy in backtests because it uses the API and takes forever.
        # Filter out the AI Agent strategy.
        safe_strategies = [s for s in strategies if 'AIAgent' not in s[0]]

        logger.info(f"Starting optimization run {run_id} for {opt_run.symbol} over {len(safe_strategies)} strategies and {len(timeframes)} timeframes.")

        for strategy_path, strategy_name in safe_strategies:
            StrategyClass = import_string(strategy_path)
            
            for tf in timeframes:
                logger.info(f"Optimizing: {strategy_name} on {tf}")
                
                # Mock a BacktestRun
                mock_run = MockBacktestRun(
                    symbol=opt_run.symbol,
                    timeframe=tf,
                    start_date=opt_run.start_date,
                    end_date=opt_run.end_date
                )
                
                # Initialize Strategy
                # Using default parameters for the optimizer
                strategy_instance = StrategyClass(name=strategy_name)
                
                # Run Engine
                engine = BacktestEngine(mock_run)
                engine.set_strategy_class(StrategyClass)
                engine.strategy_instance = strategy_instance
                
                try:
                    engine.run()
                    
                    if mock_run.status == 'completed':
                        OptimizationResult.objects.create(
                            run=opt_run,
                            strategy_name=strategy_name,
                            strategy_class=strategy_path,
                            timeframe=tf,
                            total_return_pct=mock_run.total_return_pct,
                            max_drawdown_pct=mock_run.max_drawdown_pct,
                            total_trades=mock_run.total_trades,
                            winning_trades=mock_run.winning_trades,
                            losing_trades=mock_run.losing_trades
                        )
                except Exception as e:
                    logger.error(f"Error optimizing {strategy_name} on {tf}: {e}")
                    
        opt_run.status = 'completed'
        opt_run.save()
        
    except Exception as e:
        logger.error(f"Optimization run failed: {e}")
        if 'opt_run' in locals():
            opt_run.status = 'failed'
            opt_run.save()
