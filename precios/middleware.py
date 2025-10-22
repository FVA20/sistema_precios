import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from .models import AuditoriaPrecios

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware para logging de requests
    """
    def process_request(self, request):
        request.start_time = time.time()
        
        if request.path.startswith('/api/'):
            logger.info(
                f"Request: {request.method} {request.path} "
                f"from {request.META.get('REMOTE_ADDR')}"
            )
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            if request.path.startswith('/api/'):
                logger.info(
                    f"Response: {request.method} {request.path} "
                    f"[{response.status_code}] ({duration:.2f}s)"
                )
        
        return response


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware para auditoría automática de cambios
    Captura el usuario que realiza las operaciones
    """
    def process_request(self, request):
        # Guardar usuario en el request para uso en signals
        if hasattr(request, 'user') and request.user.is_authenticated:
            request._audit_user = request.user.username
        else:
            request._audit_user = 'anonymous'


class CorsCustomMiddleware(MiddlewareMixin):
    """
    Middleware personalizado para CORS
    (Alternativa a django-cors-headers)
    """
    def process_response(self, request, response):
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Middleware simple de rate limiting
    (Para producción usar django-ratelimit)
    """
    # Diccionario para almacenar contadores
    request_counts = {}
    
    def process_request(self, request):
        if not request.path.startswith('/api/'):
            return None
        
        ip = request.META.get('REMOTE_ADDR')
        current_time = time.time()
        
        # Limpiar registros antiguos (más de 1 hora)
        self.request_counts = {
            k: v for k, v in self.request_counts.items()
            if current_time - v['timestamp'] < 3600
        }
        
        # Verificar límite
        if ip in self.request_counts:
            count = self.request_counts[ip]['count']
            
            if count > 1000:  # Límite: 1000 requests por hora
                logger.warning(f"Rate limit exceeded for IP: {ip}")
                return JsonResponse({
                    'error': 'Rate limit exceeded. Try again later.'
                }, status=429)
            
            self.request_counts[ip]['count'] += 1
        else:
            self.request_counts[ip] = {
                'count': 1,
                'timestamp': current_time
            }
        
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware para agregar headers de seguridad
    """
    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Para producción, agregar:
        # response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # response['Content-Security-Policy'] = "default-src 'self'"
        
        return response


class ApiVersionMiddleware(MiddlewareMixin):
    """
    Middleware para manejo de versiones de API
    """
    def process_request(self, request):
        # Extraer versión del header o URL
        api_version = request.META.get('HTTP_X_API_VERSION', 'v1')
        request.api_version = api_version


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Middleware para manejo centralizado de errores
    """
    def process_exception(self, request, exception):
        logger.error(
            f"Error en {request.path}: {str(exception)}",
            exc_info=True
        )
        
        # En producción, no revelar detalles del error
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': 'Internal server error',
                'message': 'An error occurred processing your request'
            }, status=500)
        
        return None


class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware para agregar ID único a cada request
    """
    def process_request(self, request):
        import uuid
        request.request_id = str(uuid.uuid4())
    
    def process_response(self, request, response):
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response


class DatabaseQueryCountMiddleware(MiddlewareMixin):
    """
    Middleware para contar queries en desarrollo
    """
    def process_request(self, request):
        from django.conf import settings
        if settings.DEBUG:
            from django.db import connection
            request._queries_before = len(connection.queries)
    
    def process_response(self, request, response):
        from django.conf import settings
        if settings.DEBUG and hasattr(request, '_queries_before'):
            from django.db import connection
            queries = len(connection.queries) - request._queries_before
            
            if queries > 50:  # Alertar si hay muchas queries
                logger.warning(
                    f"High query count in {request.path}: {queries} queries"
                )
            
            response['X-DB-Query-Count'] = str(queries)
        
        return response


class CacheControlMiddleware(MiddlewareMixin):
    """
    Middleware para control de caché
    """
    def process_response(self, request, response):
        if request.method == 'GET' and request.path.startswith('/api/'):
            # Configurar caché según el endpoint
            if 'listas-precios' in request.path:
                # Listas de precios: cachear por 5 minutos
                response['Cache-Control'] = 'public, max-age=300'
            elif 'articulos' in request.path:
                # Artículos: cachear por 10 minutos
                response['Cache-Control'] = 'public, max-age=600'
            elif 'calcular' in request.path:
                # Cálculos: no cachear
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            else:
                # Por defecto: cachear por 1 minuto
                response['Cache-Control'] = 'public, max-age=60'
        
        return response


# ============= CONFIGURACIÓN EN SETTINGS.PY =============

"""
Para usar estos middleware, agregar a settings.py:

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # ← AGREGAR ESTA LÍNEA
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... el resto igual
]>

# Configuración de logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/precios.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'precios': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
"""