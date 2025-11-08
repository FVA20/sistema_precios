from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from decimal import Decimal
from django.shortcuts import render
from django.db.models import Count

from .models import (
    Empresa, Sucursal, LineaArticulo, GrupoArticulo, Articulo,
    ListaPrecio, PrecioArticulo, ReglaPrecio, CombinacionProducto,
    DetalleCombinacionProducto, AuditoriaPrecios
)
from .serializers import (
    EmpresaSerializer, SucursalSerializer, LineaArticuloSerializer,
    GrupoArticuloSerializer, ArticuloSerializer, ListaPrecioSerializer,
    PrecioArticuloSerializer, ReglaPrecioSerializer,
    CombinacionProductoSerializer, DetalleCombinacionSerializer,
    AuditoriaPreciosSerializer, CalculoPrecioRequestSerializer,
    CalculoPrecioResponseSerializer, CalculoPrecioMultipleRequestSerializer,
    ListaPrecioConPreciosSerializer, DescuentoProveedorSerializer
)
from .services import PrecioService


class EmpresaViewSet(viewsets.ModelViewSet):
    """ViewSet para Empresas"""
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    filterset_fields = ['activo']
    search_fields = ['nombre', 'ruc']


class SucursalViewSet(viewsets.ModelViewSet):
    """ViewSet para Sucursales"""
    queryset = Sucursal.objects.select_related('empresa').all()
    serializer_class = SucursalSerializer
    filterset_fields = ['empresa', 'activo']
    search_fields = ['nombre', 'codigo']


class LineaArticuloViewSet(viewsets.ModelViewSet):
    """ViewSet para Líneas de Artículos"""
    queryset = LineaArticulo.objects.all()
    serializer_class = LineaArticuloSerializer
    filterset_fields = ['activo']
    search_fields = ['nombre', 'codigo']


class GrupoArticuloViewSet(viewsets.ModelViewSet):
    """ViewSet para Grupos de Artículos"""
    queryset = GrupoArticulo.objects.select_related('linea').all()
    serializer_class = GrupoArticuloSerializer
    filterset_fields = ['linea', 'activo']
    search_fields = ['nombre', 'codigo']


class ArticuloViewSet(viewsets.ModelViewSet):
    """ViewSet para Artículos"""
    queryset = Articulo.objects.select_related('grupo__linea').all()
    serializer_class = ArticuloSerializer
    filterset_fields = ['grupo', 'activo']
    search_fields = ['codigo', 'nombre']
    
    @action(detail=True, methods=['get'])
    def precios(self, request, pk=None):
        """Obtener todos los precios de un artículo"""
        articulo = self.get_object()
        precios = PrecioArticulo.objects.filter(articulo=articulo).select_related(
            'lista_precio__empresa',
            'lista_precio__sucursal'
        )
        serializer = PrecioArticuloSerializer(precios, many=True)
        return Response(serializer.data)


