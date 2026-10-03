#!/bin/bash

# ==============================================================================
# Script de Despliegue Automático - BotTrading
# ==============================================================================
# Este script actualiza el código desde GitHub, reconstruye los contenedores
# y aplica las migraciones y archivos estáticos.
# ==============================================================================

set -e # Detiene el script si hay algún error

echo "🚀 Iniciando despliegue de BotTrading..."

# 1. Comprobar que existe el archivo .env
if [ ! -f .env ]; then
    echo "❌ ERROR: No se encontró el archivo .env."
    echo "Por favor, crea el archivo .env con tus variables de entorno en producción."
    exit 1
fi

# 2. Bajar los últimos cambios de GitHub
echo "📥 Descargando los últimos cambios de GitHub..."
git pull origin main

# 3. Construir y levantar contenedores en segundo plano
echo "🐳 Reconstruyendo imágenes y levantando contenedores con Docker..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# 4. Recolectar archivos estáticos para Nginx
echo "📂 Recolectando archivos estáticos de Django..."
docker compose exec -T web python manage.py collectstatic --noinput --settings=config.settings.prod

echo "✅ ¡Despliegue completado con éxito!"
echo "🌐 Tu bot está corriendo en segundo plano."
echo "Para ver los logs en tiempo real, ejecuta: docker compose logs -f web"
