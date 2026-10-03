import os
import django
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

import pandas as pd
from datetime import datetime, timedelta
from apps.strategies.implementations.ai_agent import AIAgentStrategy
from apps.core.models import SystemSetting

def test_openrouter():
    print("Obteniendo API KEY de OpenRouter desde la base de datos...")
    setting = SystemSetting.objects.filter(key='OPENROUTER_API_KEY').first()
    
    if not setting or not setting.value:
        print("ERROR: No se encontró OPENROUTER_API_KEY en la base de datos.")
        sys.exit(1)
        
    print(f"API Key encontrada (oculta por seguridad: {setting.value[:5]}...)")
    
    # Crear datos simulados de mercado (velas)
    print("\nGenerando datos de mercado simulados...")
    dates = [datetime.now() - timedelta(days=i) for i in range(55, -1, -1)]
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [50000 + i*100 for i in range(56)],
        'high': [51000 + i*100 for i in range(56)],
        'low': [49000 + i*100 for i in range(56)],
        'close': [50500 + i*100 for i in range(56)],
        'volume': [1000 for i in range(56)],
    })

    # Instanciar estrategia usando OpenRouter y un modelo gratuito popular como google/gemma-7b-it:free
    # o meta-llama/llama-3-8b-instruct:free
    model_name = 'openrouter/free' 
    print(f"\nIniciando AIAgentStrategy con proveedor='openrouter' y modelo='{model_name}'")
    
    strategy = AIAgentStrategy(
        name='Test Agent',
        params={
            'ai_provider': 'openrouter',
            'model': model_name,
            'api_key': '' 
        }
    )

    print("\nLlamando al Agente de Inteligencia Artificial (esperando respuesta de OpenRouter)...")
    try:
        signal = strategy.analyze(df)
        print("\n================ RESULTADO OPENROUTER ================")
        print(f"Acción sugerida: {signal.signal_type.upper()}")
        print(f"Razón de la IA: {signal.reason}")
        print("======================================================")
    except Exception as e:
        print(f"\nError al ejecutar la estrategia: {e}")

if __name__ == '__main__':
    test_openrouter()
