from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permiso personalizado: solo admin puede modificar, otros solo lectura
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class EsPropietarioEmpresa(permissions.BasePermission):
    """
    Permiso personalizado: verificar que el usuario pertenece a la empresa
    """
    def has_object_permission(self, request, view, obj):
        # Superusuarios tienen acceso completo
        if request.user.is_superuser:
            return True
        
        # Verificar que el usuario pertenezca a la empresa del objeto
        if hasattr(obj, 'empresa'):
            return obj.empresa == request.user.empresa
        
        return False


class PuedeModificarPrecios(permissions.BasePermission):
    """
    Permiso personalizado: solo usuarios con rol de gestor de precios
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.groups.filter(name='Gestores de Precios').exists())
        )


class PuedeAutorizarBajoCosto(permissions.BasePermission):
    """
    Permiso personalizado: solo gerentes pueden autorizar precios bajo costo
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_superuser or 
             request.user.groups.filter(name='Gerentes').exists())
        )


class PuedeVerAuditoria(permissions.BasePermission):
    """
    Permiso personalizado: solo ciertos roles pueden ver auditoría
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.groups.filter(name__in=['Auditores', 'Gerentes']).exists())
        )


# ============= AUTENTICACIÓN CON JWT (opcional) =============

"""
Para usar JWT, instalar:
pip install djangorestframework-simplejwt

Luego agregar a settings.py:

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

Y configurar URLs:
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
"""


# ============= THROTTLING (RATE LIMITING) =============

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class CalculoPrecioThrottle(UserRateThrottle):
    """
    Rate limiting específico para cálculo de precios:
    - Usuarios autenticados: 1000 requests/hora
    """
    rate = '1000/hour'


class CalculoPrecioAnonThrottle(AnonRateThrottle):
    """
    Rate limiting para usuarios anónimos:
    - 100 requests/hora
    """
    rate = '100/hour'


# Para usar throttling, agregar a settings.py:
"""
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'calculo_precio': '1000/hour',
        'calculo_precio_anon': '100/hour',
    }
}
"""