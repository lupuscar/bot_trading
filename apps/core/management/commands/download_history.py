import logging
from datetime import datetime
import pandas as pd
from django.core.management.base import BaseCommand
from apps.connectors.crypto.binance import BinanceConnector
from apps.core.models import Candle

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Descarga datos históricos OHLCV y los almacena en la base de datos.'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, default='BTC/USDT', help='Par de trading (ej: BTC/USDT)')
        parser.add_argument('--timeframe', type=str, default='1h', help='Timeframe (ej: 1h, 1d)')
        parser.add_argument('--start', type=str, required=True, help='Fecha de inicio YYYY-MM-DD')
        parser.add_argument('--end', type=str, help='Fecha de fin YYYY-MM-DD (por defecto hoy)')

    def handle(self, *args, **options):
        symbol = options['symbol']
        timeframe = options['timeframe']
        
        try:
            start_date = datetime.strptime(options['start'], '%Y-%m-%d')
        except ValueError:
            self.stderr.write(self.style.ERROR("Formato de fecha de inicio inválido. Usa YYYY-MM-DD"))
            return

        if options['end']:
            try:
                end_date = datetime.strptime(options['end'], '%Y-%m-%d')
            except ValueError:
                self.stderr.write(self.style.ERROR("Formato de fecha de fin inválido. Usa YYYY-MM-DD"))
                return
        else:
            end_date = datetime.now()

        self.stdout.write(self.style.SUCCESS(f"Descargando datos para {symbol} ({timeframe}) desde {start_date.date()} hasta {end_date.date()}..."))

        # Inicializar conector (sin keys, solo API pública)
        connector = BinanceConnector(name='binance_public', market_type='crypto', config={'testnet': False})
        
        if not connector.connect():
            self.stderr.write(self.style.ERROR("Error al conectar con Binance."))
            return

        try:
            df = connector.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start_date,
                end=end_date
            )
            
            if df.empty:
                self.stdout.write(self.style.WARNING("No se obtuvieron datos."))
                return

            self.stdout.write(f"Obtenidas {len(df)} velas. Guardando en la base de datos...")

            # Convertir DataFrame a objetos Candle
            candles_to_create = []
            for _, row in df.iterrows():
                candles_to_create.append(Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=row['timestamp'].to_pydatetime(),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                ))

            # Bulk create ignorando conflictos (por si ya existen velas)
            Candle.objects.bulk_create(candles_to_create, ignore_conflicts=True)

            self.stdout.write(self.style.SUCCESS(f"Proceso completado exitosamente. Guardadas {len(candles_to_create)} velas."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error durante la descarga o guardado: {str(e)}"))
        finally:
            connector.disconnect()
