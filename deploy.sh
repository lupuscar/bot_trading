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

# 3. Limpiar cachés de Python locales (evita fantasmas en Docker)
echo "🧹 Limpiando archivos de caché (.pyc y __pycache__)..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 4. Construir y levantar contenedores
# Usamos --build --no-cache para asegurar que CERO código antiguo se cuele por culpa del caché de Docker.
echo "🐳 Reconstruyendo imágenes y levantando contenedores con Docker (Sin Caché)..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Recolectar archivos estáticos para Nginx
echo "📂 Recolectando archivos estáticos de Django..."
docker compose exec -T web python manage.py collectstatic --noinput --settings=config.settings.prod

# 5. Crear usuario administrador por defecto si no existe
echo "👤 Comprobando/Creando usuario administrador por defecto..."
docker compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@bottrading.com', 'admin123')"

echo "✅ ¡Despliegue completado con éxito!"
echo "🌐 Tu bot está corriendo en segundo plano."
echo "Para ver los logs en tiempo real, ejecuta: docker compose logs -f web"
