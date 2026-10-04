"""
Vistas CRUD para gestionar bots de trading.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from apps.live_trading.models import TradingBot, TradeRecord
from apps.connectors.models import ExchangeConnection
from apps.strategies.models import Strategy
from apps.core.models import TimeFrame, TradingMode


@login_required
def bot_list(request):
    """Lista de bots del usuario."""
    bots = TradingBot.objects.filter(user=request.user).select_related(
        'exchange_connection', 'strategy'
    )
    return render(request, 'bots/list.html', {
        'title': 'Bots de Trading',
        'bots': bots,
    })


@login_required
def bot_create(request):
    """Crear nuevo bot de trading."""
    if request.method == 'POST':
        try:
            bot = TradingBot.objects.create(
                user=request.user,
                name=request.POST['name'],
                description=request.POST.get('description', ''),
                exchange_connection_id=request.POST['exchange_connection'],
                strategy_id=request.POST['strategy'],
                symbol=request.POST['symbol'],
                timeframe=request.POST['timeframe'],
                mode=request.POST['mode'],
                max_position_size=request.POST['max_position_size'],
                risk_per_trade_pct=request.POST.get('risk_per_trade_pct', 2.0),
                max_open_positions=request.POST.get('max_open_positions', 3),
                daily_loss_limit_pct=request.POST.get('daily_loss_limit_pct', 5.0),
            )
            
            if bot.mode == TradingMode.PAPER:
                from apps.paper_trading.models import PaperAccount
                from decimal import Decimal
                PaperAccount.objects.create(
                    bot=bot,
                    user=request.user,
                    name=f'Cartera de {bot.name}',
                    initial_balance=Decimal('10000.00'),
                    current_balance=Decimal('10000.00'),
                )
                
            messages.success(request, 'Bot creado correctamente.')
            return redirect('live_trading:list')
        except Exception as e:
            messages.error(request, f'Error al crear el bot: {e}')

    connections = ExchangeConnection.objects.filter(user=request.user, is_active=True)
    strategies = Strategy.objects.filter(user=request.user, is_active=True)

    return render(request, 'bots/form.html', {
        'title': 'Nuevo Bot',
        'connections': connections,
        'strategies': strategies,
        'timeframes': TimeFrame.choices,
        'modes': TradingMode.choices,
    })


@login_required
def bot_edit(request, pk):
    """Editar un bot existente."""
    bot = get_object_or_404(TradingBot, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            bot.name = request.POST['name']
            bot.description = request.POST.get('description', '')
            bot.exchange_connection_id = request.POST['exchange_connection']
            bot.strategy_id = request.POST['strategy']
            bot.symbol = request.POST['symbol']
            bot.timeframe = request.POST['timeframe']
            bot.mode = request.POST['mode']
            bot.max_position_size = request.POST['max_position_size']
            bot.risk_per_trade_pct = request.POST.get('risk_per_trade_pct', 2.0)
            bot.max_open_positions = request.POST.get('max_open_positions', 3)
            bot.daily_loss_limit_pct = request.POST.get('daily_loss_limit_pct', 5.0)
            bot.save()
            messages.success(request, 'Bot actualizado correctamente.')
            return redirect('live_trading:list')
        except Exception as e:
            messages.error(request, f'Error al actualizar: {e}')

    connections = ExchangeConnection.objects.filter(user=request.user, is_active=True)
    strategies = Strategy.objects.filter(user=request.user, is_active=True)

    return render(request, 'bots/form.html', {
        'title': f'Editar: {bot.name}',
        'bot': bot,
        'connections': connections,
        'strategies': strategies,
        'timeframes': TimeFrame.choices,
        'modes': TradingMode.choices,
    })


@login_required
def bot_delete(request, pk):
    """Eliminar un bot."""
    bot = get_object_or_404(TradingBot, pk=pk, user=request.user)
    if request.method == 'POST':
        name = bot.name
        bot.delete()
        messages.success(request, f'Bot "{name}" eliminado.')
        return redirect('live_trading:list')
    return render(request, 'bots/confirm_delete.html', {
        'title': 'Eliminar Bot',
        'bot': bot,
    })


@login_required
def bot_toggle(request, pk):
    """Arrancar o detener un bot (AJAX/HTMX)."""
    bot = get_object_or_404(TradingBot, pk=pk, user=request.user)

    if bot.status == 'running':
        bot.status = 'stopped'
        bot.save(update_fields=['status', 'updated_at'])
        msg = f'Bot "{bot.name}" detenido.'
    else:
        # Si lo estamos arrancando y es modo PAPER, asegurarnos de que su cartera existe
        if bot.mode == TradingMode.PAPER:
            from apps.paper_trading.models import PaperAccount
            from decimal import Decimal
            PaperAccount.objects.get_or_create(
                bot=bot,
                defaults={
                    'user': bot.user,
                    'name': f'Cartera de {bot.name}',
                    'initial_balance': Decimal('10000.00'),
                    'current_balance': Decimal('10000.00'),
                }
            )
            
        bot.status = 'running'
        bot.save(update_fields=['status', 'updated_at'])
        msg = f'Bot "{bot.name}" iniciado.'

    if request.headers.get('HX-Request'):
        # Devolvemos la fila actualizada para HTMX
        return render(request, 'bots/_bot_row.html', {'bot': bot})

    messages.success(request, msg)
    return redirect('live_trading:list')


@login_required
def bot_trades(request, pk):
    """Historial de operaciones de un bot."""
    bot = get_object_or_404(TradingBot, pk=pk, user=request.user)
    
    if bot.mode == 'paper':
        from apps.paper_trading.models import PaperTrade
        from django.db.models import F, ExpressionWrapper, DecimalField
        
        # En Paper Trading, anotamos los campos que espera la plantilla (price, cost)
        trades = PaperTrade.objects.filter(account__bot=bot).annotate(
            price=F('entry_price'),
            cost=ExpressionWrapper(F('amount') * F('entry_price'), output_field=DecimalField())
        ).order_by('-created_at')[:100]
    else:
        trades = TradeRecord.objects.filter(bot=bot).order_by('-created_at')[:100]
        
    return render(request, 'bots/trades.html', {
        'title': f'Operaciones: {bot.name}',
        'bot': bot,
        'trades': trades,
    })
