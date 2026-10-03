import json
import logging
from datetime import datetime, timedelta

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

from apps.live_trading.models import TradingBot
from apps.paper_trading.models import PaperAccount
from apps.core.models import Candle, SystemSetting

logger = logging.getLogger(__name__)


def _get_chart_data_from_db(symbol, timeframe, limit=200):
    """Intentar obtener datos de velas desde la BD."""
    candles = Candle.objects.filter(
        symbol=symbol, timeframe=timeframe
    ).order_by('-timestamp')[:limit]

    data = []
    for c in reversed(list(candles)):
        time_val = c.timestamp.strftime('%Y-%m-%d') if timeframe == '1d' else int(c.timestamp.timestamp())
        data.append({
            'time': time_val,
            'open': float(c.open),
            'high': float(c.high),
            'low': float(c.low),
            'close': float(c.close),
        })
    return data


_cached_dashboard_connector = None

def _get_chart_data_from_binance(symbol, timeframe, limit=200):
    """
    Obtener datos de velas de Binance (solo las necesarias) y actualizar la BD local.
    Devuelve las velas combinadas de la BD.
    """
    global _cached_dashboard_connector
    try:
        if not _cached_dashboard_connector:
            from apps.connectors.crypto.binance import BinanceConnector
            _cached_dashboard_connector = BinanceConnector(
                name='dashboard_public',
                market_type='crypto',
                config={'testnet': False}
            )
            if not _cached_dashboard_connector.connect():
                logger.warning("No se pudo conectar a Binance para datos del gráfico.")
                _cached_dashboard_connector = None
                return _get_chart_data_from_db(symbol, timeframe, limit)
        
        connector = _cached_dashboard_connector

        try:
            # Obtener el último timestamp guardado para descargar solo lo nuevo
            last_candle = Candle.objects.filter(symbol=symbol, timeframe=timeframe).order_by('-timestamp').first()
            last_ts = last_candle.timestamp if last_candle else None
            
            # ccxt traerá velas desde 'start' si existe, de lo contrario las más recientes.
            df = connector.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=last_ts,
                limit=limit if not last_ts else None, 
            )

            if df.empty:
                return _get_chart_data_from_db(symbol, timeframe, limit)

            # Usar update_or_create porque la última vela (en last_ts) podía estar incompleta
            for _, row in df.iterrows():
                Candle.objects.update_or_create(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=row['timestamp'],
                    defaults={
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row['volume']
                    }
                )
                
            # Una vez la BD está actualizada con las velas nuevas, 
            # delegamos en la función de la BD para que formatee y devuelva las últimas N.
            return _get_chart_data_from_db(symbol, timeframe, limit)
            
        finally:
            # NO desconectamos el conector aquí para mantener la caché global
            pass

    except Exception as e:
        logger.error(f"Error obteniendo datos de Binance: {e}")
        return _get_chart_data_from_db(symbol, timeframe, limit)


def _get_celery_status():
    """Comprueba el estado del trabajador de Celery."""
    try:
        from config.celery import app
        # Usamos un timeout corto de 0.5s para evitar que el dashboard tarde en cargar si Redis está caído
        i = app.control.inspect(timeout=0.5)
        active = i.active()
        if active is None:
            return {'status': 'offline', 'msg': 'Motor detenido (No hay workers)'}
        
        return {'status': 'online', 'msg': f'{len(active)} Worker(s) Online'}
    except Exception:
        return {'status': 'error', 'msg': 'Redis/Broker desconectado'}


