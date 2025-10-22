from rest_framework import serializers
from .models import (
    Empresa, Sucursal, LineaArticulo, GrupoArticulo, Articulo,
    ListaPrecio, PrecioArticulo, ReglaPrecio, CombinacionProducto,
    DetalleCombinacionProducto, AuditoriaPrecios
)


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = '__all__'


class SucursalSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    
    class Meta:
        model = Sucursal
        fields = '__all__'


class LineaArticuloSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineaArticulo
        fields = '__all__'


class GrupoArticuloSerializer(serializers.ModelSerializer):
    linea_nombre = serializers.CharField(source='linea.nombre', read_only=True)
    
    class Meta:
        model = GrupoArticulo
        fields = '__all__'


class ArticuloSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    linea_nombre = serializers.CharField(source='grupo.linea.nombre', read_only=True)
    
    class Meta:
        model = Articulo
        fields = '__all__'


class ArticuloSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplificado para artículos"""
    class Meta:
        model = Articulo
        fields = ['id', 'codigo', 'nombre', 'ultimo_costo', 'unidad_medida']


class PrecioArticuloSerializer(serializers.ModelSerializer):
    articulo_nombre = serializers.CharField(source='articulo.nombre', read_only=True)
    articulo_codigo = serializers.CharField(source='articulo.codigo', read_only=True)
    margen = serializers.SerializerMethodField()
    
    class Meta:
        model = PrecioArticulo
        fields = '__all__'
    
    def get_margen(self, obj):
        """Calcular margen de ganancia"""
        if obj.articulo.ultimo_costo > 0:
            return round((obj.precio_base - obj.articulo.ultimo_costo) / obj.articulo.ultimo_costo * 100, 2)
        return 0
    
    def validate(self, data):
        """Validar precio base vs costo"""
        articulo = data.get('articulo')
        precio_base = data.get('precio_base')
        bajo_costo = data.get('bajo_costo', False)
        autorizado = data.get('autorizado_bajo_costo', False)
        descuento_proveedor = data.get('descuento_proveedor', 0)
        
        if precio_base < articulo.ultimo_costo:
            if not bajo_costo or not autorizado:
                if descuento_proveedor < 50:
                    raise serializers.ValidationError(
                        f'El precio ({precio_base}) es inferior al costo ({articulo.ultimo_costo}). '
                        f'Requiere marcar como bajo_costo=True, autorizado_bajo_costo=True '
                        f'o descuento_proveedor >= 50%'
                    )
            data['bajo_costo'] = True
        
        return data


class ListaPrecioSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True, allow_null=True)
    total_articulos = serializers.SerializerMethodField()
    vigente = serializers.SerializerMethodField()
    
    class Meta:
        model = ListaPrecio
        fields = '__all__'
    
    def get_total_articulos(self, obj):
        return obj.precios.count()
    
    def get_vigente(self, obj):
        return obj.esta_vigente()
    
    def validate(self, data):
        """Validar fechas y solapamiento"""
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        
        if fecha_fin and fecha_fin < fecha_inicio:
            raise serializers.ValidationError(
                'La fecha de fin no puede ser anterior a la fecha de inicio'
            )
        
        return data


class ReglaPrecioSerializer(serializers.ModelSerializer):
    lista_precio_nombre = serializers.CharField(source='lista_precio.nombre', read_only=True)
    linea_nombre = serializers.CharField(source='linea_articulo.nombre', read_only=True, allow_null=True)
    grupo_nombre = serializers.CharField(source='grupo_articulo.nombre', read_only=True, allow_null=True)
    
    class Meta:
        model = ReglaPrecio
        fields = '__all__'
    
    def validate(self, data):
        """Validar escalas y montos"""
        cantidad_minima = data.get('cantidad_minima')
        cantidad_maxima = data.get('cantidad_maxima')
        monto_minimo = data.get('monto_minimo')
        monto_maximo = data.get('monto_maximo')
        
        if cantidad_minima and cantidad_maxima:
            if cantidad_maxima < cantidad_minima:
                raise serializers.ValidationError(
                    'La cantidad máxima no puede ser menor que la cantidad mínima'
                )
        
        if monto_minimo and monto_maximo:
            if monto_maximo < monto_minimo:
                raise serializers.ValidationError(
                    'El monto máximo no puede ser menor que el monto mínimo'
                )
        
        return data


class DetalleCombinacionSerializer(serializers.ModelSerializer):
    articulo_nombre = serializers.CharField(source='articulo.nombre', read_only=True, allow_null=True)
    grupo_nombre = serializers.CharField(source='grupo_articulo.nombre', read_only=True, allow_null=True)
    linea_nombre = serializers.CharField(source='linea_articulo.nombre', read_only=True, allow_null=True)
    
    class Meta:
        model = DetalleCombinacionProducto
        fields = '__all__'


class CombinacionProductoSerializer(serializers.ModelSerializer):
    lista_precio_nombre = serializers.CharField(source='lista_precio.nombre', read_only=True)
    detalles = DetalleCombinacionSerializer(many=True, read_only=True)
    
    class Meta:
        model = CombinacionProducto
        fields = '__all__'


class AuditoriaPreciosSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditoriaPrecios
        fields = '__all__'


# ============= SERIALIZERS PARA CÁLCULO DE PRECIOS =============

class ItemPedidoSerializer(serializers.Serializer):
    """Serializer para items de un pedido"""
    articulo_id = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)


class CalculoPrecioRequestSerializer(serializers.Serializer):
    """Serializer para solicitud de cálculo de precio"""
    empresa_id = serializers.IntegerField(required=True)
    articulo_id = serializers.IntegerField(required=True)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, required=True)
    sucursal_id = serializers.IntegerField(required=False, allow_null=True)
    canal = serializers.ChoiceField(
        choices=ListaPrecio.CANAL_CHOICES,
        required=False,
        allow_null=True
    )
    monto_pedido = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    items_pedido = ItemPedidoSerializer(many=True, required=False, allow_null=True)
    fecha = serializers.DateField(required=False, allow_null=True)


class CalculoPrecioResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de cálculo de precio"""
    articulo_id = serializers.IntegerField()
    articulo_nombre = serializers.CharField()
    cantidad = serializers.FloatField()
    precio_base = serializers.FloatField()
    precio_final = serializers.FloatField()
    monto_total = serializers.FloatField()
    descuento_total = serializers.FloatField()
    porcentaje_descuento = serializers.FloatField()
    reglas_aplicadas = serializers.ListField()
    bajo_costo = serializers.BooleanField()
    autorizado_bajo_costo = serializers.BooleanField()
    ultimo_costo = serializers.FloatField()
    descuento_proveedor = serializers.FloatField()
    lista_precio = serializers.CharField()


