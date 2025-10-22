import django_filters
from django.db.models import Q
from decimal import Decimal
from .models import (
    Empresa, Sucursal, Articulo, ListaPrecio, PrecioArticulo,
    ReglaPrecio, CombinacionProducto, AuditoriaPrecios
)


class EmpresaFilter(django_filters.FilterSet):
    """Filtros para Empresa"""
    nombre = django_filters.CharFilter(lookup_expr='icontains')
    ruc = django_filters.CharFilter(lookup_expr='exact')
    activo = django_filters.BooleanFilter()
    fecha_desde = django_filters.DateFilter(field_name='fecha_creacion', lookup_expr='gte')
    fecha_hasta = django_filters.DateFilter(field_name='fecha_creacion', lookup_expr='lte')
    
    class Meta:
        model = Empresa
        fields = ['nombre', 'ruc', 'activo']


class SucursalFilter(django_filters.FilterSet):
    """Filtros para Sucursal"""
    empresa = django_filters.NumberFilter()
    nombre = django_filters.CharFilter(lookup_expr='icontains')
    codigo = django_filters.CharFilter(lookup_expr='icontains')
    activo = django_filters.BooleanFilter()
    
    class Meta:
        model = Sucursal
        fields = ['empresa', 'nombre', 'codigo', 'activo']


class ArticuloFilter(django_filters.FilterSet):
    """Filtros avanzados para Artículo"""
    codigo = django_filters.CharFilter(lookup_expr='icontains')
    nombre = django_filters.CharFilter(lookup_expr='icontains')
    grupo = django_filters.NumberFilter()
    linea = django_filters.NumberFilter(field_name='grupo__linea')
    activo = django_filters.BooleanFilter()
    
    # Filtros por rango de costo
    costo_min = django_filters.NumberFilter(field_name='ultimo_costo', lookup_expr='gte')
    costo_max = django_filters.NumberFilter(field_name='ultimo_costo', lookup_expr='lte')
    
    # Búsqueda general
    busqueda = django_filters.CharFilter(method='buscar_general')
    
    def buscar_general(self, queryset, name, value):
        """Búsqueda en múltiples campos"""
        return queryset.filter(
            Q(codigo__icontains=value) |
            Q(nombre__icontains=value) |
            Q(descripcion__icontains=value)
        )
    
    class Meta:
        model = Articulo
        fields = ['codigo', 'nombre', 'grupo', 'activo']


class ListaPrecioFilter(django_filters.FilterSet):
    """Filtros avanzados para Lista de Precios"""
    empresa = django_filters.NumberFilter()
    sucursal = django_filters.NumberFilter()
    nombre = django_filters.CharFilter(lookup_expr='icontains')
    tipo = django_filters.ChoiceFilter(choices=ListaPrecio.TIPO_CHOICES)
    canal = django_filters.ChoiceFilter(choices=ListaPrecio.CANAL_CHOICES)
    activo = django_filters.BooleanFilter()
    
    # Filtros por fechas
    vigente_en = django_filters.DateFilter(method='filtrar_vigente_en')
    fecha_inicio_desde = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='gte')
    fecha_inicio_hasta = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='lte')
    
    # Filtro para listas con/sin fecha fin
    sin_fecha_fin = django_filters.BooleanFilter(method='filtrar_sin_fecha_fin')
    
    def filtrar_vigente_en(self, queryset, name, value):
        """Filtrar listas vigentes en una fecha específica"""
        return queryset.filter(
            activo=True,
            fecha_inicio__lte=value
        ).filter(
            Q(fecha_fin__gte=value) | Q(fecha_fin__isnull=True)
        )
    
    def filtrar_sin_fecha_fin(self, queryset, name, value):
        """Filtrar listas sin fecha de fin (indefinidas)"""
        if value:
            return queryset.filter(fecha_fin__isnull=True)
        else:
            return queryset.filter(fecha_fin__isnull=False)
    
    class Meta:
        model = ListaPrecio
        fields = ['empresa', 'sucursal', 'tipo', 'canal', 'activo']