class ListaPrecioViewSet(viewsets.ModelViewSet):
    """ViewSet para Listas de Precios"""
    queryset = ListaPrecio.objects.select_related('empresa', 'sucursal').all()
    serializer_class = ListaPrecioSerializer
    filterset_fields = ['empresa', 'sucursal', 'tipo', 'canal', 'activo']
    search_fields = ['nombre']
    
    @action(detail=False, methods=['get'])
    def vigentes(self, request):
        """Obtener listas vigentes"""
        empresa_id = request.query_params.get('empresa_id')
        sucursal_id = request.query_params.get('sucursal_id')
        canal = request.query_params.get('canal')
        
        if not empresa_id:
            return Response(
                {'error': 'empresa_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        lista = PrecioService.obtener_lista_vigente(
            empresa_id=int(empresa_id),
            sucursal_id=int(sucursal_id) if sucursal_id else None,
            canal=canal
        )
        
        if lista:
            serializer = ListaPrecioConPreciosSerializer(lista)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'No se encontró lista vigente'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def detalle_completo(self, request, pk=None):
        """Obtener lista con precios, reglas y combinaciones"""
        lista = self.get_object()
        serializer = ListaPrecioConPreciosSerializer(lista)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def duplicar(self, request, pk=None):
        """Duplicar una lista de precios"""
        lista_original = self.get_object()
        
        # Crear nueva lista
        nueva_lista = ListaPrecio.objects.create(
            empresa=lista_original.empresa,
            sucursal=lista_original.sucursal,
            nombre=f"{lista_original.nombre} (Copia)",
            tipo=lista_original.tipo,
            canal=lista_original.canal,
            fecha_inicio=request.data.get('fecha_inicio'),
            fecha_fin=request.data.get('fecha_fin'),
            activo=False
        )
        
        # Copiar precios
        precios_originales = PrecioArticulo.objects.filter(lista_precio=lista_original)
        for precio in precios_originales:
            PrecioArticulo.objects.create(
                lista_precio=nueva_lista,
                articulo=precio.articulo,
                precio_base=precio.precio_base,
                bajo_costo=precio.bajo_costo,
                autorizado_bajo_costo=precio.autorizado_bajo_costo,
                descuento_proveedor=precio.descuento_proveedor
            )
        
        # Copiar reglas
        reglas_originales = ReglaPrecio.objects.filter(lista_precio=lista_original)
        for regla in reglas_originales:
            ReglaPrecio.objects.create(
                lista_precio=nueva_lista,
                nombre=regla.nombre,
                tipo_regla=regla.tipo_regla,
                prioridad=regla.prioridad,
                canal=regla.canal,
                linea_articulo=regla.linea_articulo,
                grupo_articulo=regla.grupo_articulo,
                cantidad_minima=regla.cantidad_minima,
                cantidad_maxima=regla.cantidad_maxima,
                monto_minimo=regla.monto_minimo,
                monto_maximo=regla.monto_maximo,
                tipo_descuento=regla.tipo_descuento,
                valor_descuento=regla.valor_descuento,
                activo=regla.activo
            )
        
        serializer = ListaPrecioSerializer(nueva_lista)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PrecioArticuloViewSet(viewsets.ModelViewSet):
    """ViewSet para Precios de Artículos"""
    queryset = PrecioArticulo.objects.select_related(
        'lista_precio',
        'articulo__grupo__linea'
    ).all()
    serializer_class = PrecioArticuloSerializer
    filterset_fields = ['lista_precio', 'articulo', 'bajo_costo']
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def carga_masiva(self, request):
        """Carga masiva de precios"""
        lista_precio_id = request.data.get('lista_precio_id')
        precios_data = request.data.get('precios', [])
        
        if not lista_precio_id or not precios_data:
            return Response(
                {'error': 'lista_precio_id y precios son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lista_precio = ListaPrecio.objects.get(pk=lista_precio_id)
        except ListaPrecio.DoesNotExist:
            return Response(
                {'error': 'Lista de precios no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        precios_creados = []
        errores = []
        
        for idx, precio_data in enumerate(precios_data):
            try:
                articulo_id = precio_data.get('articulo_id')
                precio_base = Decimal(str(precio_data.get('precio_base')))
                
                articulo = Articulo.objects.get(pk=articulo_id)
                
                precio, created = PrecioArticulo.objects.update_or_create(
                    lista_precio=lista_precio,
                    articulo=articulo,
                    defaults={
                        'precio_base': precio_base,
                        'bajo_costo': precio_data.get('bajo_costo', False),
                        'autorizado_bajo_costo': precio_data.get('autorizado_bajo_costo', False),
                        'descuento_proveedor': precio_data.get('descuento_proveedor', 0),
                    }
                )
                precios_creados.append(precio.id)
                
            except Exception as e:
                errores.append({
                    'indice': idx,
                    'articulo_id': precio_data.get('articulo_id'),
                    'error': str(e)
                })
        
        return Response({
            'mensaje': f'{len(precios_creados)} precios procesados',
            'precios_creados': precios_creados,
            'errores': errores
        }, status=status.HTTP_201_CREATED)


class ReglaPrecioViewSet(viewsets.ModelViewSet):
    """ViewSet para Reglas de Precio"""
    queryset = ReglaPrecio.objects.select_related(
        'lista_precio',
        'linea_articulo',
        'grupo_articulo'
    ).all()
    serializer_class = ReglaPrecioSerializer
    filterset_fields = ['lista_precio', 'tipo_regla', 'activo']


class CombinacionProductoViewSet(viewsets.ModelViewSet):
    """ViewSet para Combinaciones de Productos"""
    queryset = CombinacionProducto.objects.prefetch_related('detalles').all()
    serializer_class = CombinacionProductoSerializer
    filterset_fields = ['lista_precio', 'activo']
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def agregar_detalle(self, request, pk=None):
        """Agregar detalle a una combinación"""
        combinacion = self.get_object()
        serializer = DetalleCombinacionSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(combinacion=combinacion)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuditoriaPreciosViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para Auditoría (solo lectura)"""
    queryset = AuditoriaPrecios.objects.all()
    serializer_class = AuditoriaPreciosSerializer
    filterset_fields = ['tipo_operacion', 'tabla']
    
    @action(detail=False, methods=['get'])
    def por_articulo(self, request):
        """Auditoría de un artículo específico"""
        articulo_id = request.query_params.get('articulo_id')
        
        if not articulo_id:
            return Response(
                {'error': 'articulo_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        auditorias = AuditoriaPrecios.objects.filter(
            registro_id=articulo_id,
            tabla__in=['precio_articulo', 'precio_calculo']
        ).order_by('-fecha_operacion')
        
        serializer = self.get_serializer(auditorias, many=True)
        return Response(serializer.data)


# ============= VISTAS PARA CÁLCULO DE PRECIOS =============

class CalculoPrecioView(APIView):
    """
    Vista para calcular precio de un artículo
    
    POST /api/precios/calcular/
    {
        "empresa_id": 1,
        "articulo_id": 10,
        "cantidad": 5,
        "sucursal_id": 2,  // opcional
        "canal": "TIENDA",  // opcional
        "monto_pedido": 1000,  // opcional
        "items_pedido": [  // opcional
            {"articulo_id": 10, "cantidad": 5},
            {"articulo_id": 15, "cantidad": 3}
        ]
    }
    """
    
    def post(self, request):
        serializer = CalculoPrecioRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            resultado = PrecioService.calcular_precio(
                empresa_id=serializer.validated_data['empresa_id'],
                articulo_id=serializer.validated_data['articulo_id'],
                cantidad=serializer.validated_data['cantidad'],
                sucursal_id=serializer.validated_data.get('sucursal_id'),
                canal=serializer.validated_data.get('canal'),
                monto_pedido=serializer.validated_data.get('monto_pedido'),
                items_pedido=serializer.validated_data.get('items_pedido'),
                fecha=serializer.validated_data.get('fecha')
            )
            
            response_serializer = CalculoPrecioResponseSerializer(data=resultado)
            response_serializer.is_valid(raise_exception=True)
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error inesperado: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CalculoPrecioMultipleView(APIView):
    """
    Vista para calcular precio de múltiples artículos
    
    POST /api/precios/calcular-multiple/
    {
        "empresa_id": 1,
        "sucursal_id": 2,  // opcional
        "canal": "ONLINE",  // opcional
        "items": [
            {"articulo_id": 10, "cantidad": 5},
            {"articulo_id": 15, "cantidad": 3},
            {"articulo_id": 20, "cantidad": 2}
        ]
    }
    """
    
    def post(self, request):
        serializer = CalculoPrecioMultipleRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        empresa_id = serializer.validated_data['empresa_id']
        sucursal_id = serializer.validated_data.get('sucursal_id')
        canal = serializer.validated_data.get('canal')
        items = serializer.validated_data['items']
        fecha = serializer.validated_data.get('fecha')
        
        # Calcular monto total del pedido
        monto_total = Decimal('0')
        for item in items:
            articulo = Articulo.objects.get(pk=item['articulo_id'])
            lista = PrecioService.obtener_lista_vigente(empresa_id, sucursal_id, canal, fecha)
            if lista:
                precio_articulo = PrecioArticulo.objects.filter(
                    lista_precio=lista,
                    articulo=articulo
                ).first()
                if precio_articulo:
                    monto_total += precio_articulo.precio_base * item['cantidad']
        
        resultados = []
        errores = []
        
        for item in items:
            try:
                resultado = PrecioService.calcular_precio(
                    empresa_id=empresa_id,
                    articulo_id=item['articulo_id'],
                    cantidad=item['cantidad'],
                    sucursal_id=sucursal_id,
                    canal=canal,
                    monto_pedido=monto_total,
                    items_pedido=items,
                    fecha=fecha
                )
                resultados.append(resultado)
                
            except Exception as e:
                errores.append({
                    'articulo_id': item['articulo_id'],
                    'error': str(e)
                })
        
        return Response({
            'monto_total': float(monto_total),
            'total_items': len(items),
            'items_procesados': len(resultados),
            'resultados': resultados,
            'errores': errores
        }, status=status.HTTP_200_OK)


class RegistrarDescuentoProveedorView(APIView):
    """
    Vista para registrar descuento de proveedor
    
    POST /api/precios/descuento-proveedor/
    {
        "precio_articulo_id": 123,
        "descuento_porcentaje": 60,
        "observaciones": "Descuento especial por liquidación"
    }
    """
    
    def post(self, request):
        serializer = DescuentoProveedorSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            precio_articulo = PrecioService.registrar_descuento_proveedor(
                precio_articulo_id=serializer.validated_data['precio_articulo_id'],
                descuento_porcentaje=serializer.validated_data['descuento_porcentaje'],
                observaciones=serializer.validated_data.get('observaciones', '')
            )
            
            response_serializer = PrecioArticuloSerializer(precio_articulo)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except PrecioArticulo.DoesNotExist:
            return Response(
                {'error': 'Precio de artículo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============= VISTAS PARA EL DASHBOARD =============
# VERSIÓN FINAL CON NOMBRES DE RELACIONES CORRECTOS

def dashboard_view(request):
    """Vista principal del dashboard"""
    
    # Obtener estadísticas generales
    stats = {
        'total_empresas': Empresa.objects.count(),
        'total_articulos': Articulo.objects.count(),
        'total_listas': ListaPrecio.objects.count(),
        'total_precios': PrecioArticulo.objects.count(),
    }
    
    # Obtener listas de precios activas con información agregada
    listas_precios = ListaPrecio.objects.filter(activo=True).annotate(
        total_articulos=Count('precios')
    ).select_related('empresa', 'sucursal')[:5]
    
    # Formatear datos de listas de precios
    listas_data = []
    for lista in listas_precios:
        # Obtener nombre de empresa de forma segura
        empresa_nombre = 'N/A'
        if lista.empresa:
            if hasattr(lista.empresa, 'razon_social'):
                empresa_nombre = lista.empresa.razon_social
            elif hasattr(lista.empresa, 'nombre'):
                empresa_nombre = lista.empresa.nombre
            else:
                empresa_nombre = str(lista.empresa)
        
        listas_data.append({
            'id': lista.id,
            'empresa_nombre': empresa_nombre,
            'nombre': lista.nombre,
            'tipo': lista.tipo,
            'canal': lista.canal if hasattr(lista, 'canal') and lista.canal else 'General',
            'total_articulos': lista.total_articulos,
            'activo': lista.activo,
        })
    
    # Artículos recientes
    articulos_recientes = Articulo.objects.select_related('grupo__linea').order_by('-id')[:5]
    articulos_data = []
    for articulo in articulos_recientes:
        articulos_data.append({
            'codigo': articulo.codigo,
            'descripcion': articulo.nombre,
            'linea_nombre': articulo.grupo.linea.nombre if articulo.grupo and articulo.grupo.linea else 'Sin línea',
            'activo': articulo.activo,
        })
    
    # Empresas con conteo de sucursales
    empresas = Empresa.objects.annotate(
        total_sucursales=Count('sucursales')  # CORREGIDO: 'sucursales' en plural
    )[:5]
    
    empresas_data = []
    for empresa in empresas:
        # Obtener RUC y nombre de forma segura
        ruc = empresa.ruc if hasattr(empresa, 'ruc') else 'N/A'
        
        if hasattr(empresa, 'razon_social'):
            nombre = empresa.razon_social
        elif hasattr(empresa, 'nombre'):
            nombre = empresa.nombre
        else:
            nombre = str(empresa)
        
        empresas_data.append({
            'ruc': ruc,
            'razon_social': nombre,
            'total_sucursales': empresa.total_sucursales,
        })
    
    context = {
        'stats': stats,
        'listas_precios': listas_data,
        'articulos_recientes': articulos_data,
        'empresas': empresas_data,
    }
    
    return render(request, 'dashboard.html', context)


def empresas_list_view(request):
    """Vista de listado de empresas"""
    empresas = Empresa.objects.annotate(
        total_sucursales=Count('sucursales'),  # CORREGIDO: 'sucursales' en plural
        total_listas=Count('listas_precios')  # CORREGIDO: 'listas_precios' en lugar de 'listaprecio'
    ).order_by('-id')
    
    empresas_data = []
    for empresa in empresas:
        # Obtener campos de forma segura
        ruc = empresa.ruc if hasattr(empresa, 'ruc') else 'N/A'
        
        if hasattr(empresa, 'razon_social'):
            razon_social = empresa.razon_social
        elif hasattr(empresa, 'nombre'):
            razon_social = empresa.nombre
        else:
            razon_social = str(empresa)
        
        if hasattr(empresa, 'nombre_comercial'):
            nombre_comercial = empresa.nombre_comercial
        else:
            nombre_comercial = razon_social
        
        empresas_data.append({
            'id': empresa.id,
            'ruc': ruc,
            'razon_social': razon_social,
            'nombre_comercial': nombre_comercial,
            'total_sucursales': empresa.total_sucursales,
            'total_listas': empresa.total_listas,
            'activo': empresa.activo,
        })
    
    context = {
        'empresas': empresas_data,
        'total': empresas.count(),
    }
    
    return render(request, 'empresas_list.html', context)


def sucursales_list_view(request):
    """Vista de listado de sucursales"""
    sucursales = Sucursal.objects.select_related('empresa').order_by('-id')
    
    sucursales_data = []
    for sucursal in sucursales:
        # Obtener nombre de empresa de forma segura
        if sucursal.empresa:
            if hasattr(sucursal.empresa, 'razon_social'):
                empresa_nombre = sucursal.empresa.razon_social
            elif hasattr(sucursal.empresa, 'nombre'):
                empresa_nombre = sucursal.empresa.nombre
            else:
                empresa_nombre = str(sucursal.empresa)
        else:
            empresa_nombre = 'N/A'
        
        sucursales_data.append({
            'id': sucursal.id,
            'codigo': sucursal.codigo,
            'nombre': sucursal.nombre,
            'empresa_nombre': empresa_nombre,
            'direccion': sucursal.direccion if hasattr(sucursal, 'direccion') else 'N/A',
            'telefono': sucursal.telefono if hasattr(sucursal, 'telefono') else 'N/A',
            'activo': sucursal.activo,
        })
    
    context = {
        'sucursales': sucursales_data,
        'total': sucursales.count(),
    }
    
    return render(request, 'sucursales_list.html', context)


def articulos_list_view(request):
    """Vista de listado de artículos"""
    articulos = Articulo.objects.select_related('grupo__linea').order_by('-id')
    
    articulos_data = []
    for articulo in articulos:
        articulos_data.append({
            'id': articulo.id,
            'codigo': articulo.codigo,
            'descripcion': articulo.nombre,
            'linea_nombre': articulo.grupo.linea.nombre if articulo.grupo and articulo.grupo.linea else 'N/A',
            'grupo_nombre': articulo.grupo.nombre if articulo.grupo else 'N/A',
            'unidad_medida': articulo.unidad_medida if hasattr(articulo, 'unidad_medida') else 'UND',
            'activo': articulo.activo,
        })
    
    context = {
        'articulos': articulos_data,
        'total': articulos.count(),
    }
    
    return render(request, 'articulos_list.html', context)


def listas_precios_list_view(request):
    """Vista de listado de listas de precios"""
    listas = ListaPrecio.objects.select_related('empresa', 'sucursal').annotate(
        total_articulos=Count('precios')
    ).order_by('-id')
    
    listas_data = []
    for lista in listas:
        # Obtener nombre de empresa de forma segura
        if lista.empresa:
            if hasattr(lista.empresa, 'razon_social'):
                empresa_nombre = lista.empresa.razon_social
            elif hasattr(lista.empresa, 'nombre'):
                empresa_nombre = lista.empresa.nombre
            else:
                empresa_nombre = str(lista.empresa)
        else:
            empresa_nombre = 'N/A'
        
        listas_data.append({
            'id': lista.id,
            'empresa_nombre': empresa_nombre,
            'sucursal_nombre': lista.sucursal.nombre if lista.sucursal else 'Todas',
            'nombre': lista.nombre,
            'tipo': lista.tipo,
            'canal': lista.canal if hasattr(lista, 'canal') and lista.canal else 'General',
            'fecha_inicio': lista.fecha_inicio,
            'fecha_fin': lista.fecha_fin if hasattr(lista, 'fecha_fin') and lista.fecha_fin else 'Indefinido',
            'total_articulos': lista.total_articulos,
            'activo': lista.activo,
        })
    
    context = {
        'listas': listas_data,
        'total': listas.count(),
    }
    
    return render(request, 'listas_precios_list.html', context)


def precios_articulos_list_view(request):
    """Vista de listado de precios por artículo"""
    precios = PrecioArticulo.objects.select_related(
        'lista_precio', 'articulo'
    ).order_by('-id')[:100]  # Limitar a 100 registros
    
    precios_data = []
    for precio in precios:
        precios_data.append({
            'id': precio.id,
            'lista_nombre': precio.lista_precio.nombre,
            'articulo_codigo': precio.articulo.codigo,
            'articulo_desc': precio.articulo.nombre,
            'precio_base': float(precio.precio_base),
            'precio_final': float(precio.precio_final),
            'descuento': float(precio.descuento_porcentaje) if hasattr(precio, 'descuento_porcentaje') and precio.descuento_porcentaje else 0,
            'activo': precio.activo if hasattr(precio, 'activo') else True,
        })
    
    context = {
        'precios': precios_data,
        'total': PrecioArticulo.objects.count(),
    }
    
    return render(request, 'precios_articulos_list.html', context)


def reglas_precios_list_view(request):
    """Vista de listado de reglas de precios"""
    reglas = ReglaPrecio.objects.select_related(
        'lista_precio', 'linea_articulo', 'grupo_articulo'
    ).order_by('-id')
    
    reglas_data = []
    for regla in reglas:
        reglas_data.append({
            'id': regla.id,
            'lista_nombre': regla.lista_precio.nombre,
            'tipo_regla': regla.tipo_regla,
            'linea_nombre': regla.linea_articulo.nombre if regla.linea_articulo else 'N/A',
            'grupo_nombre': regla.grupo_articulo.nombre if regla.grupo_articulo else 'N/A',
            'tipo_ajuste': regla.tipo_descuento,
            'valor_ajuste': float(regla.valor_descuento),
            'prioridad': regla.prioridad,
            'activo': regla.activo,
        })
    
    context = {
        'reglas': reglas_data,
        'total': reglas.count(),
    }
    
    return render(request, 'reglas_precios_list.html', context)