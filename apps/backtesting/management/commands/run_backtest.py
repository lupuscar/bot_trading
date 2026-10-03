import logging
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.timezone import make_aware

from apps.backtesting.models import BacktestRun
from apps.backtesting.engine import BacktestEngine
from apps.strategies.models import Strategy
from apps.strategies.implementations.ma_crossover import MACrossoverStrategy

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Ejecuta un backtest de prueba con la estrategia MA Crossover.'

    def handle(self, *args, **options):
        # 1. Obtener o crear superusuario
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stderr.write("No hay superusuario. Crea uno primero.")
            return

        # 2. Registrar la estrategia en la BD si no existe
        strategy_obj, created = Strategy.objects.get_or_create(
            user=user,
            name='MA Crossover',
            defaults={
                'version': '1.0',
                'description': 'Estrategia de cruce de medias móviles',
                'strategy_class': 'apps.strategies.implementations.ma_crossover.MACrossoverStrategy'
            }
        )

        # 3. Crear el BacktestRun
        start_date = make_aware(datetime(2026, 1, 1))
        end_date = make_aware(datetime(2026, 2, 1))
        
        run_obj = BacktestRun.objects.create(
            user=user,
            strategy=strategy_obj,
            symbol='BTC/USDT',
            timeframe='1d',
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal('10000.00'),
            strategy_params={'fast_period': 5, 'slow_period': 15}  # Valores rápidos para probar con pocas velas
        )

        self.stdout.write(f"BacktestRun creado con ID {run_obj.id}")

        # 4. Iniciar Engine
        engine = BacktestEngine(run_id=run_obj.id)
        engine.set_strategy_class(MACrossoverStrategy)
        
        self.stdout.write("Ejecutando backtest...")
        try:
            engine.run()
            
            # Recargar y mostrar resultados
            run_obj.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(f"Backtest finalizado!"))
            self.stdout.write(f"Capital Inicial: {run_obj.initial_capital}")
            self.stdout.write(f"Capital Final: {run_obj.final_capital}")
            self.stdout.write(f"Retorno: {run_obj.total_return_pct:.2f}%")
            self.stdout.write(f"Trades Totales: {run_obj.total_trades} (G: {run_obj.winning_trades}, P: {run_obj.losing_trades})")
            self.stdout.write(f"Max Drawdown: {run_obj.max_drawdown_pct:.2f}%")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error en backtest: {e}"))