@login_required
def index(request):
    """Página principal del dashboard."""
    bots = TradingBot.objects.all()
    paper_accounts = PaperAccount.objects.prefetch_related('trades').all()

    # Símbolo y timeframe del primer bot, o valores por defecto
    symbol = bots.first().symbol if bots.exists() else 'BTC/USDT'
    timeframe = bots.first().timeframe if bots.exists() else '1d'

    # Ya NO obtenemos los datos de Binance de forma síncrona para no ralentizar la carga de la página.
    # Delegamos toda la carga del gráfico a la llamada AJAX en el frontend.
    
    context = {
        'title': 'Dashboard',
        'bots': bots,
        'paper_accounts': paper_accounts,
        'chart_data_json': '[]',
        'chart_symbol': symbol,
        'chart_timeframe': timeframe,
        'chart_data_source': 'loading',
        'chart_candle_count': 0,
        'celery_status': _get_celery_status(),
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def get_chart_data(request):
    """
    API endpoint: devuelve datos de velas para el gráfico.
    Acepta ?symbol=BTC/USDT&timeframe=1d&source=auto&bot_id=1
    source: 'db' (solo BD), 'binance' (solo API), 'auto' (BD → fallback Binance)
    """
    import time
    symbol = request.GET.get('symbol', 'BTC/USDT')
    timeframe = request.GET.get('timeframe', '1d')
    source = request.GET.get('source', 'auto')
    bot_id = request.GET.get('bot_id')

    data = []

    if source in ('db', 'auto'):
        data = _get_chart_data_from_db(symbol, timeframe)

    needs_update = not data
    if source == 'auto':
        # Como hemos optimizado la descarga para pedir solo la última vela desde la caché,
        # forzamos SIEMPRE la actualización para tener el precio real en la vela actual incompleta.
        needs_update = True

    if needs_update and source in ('binance', 'auto'):
        binance_data = _get_chart_data_from_binance(symbol, timeframe)
        if binance_data:
            data = binance_data
            source = 'binance'

    markers = []
    if bot_id:
        from apps.paper_trading.models import PaperTrade
        trades = PaperTrade.objects.filter(account__bot_id=bot_id, symbol=symbol)
        for t in trades:
            ts = int(t.created_at.timestamp())
            markers.append({
                'time': ts,
                'position': 'belowBar' if t.side == 'buy' else 'aboveBar',
                'color': '#10b981' if t.side == 'buy' else '#ef4444',
                'shape': 'arrowUp' if t.side == 'buy' else 'arrowDown',
                'text': f"{t.side.upper()} {t.amount:.2f} @ {t.entry_price:.2f}"
            })

    return JsonResponse({
        'data': data,
        'symbol': symbol,
        'timeframe': timeframe,
        'count': len(data),
        'source': 'db' if source == 'db' and data and not needs_update else ('binance' if data else 'empty'),
        'markers': markers,
    })

import sys
import subprocess
import os
from django.contrib import messages
from django.shortcuts import redirect

@login_required
def settings_view(request):
    """Panel unificado de configuración (IA, Exchanges, Sistema)."""
    if request.method == 'POST':
        keys = ['OPENAI_API_KEY', 'GEMINI_API_KEY', 'GROQ_API_KEY', 'OPENROUTER_API_KEY', 'OLLAMA_BASE_URL', 'BINANCE_API_KEY', 'BINANCE_API_SECRET']
        for key in keys:
            val = request.POST.get(key)
            if val is not None:
                setting, _ = SystemSetting.objects.get_or_create(key=key)
                setting.value = val
                setting.save()
        messages.success(request, "Configuración guardada correctamente.")
        return redirect('dashboard:settings')

    settings = {s.key: s.value for s in SystemSetting.objects.all()}

    return render(request, 'dashboard/settings.html', {
        'title': 'Configuración Unificada',
        'settings': settings,
        'celery_status': _get_celery_status(),
    })


@login_required
def system_action(request):
    """Acciones para arrancar/detener Celery."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'start':
            try:
                env = os.environ.copy()
                # Iniciar Worker
                subprocess.Popen([sys.executable, "-m", "celery", "-A", "config", "worker", "-l", "info"], 
                                 env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Iniciar Beat
                subprocess.Popen([sys.executable, "-m", "celery", "-A", "config", "beat", "-l", "info"], 
                                 env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                messages.success(request, "Se ha enviado la orden de arranque a Celery (Worker + Beat).")
            except Exception as e:
                messages.error(request, f"Error arrancando el motor: {e}")
                
        elif action == 'stop':
            try:
                os.system("pkill -f 'celery -A config'")
                messages.success(request, "Se ha enviado la orden de apagado al motor.")
            except Exception as e:
                messages.error(request, f"Error deteniendo el motor: {e}")
                
    return redirect('dashboard:settings')
