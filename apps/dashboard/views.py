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


def _get_chart_data_from_binance(symbol, timeframe, limit=200):
    """
    Obtener datos de velas directamente de Binance API y guardarlos en la BD para futuro uso (caché local).
    """
    try:
        from apps.connectors.crypto.binance import BinanceConnector

        connector = BinanceConnector(
            name='dashboard_public',
            market_type='crypto',
            config={'testnet': False}
        )
        if not connector.connect():
            logger.warning("No se pudo conectar a Binance para datos del gráfico.")
            return []

        try:
            # Al pasar start=None, ccxt traerá las últimas 'limit' velas más recientes.
            df = connector.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=None,
                limit=limit,
            )

            if df.empty:
                return []

            data = []
            new_candles = []
            
            # Obtener el último timestamp guardado para no duplicar
            last_candle = Candle.objects.filter(symbol=symbol, timeframe=timeframe).order_by('-timestamp').first()
            last_ts = last_candle.timestamp if last_candle else None
            
            for _, row in df.iterrows():
                ts = row['timestamp']
                
                # Preparar para guardar en BD si es más reciente o no existe
                if not last_ts or ts > last_ts:
                    new_candles.append(Candle(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=ts,
                        open=row['open'],
                        high=row['high'],
                        low=row['low'],
                        close=row['close'],
                        volume=row['volume']
                    ))

                if timeframe == '1d':
                    time_val = ts.strftime('%Y-%m-%d')
                else:
                    time_val = int(ts.timestamp())

                data.append({
                    'time': time_val,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                })
                
            # Guardar en BD para futuras peticiones (Bulk create)
            if new_candles:
                Candle.objects.bulk_create(new_candles, ignore_conflicts=True)
                
            return data
        finally:
            connector.disconnect()

    except Exception as e:
        logger.error(f"Error obteniendo datos de Binance: {e}")
        return []


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
    Acepta ?symbol=BTC/USDT&timeframe=1d&source=auto
    source: 'db' (solo BD), 'binance' (solo API), 'auto' (BD → fallback Binance)
    """
    symbol = request.GET.get('symbol', 'BTC/USDT')
    timeframe = request.GET.get('timeframe', '1d')
    source = request.GET.get('source', 'auto')

    data = []

    if source in ('db', 'auto'):
        data = _get_chart_data_from_db(symbol, timeframe)

    if not data and source in ('binance', 'auto'):
        data = _get_chart_data_from_binance(symbol, timeframe)

    return JsonResponse({
        'data': data,
        'symbol': symbol,
        'timeframe': timeframe,
        'count': len(data),
        'source': 'db' if source == 'db' and data else ('binance' if data else 'empty'),
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
