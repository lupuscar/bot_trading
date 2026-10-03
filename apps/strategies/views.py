"""
Vistas CRUD para gestionar estrategias de trading.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

import json

from apps.strategies.models import Strategy
from apps.core.models import TimeFrame





@login_required
def strategy_list(request):
    """Lista de estrategias del usuario."""
    strategies = Strategy.objects.filter(user=request.user)
    return render(request, 'strategies/list.html', {
        'title': 'Estrategias',
        'strategies': strategies,
    })


@login_required
def strategy_create(request):
    """Crear nueva estrategia."""
    from apps.strategies.registry import discover_strategies
    
    if request.method == 'POST':
        try:
            params = {}
            # Primero buscamos campos dinámicos
            has_dynamic = False
            for key, value in request.POST.items():
                if key.startswith('param_'):
                    has_dynamic = True
                    real_key = key.replace('param_', '')
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                    params[real_key] = value
            
            # Si no hay dinámicos, intentamos leer el JSON crudo fallback
            if not has_dynamic:
                params_raw = request.POST.get('parameters', '{}')
                params = json.loads(params_raw) if params_raw else {}

            Strategy.objects.create(
                user=request.user,
                name=request.POST['name'],
                description=request.POST.get('description', ''),
                strategy_class=request.POST['strategy_class'],
                version=request.POST.get('version', '1.0'),
                timeframe=request.POST['timeframe'],
                parameters=params,
            )
            messages.success(request, 'Estrategia creada correctamente.')
            return redirect('strategies:list')
        except json.JSONDecodeError:
            messages.error(request, 'Los parámetros deben ser JSON válido.')
        except Exception as e:
            messages.error(request, f'Error al crear la estrategia: {e}')

    return render(request, 'strategies/form.html', {
        'title': 'Nueva Estrategia',
        'timeframes': TimeFrame.choices,
        'strategy_classes': discover_strategies(),
    })


@login_required
def strategy_edit(request, pk):
    """Editar estrategia existente."""
    from apps.strategies.registry import discover_strategies
    
    strategy = get_object_or_404(Strategy, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            params = {}
            has_dynamic = False
            for key, value in request.POST.items():
                if key.startswith('param_'):
                    has_dynamic = True
                    real_key = key.replace('param_', '')
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                    params[real_key] = value
            
            if not has_dynamic:
                params_raw = request.POST.get('parameters', '{}')
                params = json.loads(params_raw) if params_raw else {}

            strategy.name = request.POST['name']
            strategy.description = request.POST.get('description', '')
            strategy.strategy_class = request.POST['strategy_class']
            strategy.version = request.POST.get('version', '1.0')
            strategy.timeframe = request.POST['timeframe']
            strategy.parameters = params
            strategy.save()
            messages.success(request, 'Estrategia actualizada correctamente.')
            return redirect('strategies:list')
        except json.JSONDecodeError:
            messages.error(request, 'Los parámetros deben ser JSON válido.')
        except Exception as e:
            messages.error(request, f'Error al actualizar: {e}')

    return render(request, 'strategies/form.html', {
        'title': f'Editar: {strategy.name}',
        'strategy': strategy,
        'timeframes': TimeFrame.choices,
        'strategy_classes': discover_strategies(),
        'params_json': json.dumps(strategy.parameters, indent=2),
    })


@login_required
def strategy_delete(request, pk):
    """Eliminar una estrategia."""
    strategy = get_object_or_404(Strategy, pk=pk, user=request.user)
    if request.method == 'POST':
        name = strategy.name
        strategy.delete()
        messages.success(request, f'Estrategia "{name}" eliminada.')
        return redirect('strategies:list')
    return render(request, 'strategies/confirm_delete.html', {
        'title': 'Eliminar Estrategia',
        'strategy': strategy,
    })

@login_required
def strategy_params_form(request):
    """
    Endpoint HTMX para devolver el formulario dinámico de parámetros
    basado en la estrategia seleccionada.
    """
    import importlib
    strategy_class_path = request.GET.get('strategy_class')
    strategy_id = request.GET.get('strategy_id')
    
    schema = {}
    saved_params = {}
    
    if strategy_id:
        try:
            strategy = Strategy.objects.get(id=strategy_id, user=request.user)
            saved_params = strategy.parameters
        except Strategy.DoesNotExist:
            pass

    if strategy_class_path:
        try:
            module_name, class_name = strategy_class_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            strategy_class = getattr(module, class_name)
            schema = strategy_class.get_parameters_schema()
            
            # Fetch dynamic choices if needed
            for key, field_def in schema.items():
                if field_def.get('dynamic_choices') == 'openrouter_models':
                    import requests
                    from apps.core.models import SystemSetting
                    api_key = SystemSetting.objects.filter(key='OPENROUTER_API_KEY').first()
                    models_list = ['openrouter/free'] # Fallback default
                    if api_key and api_key.value:
                        try:
                            resp = requests.get(
                                "https://openrouter.ai/api/v1/models",
                                headers={"Authorization": f"Bearer {api_key.value}"},
                                timeout=5
                            )
                            if resp.status_code == 200:
                                models_data = resp.json().get('data', [])
                                models_list = sorted([m['id'] for m in models_data])
                        except Exception as req_e:
                            print(f"Error fetching OpenRouter models: {req_e}")
                    
                    field_def['choices'] = models_list

            # Sobreescribir defaults con los valores guardados
            for key, field_def in schema.items():
                if key in saved_params:
                    field_def['default'] = saved_params[key]
        except Exception as e:
            print(f"Error cargando esquema de {strategy_class_path}: {e}")
            
    return render(request, 'strategies/partials/params_form.html', {
        'schema': schema,
    })
