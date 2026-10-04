import logging
from decimal import Decimal
import pandas as pd
from datetime import datetime

from celery import shared_task
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.live_trading.models import TradingBot, TradeRecord, BotLog
from apps.paper_trading.models import PaperAccount, PaperTrade
from apps.core.models import TradingMode, OrderSide

logger = logging.getLogger(__name__)


def _log(bot, level, msg):
    logger_method = getattr(logger, level if level != 'success' else 'info')
    logger_method(f"Bot {bot.name}: {msg}")
    BotLog.objects.create(bot=bot, level=level, message=msg)

@shared_task
def process_trading_bots():
    """
    Tarea programada (Celery Beat) que se ejecuta cada N minutos.
    Busca bots activos y procesa su lógica de trading.
    """
    bots = TradingBot.objects.filter(is_active=True, status='running')
    if not bots.exists():
        logger.info("No hay bots activos ejecutándose.")
        return

    logger.info(f"Procesando {bots.count()} bots activos...")

    for bot in bots:
        try:
            _process_single_bot(bot)
            bot.last_run_at = timezone.now()
            bot.save(update_fields=['last_run_at', 'last_signal'])
        except Exception as e:
            logger.error(f"Error procesando bot {bot.name}: {e}")


def _process_single_bot(bot: TradingBot):
    """Procesar la lógica individual de un bot."""
    
    # 1. Obtener credenciales / conector
    # En un entorno real instanciaríamos según bot.exchange_connection.exchange_id
    # Aquí simplificamos asumiendo que es Binance
    from apps.connectors.crypto.binance import BinanceConnector
    
    conn_model = bot.exchange_connection
    connector = BinanceConnector(
        name=conn_model.name,
        market_type='crypto',
        config={
            'api_key': conn_model.api_key,
            'api_secret': conn_model.api_secret,
            'testnet': conn_model.is_testnet
        }
    )
    
    if not connector.connect():
        _log(bot, 'error', f"No se pudo conectar a {conn_model.name}")
        raise ConnectionError(f"No se pudo conectar a {conn_model.name}")

    try:
        # 2. Obtener datos históricos recientes
        # (Idealmente traeríamos esto de la BD si tenemos otro task guardando velas,
        # pero aquí lo traemos directo del exchange para tener la última vela fresca)
        strategy_class = import_string(bot.strategy.strategy_class)
        strategy_instance = strategy_class(name=bot.strategy.name, params=bot.strategy.parameters)
        
        limit = strategy_instance.get_min_data_points() + 10
        # Para operar en vivo o paper trading necesitamos los datos más recientes.
        # Si no pasamos start_date, CCXT nos traerá las últimas 'limit' velas actuales.
        df = connector.get_historical_data(
            symbol=bot.symbol,
            timeframe=bot.timeframe,
            start=None,
            limit=limit
        )

        if len(df) < strategy_instance.get_min_data_points():
            _log(bot, 'warning', f"Datos insuficientes para operar ({len(df)} velas)")
            return

        # 3. Analizar y obtener señal
        signal = strategy_instance.safe_analyze(df)
        
        # Guardamos la última señal generada
        bot.last_signal = {
            'type': signal.signal_type,
            'timestamp': signal.timestamp.isoformat(),
            'price': float(signal.price) if signal.price else None,
            'reason': signal.reason
        }

        if not signal.is_actionable:
            _log(bot, 'info', f"Señal {signal.signal_type.upper()}: {signal.reason}")
            return

        _log(bot, 'info', f"Señal {signal.signal_type.upper()} detectada: {signal.reason}")

        # 4. Ejecutar (Paper o Live)
        if bot.mode == TradingMode.PAPER:
            _execute_paper_trade(bot, signal, df.iloc[-1])
        elif bot.mode == TradingMode.LIVE:
            _execute_live_trade(bot, signal, connector)

    finally:
        connector.disconnect()


def _execute_paper_trade(bot: TradingBot, signal, last_candle):
    """Ejecuta una operación en modo simulación (Paper Trading)."""
    account, _ = PaperAccount.objects.get_or_create(
        bot=bot,
        defaults={
            'user': bot.user,
            'name': f'Cartera de {bot.name}',
            'initial_balance': Decimal('10000.00'),
            'current_balance': Decimal('10000.00'),
        }
    )
    
    current_price = Decimal(str(last_candle['close']))
    commission_rate = Decimal('0.001') # 0.1% comisión simulada
    
    open_positions = PaperTrade.objects.filter(
        account=account, 
        symbol=bot.symbol, 
        status='open',
        side='buy'
    )
    
    if signal.signal_type == 'buy':
        if open_positions.count() >= bot.max_open_positions:
            _log(bot, 'warning', f"Límite de posiciones abiertas alcanzado ({bot.max_open_positions}).")
            return
            
        risk_multiplier = Decimal(str(bot.risk_per_trade_pct)) / Decimal('100.0')
        cash_to_risk = account.current_balance * risk_multiplier
        usable_cash = cash_to_risk / (Decimal('1') + commission_rate)
        trade_amount = usable_cash / current_price
        
        cost = trade_amount * current_price
        commission = cost * commission_rate
        total_cost = cost + commission
        
        if account.current_balance >= total_cost:
            account.current_balance -= total_cost
            account.save(update_fields=['current_balance', 'updated_at'])
            
            PaperTrade.objects.create(
                account=account,
                strategy=bot.strategy,
                symbol=bot.symbol,
                side='buy',
                order_type='market',
                amount=trade_amount,
                entry_price=current_price,
                status='open'
            )
            _log(bot, 'success', f"Operación simulada: COMPRA de {trade_amount:.6f} {bot.symbol} a ${current_price:.2f}")
        else:
            _log(bot, 'warning', f"Saldo insuficiente para comprar. Necesario: ${total_cost:.2f}, Disp: ${account.current_balance:.2f}")

    elif signal.signal_type == 'sell':
        for pos in open_positions:
            revenue = pos.amount * current_price
            commission = revenue * commission_rate
            net_revenue = revenue - commission
            
            # El coste original fue (amount * entry_price) + commission (ya descontada del balance).
            # Para que el PnL refleje la realidad, debemos restarle también la comisión de entrada al beneficio bruto.
            entry_cost_gross = pos.amount * pos.entry_price
            entry_commission = entry_cost_gross * commission_rate
            entry_cost_total = entry_cost_gross + entry_commission
            
            pnl = net_revenue - entry_cost_total
            
            account.current_balance += net_revenue
            account.save(update_fields=['current_balance', 'updated_at'])
            
            pos.exit_price = current_price
            pos.closed_at = timezone.now()
            pos.pnl = pnl
            pos.status = 'closed'
            pos.save()
            
            pnl_type = 'ganancia' if pnl > 0 else 'pérdida'
            _log(bot, 'success', f"Operación simulada: VENTA de {pos.amount:.6f} {bot.symbol} a ${current_price:.2f}. PnL: ${pnl:.2f} ({pnl_type})")


def _execute_live_trade(bot: TradingBot, signal, connector):
    """Ejecuta una operación real en el exchange."""
    logger.warning(f"EJECUCIÓN EN VIVO NO IMPLEMENTADA COMPLETAMENTE: {signal}")
    # Aquí iría el connector.place_order(...) y crear un TradeRecord