class CalculoPrecioMultipleRequestSerializer(serializers.Serializer):
    """Serializer para cálculo de múltiples artículos"""
    empresa_id = serializers.IntegerField(required=True)
    sucursal_id = serializers.IntegerField(required=False, allow_null=True)
    canal = serializers.ChoiceField(
        choices=ListaPrecio.CANAL_CHOICES,
        required=False,
        allow_null=True
    )
    items = ItemPedidoSerializer(many=True, required=True)
    fecha = serializers.DateField(required=False, allow_null=True)


class ListaPrecioConPreciosSerializer(serializers.ModelSerializer):
    """Serializer de lista con todos sus precios"""
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True, allow_null=True)
    precios = PrecioArticuloSerializer(many=True, read_only=True)
    reglas = ReglaPrecioSerializer(many=True, read_only=True)
    combinaciones = CombinacionProductoSerializer(many=True, read_only=True)
    
    class Meta:
        model = ListaPrecio
        fields = '__all__'


class DescuentoProveedorSerializer(serializers.Serializer):
    """Serializer para registrar descuento de proveedor"""
    precio_articulo_id = serializers.IntegerField(required=True)
    descuento_porcentaje = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=50,
        max_value=70,
        required=True
    )
    observaciones = serializers.CharField(required=False, allow_blank=True)