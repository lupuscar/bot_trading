# Estado del Proyecto: BotTrading

## Contexto Actual (Octubre 2026)
Estamos desarrollando un Bot de Trading en Django con soporte para Backtesting, Paper Trading y Live Trading. Utilizamos Celery para tareas en segundo plano y Docker para los contenedores.

## Última Tarea en Progreso: Panel de Configuración Unificado
Objetivo: Migrar la gestión de API Keys (Binance, OpenAI, Gemini) y la gestión del motor del sistema (Celery) desde variables de entorno y paneles sueltos hacia un único **Panel de Configuración Unificado** en la web.

### Progreso:
- [x] Crear modelo `SystemSetting` en `apps/core/models.py` para almacenar pares clave-valor (ej: OPENAI_API_KEY) de forma segura en la base de datos.
- [x] Ejecutar migraciones (`makemigrations` y `migrate`).

### Tareas Pendientes (Siguientes Pasos):
- [x] **Interfaz Web (Dashboard):** Crear la vista y el template HTML (`apps/dashboard/templates/dashboard/settings.html` o similar) con pestañas para:
  - Inteligencia Artificial (OpenRouter habilitado. OpenAI, Gemini, Groq y Ollama deshabilitados temporalmente).
  - Exchanges & Brokers (Binance).
  - Motor del Sistema (Control de Celery).
- [x] **Lógica de Vistas:** Implementar en `apps/dashboard/views.py` la lógica para guardar y leer estos ajustes desde la base de datos.
- [x] **Actualizar Estrategia IA:** Modificar `apps/strategies/implementations/ai_agent.py` para que lea las API keys usando el modelo `SystemSetting` e integrar llamadas a Groq y OpenRouter.
- [x] **Limpieza:** Eliminar la dependencia de estas variables en el `.env` (dejándolo solo para configuraciones core como Redis, DB o secretos de Django).

## Mejoras Recientes (Motor de Estrategias y UX)
- [x] **Auto-descubrimiento de Estrategias:** Creado `apps/strategies/registry.py` para cargar automáticamente cualquier algoritmo que herede de `BaseStrategy` sin tocar `views.py`.
- [x] **Formularios Dinámicos con HTMX:** 
  - Estandarizado `get_parameters_schema()` como método de clase (`@classmethod`).
  - Creado un endpoint HTMX (`/api/params/`) para renderizar inputs dinámicos en lugar de requerir que el usuario escriba JSON crudo al crear o editar estrategias.
- [x] **Robustez IA:** Añadida lógica de expresiones regulares (`regex`) en `AIAgentStrategy` para parsear JSON incluso si modelos de OpenRouter incluyen cabeceras extra (ej. "User Safety: safe").

## Notas Adicionales
*Mantendremos este archivo actualizado para no perder el contexto en caso de que se reinicie el IDE o la sesión.*
