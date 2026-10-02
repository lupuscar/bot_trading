FROM python:3.12-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copiar el proyecto
COPY . .

# Recoger archivos estáticos
RUN python manage.py collectstatic --noinput --settings=config.settings.prod 2>/dev/null || true

# Puerto
EXPOSE 8000

# Comando por defecto
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
