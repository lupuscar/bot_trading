"""
Vistas CRUD para gestionar conexiones a exchanges.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from apps.connectors.models import ExchangeConnection
from apps.core.models import MarketType


@login_required
def connector_list(request):
    """Lista de conexiones a exchanges del usuario."""
    connections = ExchangeConnection.objects.filter(user=request.user)
    return render(request, 'connectors/list.html', {
        'title': 'Conectores',
        'connections': connections,
    })


@login_required
def connector_create(request):
    """Crear nueva conexión a exchange."""
    if request.method == 'POST':
        try:
            ExchangeConnection.objects.create(
                user=request.user,
                name=request.POST['name'],
                exchange_id=request.POST['exchange_id'],
                market_type=request.POST['market_type'],
                api_key=request.POST.get('api_key', ''),
                api_secret=request.POST.get('api_secret', ''),
                api_passphrase=request.POST.get('api_passphrase', ''),
                is_testnet=request.POST.get('is_testnet') == 'on',
            )
            messages.success(request, 'Conexión creada correctamente.')
            return redirect('connectors:list')
        except Exception as e:
            messages.error(request, f'Error al crear la conexión: {e}')

    return render(request, 'connectors/form.html', {
        'title': 'Nueva Conexión',
        'market_types': MarketType.choices,
        'exchanges': [
            ('binance', 'Binance'),
            ('kraken', 'Kraken'),
            ('coinbase', 'Coinbase'),
            ('oanda', 'OANDA'),
            ('interactive_brokers', 'Interactive Brokers'),
        ],
    })


@login_required
def connector_edit(request, pk):
    """Editar una conexión existente."""
    connection = get_object_or_404(ExchangeConnection, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            connection.name = request.POST['name']
            connection.exchange_id = request.POST['exchange_id']
            connection.market_type = request.POST['market_type']
            # Solo actualizar keys si se proporcionan nuevas (no sobrescribir con vacío)
            new_key = request.POST.get('api_key', '')
            if new_key:
                connection.api_key = new_key
            new_secret = request.POST.get('api_secret', '')
            if new_secret:
                connection.api_secret = new_secret
            new_passphrase = request.POST.get('api_passphrase', '')
            if new_passphrase:
                connection.api_passphrase = new_passphrase
            connection.is_testnet = request.POST.get('is_testnet') == 'on'
            connection.save()
            messages.success(request, 'Conexión actualizada correctamente.')
            return redirect('connectors:list')
        except Exception as e:
            messages.error(request, f'Error al actualizar: {e}')

    return render(request, 'connectors/form.html', {
        'title': f'Editar: {connection.name}',
        'connection': connection,
        'market_types': MarketType.choices,
        'exchanges': [
            ('binance', 'Binance'),
            ('kraken', 'Kraken'),
            ('coinbase', 'Coinbase'),
            ('oanda', 'OANDA'),
            ('interactive_brokers', 'Interactive Brokers'),
        ],
    })


@login_required
def connector_delete(request, pk):
    """Eliminar una conexión."""
    connection = get_object_or_404(ExchangeConnection, pk=pk, user=request.user)
    if request.method == 'POST':
        name = connection.name
        connection.delete()
        messages.success(request, f'Conexión "{name}" eliminada.')
        return redirect('connectors:list')
    return render(request, 'connectors/confirm_delete.html', {
        'title': 'Eliminar Conexión',
        'connection': connection,
    })


@login_required
def connector_test(request, pk):
    """Probar conexión a un exchange (AJAX)."""
    connection = get_object_or_404(ExchangeConnection, pk=pk, user=request.user)

    try:
        # Importar dinámicamente según exchange_id
        if connection.exchange_id == 'binance':
            from apps.connectors.crypto.binance import BinanceConnector
            connector = BinanceConnector(
                name=connection.name,
                market_type=connection.market_type,
                config=connection.get_connector_config(),
            )
        else:
            return JsonResponse({'success': False, 'message': f'Conector {connection.exchange_id} no implementado.'})

        if connector.test_connection():
            return JsonResponse({'success': True, 'message': 'Conexión exitosa ✅'})
        else:
            return JsonResponse({'success': False, 'message': 'La conexión falló. Verifica tus credenciales.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
