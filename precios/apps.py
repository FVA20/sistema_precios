from django.apps import AppConfig


class PreciosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'precios'
    verbose_name = 'Sistema de Gestión de Precios'
    
    def ready(self):
        """Importar signals cuando la app esté lista"""
        import precios.signals