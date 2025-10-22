from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from decimal import Decimal

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