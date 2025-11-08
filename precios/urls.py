from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
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

# URLs adicionales
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Endpoints de cálculo de precios
    path('precios/calcular/', CalculoPrecioView.as_view(), name='calcular-precio'),
    path('precios/calcular-multiple/', CalculoPrecioMultipleView.as_view(), name='calcular-precio-multiple'),
    path('precios/descuento-proveedor/', RegistrarDescuentoProveedorView.as_view(), name='descuento-proveedor'),
    
    # ============= RUTAS DEL DASHBOARD =============
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/empresas/', views.empresas_list_view, name='empresas-list'),
    path('dashboard/sucursales/', views.sucursales_list_view, name='sucursales-list'),
    path('dashboard/articulos/', views.articulos_list_view, name='articulos-list'),
    path('dashboard/listas-precios/', views.listas_precios_list_view, name='listas-precios-list'),
    path('dashboard/precios-articulos/', views.precios_articulos_list_view, name='precios-articulos-list'),
    path('dashboard/reglas-precios/', views.reglas_precios_list_view, name='reglas-precios-list'),
]