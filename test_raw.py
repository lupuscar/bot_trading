import os
import django
import sys
import requests
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()
from apps.core.models import SystemSetting

def test_raw():
    setting = SystemSetting.objects.filter(key='OPENROUTER_API_KEY').first()
    api_key = setting.value
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "BotTrading",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openrouter/free",
        "messages": [
            {"role": "system", "content": "Responde SOLO con JSON {\"action\": \"buy\", \"confidence\": 90, \"reason\": \"test\"}"},
            {"role": "user", "content": "Hola"}
        ],
        "temperature": 0.2
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    print("STATUS:", resp.status_code)
    try:
        content = resp.json()['choices'][0]['message']['content']
        print("CONTENT RAW:")
        print(repr(content))
    except Exception as e:
        print("ERROR:", e, resp.text)

if __name__ == '__main__':
    test_raw()
