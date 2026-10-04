import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from apps.backtesting.models import BacktestRun
from apps.strategies.models import Strategy
from apps.core.models import TimeFrame
from apps.backtesting.engine import BacktestEngine


@login_required
def run_list(request):
    runs = BacktestRun.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'backtesting/run_list.html', {'runs': runs})




@login_required
def run_delete(request, pk):
    run = get_object_or_404(BacktestRun, pk=pk, user=request.user)
    if request.method == 'POST':
        run.delete()
        messages.success(request, 'Backtest eliminado correctamente.')
    return redirect('backtesting:run_list')


@login_required
def run_delete_all(request):
    if request.method == 'POST':
        count, _ = BacktestRun.objects.filter(user=request.user).delete()
        messages.success(request, f'Se han eliminado {count} backtests correctamente.')
    return redirect('backtesting:run_list')


@login_required
def run_create(request):
    if request.method == 'POST':
        strategy_id = request.POST.get('strategy_id')
        symbol = request.POST.get('symbol')
        timeframe = request.POST.get('timeframe')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        initial_capital = request.POST.get('initial_capital')
        trade_risk_pct = request.POST.get('trade_risk_pct', '100.0')
        allow_pyramiding = request.POST.get('allow_pyramiding') == 'on'

        try:
            strategy = Strategy.objects.get(id=strategy_id)
            
            run = BacktestRun.objects.create(
                user=request.user,
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                trade_risk_pct=trade_risk_pct,
                allow_pyramiding=allow_pyramiding,
                strategy_params=strategy.parameters,
                status='pending'
            )
            
            # Ejecutar de forma síncrona por ahora (para MVP), 
            # en un entorno de producción se enviaría a Celery
            try:
                engine = BacktestEngine(run.id)
                from django.utils.module_loading import import_string
                strategy_cls = import_string(strategy.strategy_class)
                engine.set_strategy_class(strategy_cls)
                engine.run()
                messages.success(request, f"Backtest ejecutado correctamente.")
            except Exception as e:
                run.status = 'failed'
                run.error_message = str(e)
                run.save()
                messages.error(request, f"Error ejecutando backtest: {e}")

            return redirect('backtesting:run_detail', pk=run.id)
            
        except Exception as e:
            messages.error(request, f"Error creando el backtest: {e}")

    strategies = Strategy.objects.all()
    timeframes = TimeFrame.choices

    # Default dates (last 30 days)
    end = timezone.now()
    start = end - timezone.timedelta(days=30)

    context = {
        'strategies': strategies,
        'timeframes': timeframes,
        'default_start': start.strftime('%Y-%m-%dT%H:%M'),
        'default_end': end.strftime('%Y-%m-%dT%H:%M'),
    }
    return render(request, 'backtesting/run_create.html', context)


@login_required
def run_detail(request, pk):
    run = get_object_or_404(BacktestRun, pk=pk, user=request.user)
    
    # Preparar datos para gráficos
    equity_curve_json = "[]"
    if run.results_data and 'equity_curve' in run.results_data:
        # Formatear para TradingView o similar
        formatted_curve = []
        for point in run.results_data['equity_curve']:
            # Tradingview necesita formato string YYYY-MM-DD o timestamp
            formatted_curve.append({
                'time': int(timezone.datetime.fromisoformat(point['timestamp']).timestamp()),
                'value': point['equity']
            })
        equity_curve_json = json.dumps(formatted_curve)
    # Preparar datos para velas y marcadores
    chart_data_json = "[]"
    markers_json = "[]"
    indicators_json = "{}"
    from apps.core.models import Candle
    import pandas as pd
    from django.utils.module_loading import import_string
    
    if run.status == 'completed':
        # Calcular fecha de inicio extendida para "calentar" indicadores (warmup)
        tf_minutes = {'m': 1, 'h': 60, 'd': 1440, 'w': 10080}
        unit = run.timeframe[-1]
        try:
            val = int(run.timeframe[:-1])
            mins = val * tf_minutes.get(unit, 60)
        except:
            mins = 60
        warmup_delta = timezone.timedelta(minutes=mins * 250)
        fetch_start = run.start_date - warmup_delta

        candles = Candle.objects.filter(
            symbol=run.symbol,
            timeframe=run.timeframe,
            timestamp__gte=fetch_start,
            timestamp__lte=run.end_date
        ).order_by('timestamp')
        
        candle_data = []
        raw_df_data = []
        for c in candles:
            if c.timestamp >= run.start_date:
                candle_data.append({
                    'time': int(c.timestamp.timestamp()),
                    'open': float(c.open),
                    'high': float(c.high),
                    'low': float(c.low),
                    'close': float(c.close),
                })
            
            # DF data includes warmup
            raw_df_data.append({
                'timestamp': c.timestamp,
                'close': float(c.close),
                'open': float(c.open),
                'high': float(c.high),
                'low': float(c.low),
                'volume': float(c.volume)
            })
            
        chart_data_json = json.dumps(candle_data)
        
        # Calcular indicadores de la estrategia
        try:
            if raw_df_data:
                df = pd.DataFrame(raw_df_data)
                strategy_cls = import_string(run.strategy.strategy_class)
                st = strategy_cls(name=run.strategy.name, params=run.strategy_params)
                indicators = st.get_chart_indicators(df)
                
                # Filtrar indicadores para no mostrar el warmup en el gráfico
                start_ts = int(run.start_date.timestamp())
                for key, ind in indicators.items():
                    ind['data'] = [pt for pt in ind['data'] if pt['time'] >= start_ts]
                    
                indicators_json = json.dumps(indicators)
        except Exception as e:
            print(f"Error calculating indicators: {e}")
        
        markers = []
        if run.results_data and 'trades' in run.results_data:
            for t in run.results_data['trades']:
                trade_time = int(timezone.datetime.fromisoformat(t['timestamp']).timestamp())
                if t['side'] == 'buy':
                    markers.append({
                        'time': trade_time,
                        'position': 'belowBar',
                        'color': '#10b981',
                        'shape': 'arrowUp',
                        'text': 'BUY'
                    })
                elif t['side'] == 'sell':
                    markers.append({
                        'time': trade_time,
                        'position': 'aboveBar',
                        'color': '#ef4444',
                        'shape': 'arrowDown',
                        'text': 'SELL'
                    })
            markers_json = json.dumps(markers)
            
    return render(request, 'backtesting/run_detail.html', {
        'run': run,
        'equity_curve_json': equity_curve_json,
        'chart_data_json': chart_data_json,
        'markers_json': markers_json,
        'indicators_json': indicators_json
    })
