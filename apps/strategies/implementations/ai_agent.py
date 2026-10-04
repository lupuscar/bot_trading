import logging
import requests
import json
import pandas as pd

from typing import Dict, Any
from decimal import Decimal

from apps.strategies.base import BaseStrategy, Signal

logger = logging.getLogger(__name__)

class AIAgentStrategy(BaseStrategy):
    DISPLAY_NAME = 'Agente de Inteligencia Artificial (LLM)'
    """
    Estrategia impulsada por Inteligencia Artificial (LLM) y Sentimiento de Mercado.
    Combina indicadores técnicos tradicionales con el "Fear & Greed Index" y 
    pide una decisión final (BUY/SELL/HOLD) a un modelo de IA (OpenAI, Gemini, etc).
    """

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        return {
            'ai_provider': {
                'type': 'string',
                'default': 'openrouter',
                'description': 'Proveedor de IA',
                'choices': ['openrouter']
            },
            'model': {
                'type': 'string',
                'default': 'openrouter/free',
                'description': 'Modelo de IA a utilizar',
                'dynamic_choices': 'openrouter_models'
            },
            'confidence_threshold': {
                'type': 'number',
                'default': 75.0,
                'description': 'Nivel de confianza mínimo de la IA para ejecutar (0-100)'
            },
        }

    def get_default_params(self) -> dict:
        return {
            'ai_provider': 'openrouter',
            'model': 'openrouter/free',
            'confidence_threshold': 75.0,
        }

    def get_min_data_points(self) -> int:
        return 50  # Necesitamos algo de historia para calcular el RSI y la tendencia

    def _get_market_sentiment(self) -> str:
        """Obtiene el índice de Miedo y Codicia de Cripto (Público y Gratuito)"""
        try:
            response = requests.get('https://api.alternative.me/fng/?limit=1', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and len(data['data']) > 0:
                    val = data['data'][0]['value']
                    classification = data['data'][0]['value_classification']
                    return f"Fear & Greed Index: {val}/100 ({classification})"
        except Exception as e:
            logger.error(f"Error obteniendo sentimiento: {e}")
        
        return "Sentimiento de mercado desconocido."

    def _call_ai_api(self, prompt: str, provider: str, api_key: str, model_name: str) -> dict:
        """Llama a la API de la IA solicitada por HTTP puro (sin librerías extra)"""
        if not api_key and provider.lower() != 'ollama':
            return {"action": "hold", "confidence": 0, "reason": "No hay API Key configurada."}

        system_message = (
            "Eres un bot de trading algorítmico avanzado especializado en criptomonedas. "
            "Tu único propósito es analizar los datos de mercado técnicos y de sentimiento proporcionados, "
            "y decidir la próxima acción a tomar. "
            "DEBES RESPONDER ÚNICA Y EXCLUSIVAMENTE CON UN JSON VÁLIDO. SIN TEXTO EXTRA. "
            "Formato esperado: {\"action\": \"buy\"|\"sell\"|\"hold\", \"confidence\": 0-100, \"reason\": \"Explicación corta\"}"
        )

        try:
            if provider.lower() == 'openai':
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    return json.loads(content)
                else:
                    logger.error(f"Error OpenAI API: {resp.text}")

            elif provider.lower() == 'gemini':
                # Gemini REST API via Google AI Studio
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{
                        "parts": [{"text": system_message + "\n\n" + prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.2
                    }
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code == 200:
                    content = resp.json()['candidates'][0]['content']['parts'][0]['text']
                    # Limpiar markdown de json si existe
                    content = content.strip().strip("```json").strip("```").strip()
                    return json.loads(content)
                else:
                    logger.error(f"Error Gemini API: {resp.text}")

            elif provider.lower() == 'groq':
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    content = content.strip().strip("```json").strip("```").strip()
                    return json.loads(content)
                else:
                    logger.error(f"Error Groq API: {resp.text}")

            elif provider.lower() == 'openrouter':
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "BotTrading",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    logger.debug(f"RAW OPENROUTER RESPONSE: {repr(content)}")
                    
                    import re
                    # Buscar el primer { y el último }
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        content = match.group(0)
                    else:
                        raise ValueError(f"No JSON object found in response: {content}")
                    
                    return json.loads(content)
                else:
                    logger.error(f"Error OpenRouter API: {resp.text}")

            elif provider.lower() == 'ollama':
                base_url = api_key.rstrip('/') if api_key else "http://localhost:11434"
                url = f"{base_url}/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    content = content.strip().strip("```json").strip("```").strip()
                    return json.loads(content)
                else:
                    logger.error(f"Error Ollama API: {resp.text}")

        except Exception as e:
            logger.error(f"Error parseando respuesta de IA: {e}")

        return {"action": "hold", "confidence": 0, "reason": "Error en comunicación con la IA"}

    def analyze(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.get_min_data_points():
            return Signal(
                signal_type='hold', 
                symbol='',
                timestamp=df.iloc[-1]['timestamp'], 
                reason="Datos insuficientes"
            )

        # 1. Análisis Técnico Matemático Básico
        close_prices = df['close']
        current_price = close_prices.iloc[-1]
        
        # Calcular RSI (Pure Pandas para evitar dependencias externas como pandas_ta)
        period = 14
        delta = close_prices.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=period - 1, adjust=False).mean()
        ema_down = down.ewm(com=period - 1, adjust=False).mean()
        rs = ema_up / ema_down
        df['RSI'] = 100 - (100 / (1 + rs))
        current_rsi = df['RSI'].iloc[-1]
        
        # Calcular Tendencia (SMA 20)
        df['SMA_20'] = close_prices.rolling(window=20).mean()
        current_sma = df['SMA_20'].iloc[-1]
        trend = "Alcista (Por encima de SMA20)" if current_price > current_sma else "Bajista (Por debajo de SMA20)"

        # 2. Análisis de Sentimiento (Datos Externos)
        sentiment = self._get_market_sentiment()

        # 3. Construir el Prompt para la Inteligencia Artificial
        prompt = f"""
        DATOS ACTUALES DEL MERCADO:
        - Precio Actual: ${current_price:.2f}
        - Tendencia de corto plazo: {trend}
        - RSI (14 periodos): {current_rsi:.2f} (Considerar <30 sobreventa, >70 sobrecompra)
        - Sentimiento Externo: {sentiment}

        Analiza estos datos de forma objetiva. 
        ¿Es momento de comprar (buy), vender (sell), o quedarse quieto (hold)?
        Recuerda, responde SOLO en formato JSON estricto.
        """

        # 4. Obtener decisión del cerebro IA
        from apps.core.models import SystemSetting
        
        provider = self.params.get('ai_provider', 'openai')
        api_key = self.params.get('api_key', '')
        
        if not api_key:
            if provider.lower() == 'openai':
                setting = SystemSetting.objects.filter(key='OPENAI_API_KEY').first()
            elif provider.lower() == 'groq':
                setting = SystemSetting.objects.filter(key='GROQ_API_KEY').first()
            elif provider.lower() == 'openrouter':
                setting = SystemSetting.objects.filter(key='OPENROUTER_API_KEY').first()
            elif provider.lower() == 'ollama':
                setting = SystemSetting.objects.filter(key='OLLAMA_BASE_URL').first()
            else:
                setting = SystemSetting.objects.filter(key='GEMINI_API_KEY').first()
            api_key = setting.value if setting else ''

        model_name = self.params.get('model', 'gpt-3.5-turbo')
        threshold = float(self.params.get('confidence_threshold', 75.0))

        # En backtesting con muchas velas, llamar a la API por cada vela sería costosísimo y lento.
        # PROTECCIÓN DE COSTES: Si estamos en backtesting masivo (detectado si current_time es antiguo), podríamos bypassear.
        # Por ahora lo llamaremos, ¡cuidado con los costes de API en backtesting muy largos!
        
        decision = self._call_ai_api(prompt, provider, api_key, model_name)
        
        action = decision.get('action', 'hold').lower()
        
        try:
            confidence = float(decision.get('confidence', 0) or 0)
        except (ValueError, TypeError):
            confidence = 0.0
            
        reason = decision.get('reason', 'Sin justificación')

        # 5. Aplicar Filtro de Confianza
        if action != 'hold' and confidence >= threshold:
            return Signal(
                signal_type=action,
                symbol='',
                timestamp=df.iloc[-1]['timestamp'],
                price=current_price,
                reason=f"IA ({confidence}% confianza): {reason}"
            )

        return Signal(
            signal_type='hold',
            symbol='',
            timestamp=df.iloc[-1]['timestamp'],
            price=current_price,
            reason=f"IA sugirió {action} con confianza baja ({confidence}%) o sugirió HOLD. Razón: {reason}"
        )

    def get_chart_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Devuelve los indicadores visuales para que el usuario pueda ver el contexto del bot"""
        indicators = {}
        
        # Calcular y enviar SMA 20 para el gráfico de precios
        if len(df) >= 20:
            df['SMA_20'] = df['close'].rolling(window=20).mean()
            sma_data = []
            for _, row in df.iterrows():
                if not pd.isna(row['SMA_20']):
                    ts = int(row['timestamp'].timestamp())
                    sma_data.append({'time': ts, 'value': float(row['SMA_20'])})
            
            indicators['SMA_20'] = {
                'type': 'line',
                'title': 'SMA 20 (Tendencia IA)',
                'color': '#3b82f6', # Azul
                'data': sma_data,
                'pane': 0 # Panel principal de precios
            }
            
        return indicators
