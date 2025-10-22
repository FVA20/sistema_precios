from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmpresaViewSet, SucursalViewSet, LineaArticuloViewSet,
    GrupoArticuloViewSet, ArticuloViewSet, ListaPrecioViewSet,
    PrecioArticuloViewSet, ReglaPrecioViewSet, CombinacionProductoViewSet,
    AuditoriaPreciosViewSet, CalculoPrecioView, CalculoPrecioMultipleView,
    RegistrarDescuentoProveedorView
)

# Configurar router
router = DefaultRouter()
router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'sucursales', SucursalViewSet, basename='sucursal')
router.register(r'lineas-articulos', LineaArticuloViewSet, basename='linea-articulo')
router.register(r'grupos-articulos', GrupoArticuloViewSet, basename='grupo-articulo')
router.register(r'articulos', ArticuloViewSet, basename='articulo')
router.register(r'listas-precios', ListaPrecioViewSet, basename='lista-precio')
router.register(r'precios-articulos', PrecioArticuloViewSet, basename='precio-articulo')
router.register(r'reglas-precios', ReglaPrecioViewSet, basename='regla-precio')
router.register(r'combinaciones', CombinacionProductoViewSet, basename='combinacion')
router.register(r'auditoria', AuditoriaPreciosViewSet, basename='auditoria')

# URLs adicionales para cálculo de precios
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Endpoints de cálculo de precios
    path('precios/calcular/', CalculoPrecioView.as_view(), name='calcular-precio'),
    path('precios/calcular-multiple/', CalculoPrecioMultipleView.as_view(), name='calcular-precio-multiple'),
    path('precios/descuento-proveedor/', RegistrarDescuentoProveedorView.as_view(), name='descuento-proveedor'),
]