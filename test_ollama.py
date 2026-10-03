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

def test_ollama():
    print("Obteniendo URL de Ollama desde la base de datos...")
    setting = SystemSetting.objects.filter(key='OLLAMA_BASE_URL').first()
    
    if not setting or not setting.value:
        print("ERROR: No se encontró la OLLAMA_BASE_URL en la base de datos. Asegúrate de haberla guardado en Configuración.")
        sys.exit(1)
        
    url = setting.value
    print(f"URL de Ollama encontrada: {url}")
    
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

    # Instanciar estrategia (usará llama3 por defecto si existe, o el modelo que le pasemos)
    # Aquí puedes cambiar 'llama3' por el modelo que tengas instalado ('mistral', 'gemma', etc)
    model_name = 'qwen2.5:7b' 
    print(f"\nIniciando AIAgentStrategy con proveedor='ollama' y modelo='{model_name}'")
    
    strategy = AIAgentStrategy(
        name='Test Agent',
        params={
            'ai_provider': 'ollama',
            'model': model_name,
            # Dejamos api_key en blanco para que lo lea de la BD automáticamente
            'api_key': '' 
        }
    )

    print("\nLlamando al Agente de Inteligencia Artificial (esperando respuesta de Ollama)...")
    try:
        signal = strategy.analyze(df)
        print("\n================ RESULTADO OLLAMA ================")
        print(f"Acción sugerida: {signal.signal_type.upper()}")
        print(f"Razón de la IA: {signal.reason}")
        print("==================================================")
    except Exception as e:
        print(f"\nError al ejecutar la estrategia: {e}")

if __name__ == '__main__':
    test_ollama()
