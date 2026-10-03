from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import PaperAccount, PaperTrade

@login_required
def paper_list(request):
    """Muestra la lista de carteras simuladas (una por bot)."""
    accounts = PaperAccount.objects.filter(user=request.user).order_by('-created_at')
    
    # Calcular métricas globales
    total_balance = sum(account.current_balance for account in accounts) if accounts else 0
    total_initial = sum(account.initial_balance for account in accounts) if accounts else 0
    total_pnl = total_balance - total_initial
    
    context = {
        'accounts': accounts,
        'total_balance': total_balance,
        'total_pnl': total_pnl,
    }
    return render(request, 'paper_trading/paper_list.html', context)

@login_required
def paper_detail(request, pk):
    """Muestra los detalles y el historial de operaciones de una cartera específica."""
    account = get_object_or_404(PaperAccount, pk=pk, user=request.user)
    trades = account.trades.all().order_by('-created_at')
    
    # Podemos agrupar posiciones abiertas y cerradas si queremos
    open_trades = trades.filter(status='open')
    closed_trades = trades.filter(status='closed')
    
    context = {
        'account': account,
        'open_trades': open_trades,
        'closed_trades': closed_trades,
    }
    return render(request, 'paper_trading/paper_detail.html', context)
