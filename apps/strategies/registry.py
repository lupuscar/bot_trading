import inspect
import importlib
import pkgutil
import sys

def discover_strategies():
    """
    Escanea dinámicamente el paquete implementations y devuelve 
    una lista de tuplas (path_de_la_clase, nombre_visible) 
    para poblar los selectores en las vistas.
    """
    from apps.strategies.base import BaseStrategy
    import apps.strategies.implementations as implementations_pkg
    
    strategy_choices = []
    
    # Recorrer todos los submódulos dentro del paquete implementations
    for _, module_name, _ in pkgutil.iter_modules(implementations_pkg.__path__):
        full_module_name = f"apps.strategies.implementations.{module_name}"
        
        try:
            # Importar el módulo si no está importado
            if full_module_name not in sys.modules:
                importlib.import_module(full_module_name)
            
            module = sys.modules[full_module_name]
            
            # Buscar clases dentro del módulo que hereden de BaseStrategy
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Asegurarse de que obj pertenece a este módulo (no es importado)
                # y que es una subclase de BaseStrategy (pero no BaseStrategy en sí)
                if obj.__module__ == full_module_name and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                    # Usar el atributo DISPLAY_NAME si existe, o el nombre de la clase
                    display_name = getattr(obj, 'DISPLAY_NAME', obj.__name__)
                    class_path = f"{full_module_name}.{obj.__name__}"
                    strategy_choices.append((class_path, display_name))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error cargando estrategias del módulo {full_module_name}: {e}")
            
    return sorted(strategy_choices, key=lambda x: x[1])