class PrecioArticuloFilter(django_filters.FilterSet):
    """Filtros avanzados para Precio de Artículo"""
    lista_precio = django_filters.NumberFilter()
    articulo = django_filters.NumberFilter()
    bajo_costo = django_filters.BooleanFilter()
    autorizado_bajo_costo = django_filters.BooleanFilter()
    
    # Filtros por rangos de precio
    precio_min = django_filters.NumberFilter(field_name='precio_base', lookup_expr='gte')
    precio_max = django_filters.NumberFilter(field_name='precio_base', lookup_expr='lte')
    
    # Filtros por margen
    margen_min = django_filters.NumberFilter(method='filtrar_margen_min')
    margen_max = django_filters.NumberFilter(method='filtrar_margen_max')
    
    # Filtro por descuento de proveedor
    con_descuento_proveedor = django_filters.BooleanFilter(method='filtrar_con_descuento')
    
    # Filtro por empresa
    empresa = django_filters.NumberFilter(field_name='lista_precio__empresa')
    
    # Filtro por grupo/línea de artículo
    grupo_articulo = django_filters.NumberFilter(field_name='articulo__grupo')
    linea_articulo = django_filters.NumberFilter(field_name='articulo__grupo__linea')
    
    def filtrar_margen_min(self, queryset, name, value):
        """Filtrar por margen mínimo de ganancia"""
        # Calcular margen: (precio_base - costo) / costo * 100
        from django.db.models import F, ExpressionWrapper, FloatField
        from django.db.models.functions import Cast
        
        return queryset.annotate(
            margen=ExpressionWrapper(
                (F('precio_base') - F('articulo__ultimo_costo')) / F('articulo__ultimo_costo') * 100,
                output_field=FloatField()
            )
        ).filter(margen__gte=value)
    
    def filtrar_margen_max(self, queryset, name, value):
        """Filtrar por margen máximo de ganancia"""
        from django.db.models import F, ExpressionWrapper, FloatField
        
        return queryset.annotate(
            margen=ExpressionWrapper(
                (F('precio_base') - F('articulo__ultimo_costo')) / F('articulo__ultimo_costo') * 100,
                output_field=FloatField()
            )
        ).filter(margen__lte=value)
    
    def filtrar_con_descuento(self, queryset, name, value):
        """Filtrar artículos con/sin descuento de proveedor"""
        if value:
            return queryset.filter(descuento_proveedor__gt=0)
        else:
            return queryset.filter(descuento_proveedor=0)
    
    class Meta:
        model = PrecioArticulo
        fields = ['lista_precio', 'articulo', 'bajo_costo', 'autorizado_bajo_costo']


class ReglaPrecioFilter(django_filters.FilterSet):
    """Filtros para Regla de Precio"""
    lista_precio = django_filters.NumberFilter()
    tipo_regla = django_filters.ChoiceFilter(choices=ReglaPrecio.TIPO_REGLA_CHOICES)
    tipo_descuento = django_filters.ChoiceFilter(choices=ReglaPrecio.TIPO_DESCUENTO_CHOICES)
    canal = django_filters.ChoiceFilter(choices=ListaPrecio.CANAL_CHOICES)
    activo = django_filters.BooleanFilter()
    
    # Filtros por línea/grupo
    linea_articulo = django_filters.NumberFilter()
    grupo_articulo = django_filters.NumberFilter()
    
    # Filtro por prioridad
    prioridad_min = django_filters.NumberFilter(field_name='prioridad', lookup_expr='gte')
    prioridad_max = django_filters.NumberFilter(field_name='prioridad', lookup_expr='lte')
    
    # Filtros por descuento
    descuento_min = django_filters.NumberFilter(field_name='valor_descuento', lookup_expr='gte')
    descuento_max = django_filters.NumberFilter(field_name='valor_descuento', lookup_expr='lte')
    
    # Filtro por empresa
    empresa = django_filters.NumberFilter(field_name='lista_precio__empresa')
    
    class Meta:
        model = ReglaPrecio
        fields = ['lista_precio', 'tipo_regla', 'tipo_descuento', 'activo']


