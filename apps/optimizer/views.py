from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import OptimizationRun, OptimizationResult
from .tasks import run_optimization_task
from apps.strategies.registry import discover_strategies

@login_required
def optimizer_list(request):
    runs = OptimizationRun.objects.filter(user=request.user)
    has_running = any(run.status in ['pending', 'running'] for run in runs)
    return render(request, 'optimizer/list.html', {'runs': runs, 'has_running': has_running})

@login_required
def optimizer_create(request):
    if request.method == 'POST':
        symbol = request.POST.get('symbol', 'BTC/USDT')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        trade_risk_pct = float(request.POST.get('trade_risk_pct', 5.0))
        selected_strategies = request.POST.getlist('strategies')
        selected_timeframes = request.POST.getlist('timeframes')
        
        if not all([symbol, start_date, end_date]) or not selected_strategies or not selected_timeframes:
            messages.error(request, 'Todos los campos, al menos una estrategia y una temporalidad son obligatorios')
            return redirect('optimizer:create')
            
        run = OptimizationRun.objects.create(
            user=request.user,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            trade_risk_pct=trade_risk_pct,
            selected_strategies=selected_strategies,
            selected_timeframes=selected_timeframes,
            status='pending'
        )
        
        # Trigger celery task
        run_optimization_task.delay(run.id)
        
        messages.success(request, 'La optimización ha comenzado en segundo plano.')
        return redirect('optimizer:list')
    
    strategies = [s for s in discover_strategies() if 'AIAgent' not in s[0]]
    return render(request, 'optimizer/create.html', {'strategies': strategies})

@login_required
def optimizer_detail(request, pk):
    run = get_object_or_404(OptimizationRun, pk=pk, user=request.user)
    results = run.results.all()
    
    # Get top 3
    top_results = list(results[:3])
    
    return render(request, 'optimizer/detail.html', {
        'run': run,
        'results': results,
        'top_results': top_results
    })

@login_required
def optimizer_delete(request, pk):
    run = get_object_or_404(OptimizationRun, pk=pk, user=request.user)
    if request.method == 'POST':
        run.delete()
        messages.success(request, 'Optimización eliminada')
    return redirect('optimizer:list')

@login_required
def optimizer_save_strategy(request, result_id):
    from apps.strategies.models import Strategy
    
    if request.method == 'POST':
        result = get_object_or_404(OptimizationResult, pk=result_id, run__user=request.user)
        
        # Create a new strategy from the optimization result
        name = f"Optimized {result.strategy_name} ({result.run.symbol} {result.timeframe})"
        if len(name) > 100:
            name = name[:97] + "..."
            
        strategy = Strategy.objects.create(
            user=request.user,
            name=name,
            description=f"Auto-generated from Optimizer Run #{result.run.id}. Return: {result.total_return_pct}%.",
            strategy_class=result.strategy_class,
            version="1.0",
            timeframe=result.timeframe,
            parameters=result.parameters
        )
        
        messages.success(request, f'¡Estrategia "{name}" guardada con éxito!')
        return redirect('strategies:list')
        
    return redirect('optimizer:list')
