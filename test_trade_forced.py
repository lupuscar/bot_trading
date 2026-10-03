import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.live_trading.models import TradingBot
from apps.live_trading.tasks import _execute_paper_trade
from apps.strategies.base import Signal
from decimal import Decimal
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('paper_test')

try:
    bot = TradingBot.objects.get(name='Bot de Pruebas')
    print(f'Max open positions: {bot.max_open_positions}')
    print(f'Open positions count: {bot.paper_trades.filter(status="open").count()}')
    
    # Try forcing a buy signal
    print('Testing forced BUY signal...')
    signal = Signal(signal_type='buy', symbol=bot.symbol, price=Decimal('100.0'), reason='Test forced buy')
    class MockCandle:
        def __init__(self):
            self.close = 100.0
    
    from collections import namedtuple
    Candle = namedtuple('Candle', ['close'])
    candle = Candle(close=100.0)
    
    _execute_paper_trade(bot, signal, candle)
    print('Finished executing forced buy')
    print(f'Open positions count now: {bot.paper_trades.filter(status="open").count()}')

except Exception as e:
    logger.exception('Error during test')