class CombinacionProductoFilter(django_filters.FilterSet):
    """Filtros para Combinación de Productos"""
    lista_precio = django_filters.NumberFilter()
    activo = django_filters.BooleanFilter()
    tipo_descuento = django_filters.ChoiceFilter(choices=ReglaPrecio.TIPO_DESCUENTO_CHOICES)
    
    # Búsqueda por nombre
    nombre = django_filters.CharFilter(lookup_expr='icontains')
    
    # Filtros por cantidad
    cantidad_min = django_filters.NumberFilter(field_name='cantidad_minima', lookup_expr='gte')
    cantidad_max = django_filters.NumberFilter(field_name='cantidad_minima', lookup_expr='lte')
    
    # Filtros por descuento
    descuento_min = django_filters.NumberFilter(field_name='valor_descuento', lookup_expr='gte')
    descuento_max = django_filters.NumberFilter(field_name='valor_descuento', lookup_expr='lte')
    
    # Filtro por empresa
    empresa = django_filters.NumberFilter(field_name='lista_precio__empresa')
    
    class Meta:
        model = CombinacionProducto
        fields = ['lista_precio', 'activo', 'tipo_descuento']


class AuditoriaPreciosFilter(django_filters.FilterSet):
    """Filtros para Auditoría de Precios"""
    tipo_operacion = django_filters.ChoiceFilter(choices=AuditoriaPrecios.TIPO_OPERACION_CHOICES)
    tabla = django_filters.CharFilter(lookup_expr='exact')
    registro_id = django_filters.NumberFilter()
    usuario = django_filters.CharFilter(lookup_expr='icontains')
    
    # Filtros por fecha
    fecha_desde = django_filters.DateTimeFilter(field_name='fecha_operacion', lookup_expr='gte')
    fecha_hasta = django_filters.DateTimeFilter(field_name='fecha_operacion', lookup_expr='lte')
    
    # Filtro para buscar cambios específicos
    contiene_texto = django_filters.CharFilter(method='filtrar_por_contenido')
    
    def filtrar_por_contenido(self, queryset, name, value):
        """Buscar en los datos JSON de la auditoría"""
        from django.contrib.postgres.search import SearchVector
        
        # Para PostgreSQL con JSONB
        return queryset.filter(
            Q(datos_anteriores__icontains=value) |
            Q(datos_nuevos__icontains=value)
        )
    
    class Meta:
        model = AuditoriaPrecios
        fields = ['tipo_operacion', 'tabla', 'registro_id', 'usuario']


# ============= ORDENAMIENTO PERSONALIZADO =============

class ArticuloOrdering(django_filters.OrderingFilter):
    """Ordenamiento personalizado para artículos"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra['choices'] += [
            ('margen', 'Margen de Ganancia (Ascendente)'),
            ('-margen', 'Margen de Ganancia (Descendente)'),
            ('stock', 'Stock Disponible'),
            ('-stock', 'Stock Disponible (Descendente)'),
        ]


class PrecioArticuloOrdering(django_filters.OrderingFilter):
    """Ordenamiento personalizado para precios"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra['choices'] += [
            ('margen', 'Margen (Ascendente)'),
            ('-margen', 'Margen (Descendente)'),
            ('precio_base', 'Precio Base (Ascendente)'),
            ('-precio_base', 'Precio Base (Descendente)'),
        ]


# ============= EJEMPLO DE USO EN VIEWS =============

"""
Para usar estos filtros en tus ViewSets:

from .filters import ArticuloFilter, PrecioArticuloFilter

class ArticuloViewSet(viewsets.ModelViewSet):
    queryset = Articulo.objects.all()
    serializer_class = ArticuloSerializer
    filterset_class = ArticuloFilter
    
    # También puedes agregar búsqueda y ordenamiento
    search_fields = ['codigo', 'nombre', 'descripcion']
    ordering_fields = ['codigo', 'nombre', 'ultimo_costo']
    ordering = ['codigo']

Ejemplos de uso en la API:
/api/articulos/?codigo=LAP
/api/articulos/?nombre__icontains=laptop
/api/articulos/?costo_min=1000&costo_max=5000
/api/articulos/?busqueda=intel
/api/articulos/?ordering=-ultimo_costo

/api/precios-articulos/?bajo_costo=true
/api/precios-articulos/?margen_min=20&margen_max=50
/api/precios-articulos/?empresa=1&grupo_articulo=3
/api/precios-articulos/?precio_min=100&precio_max=500

/api/listas-precios/?vigente_en=2024-10-21
/api/listas-precios/?tipo=MAYORISTA&activo=true
"""