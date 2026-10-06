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
    return render(request, 'optimizer/list.html', {'runs': runs})

@login_required
def optimizer_create(request):
    if request.method == 'POST':
        symbol = request.POST.get('symbol', 'BTC/USDT')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        trade_risk_pct = float(request.POST.get('trade_risk_pct', 5.0))
        selected_strategies = request.POST.getlist('strategies')
        
        if not all([symbol, start_date, end_date]) or not selected_strategies:
            messages.error(request, 'Todos los campos y al menos una estrategia son obligatorios')
            return redirect('optimizer:create')
            
        run = OptimizationRun.objects.create(
            user=request.user,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            trade_risk_pct=trade_risk_pct,
            selected_strategies=selected_strategies,
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
