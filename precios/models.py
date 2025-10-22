from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class Empresa(models.Model):
    """Modelo de Empresa"""
    nombre = models.CharField(max_length=200)
    ruc = models.CharField(max_length=11, unique=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'empresa'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
    
    def __str__(self):
        return self.nombre


class Sucursal(models.Model):
    """Modelo de Sucursal"""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='sucursales')
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=20)
    direccion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sucursal'
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'
        unique_together = [['empresa', 'codigo']]
    
    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"


class LineaArticulo(models.Model):
    """Línea de artículos (categoría principal)"""
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'linea_articulo'
        verbose_name = 'Línea de Artículo'
        verbose_name_plural = 'Líneas de Artículos'
    
    def __str__(self):
        return self.nombre


class GrupoArticulo(models.Model):
    """Grupo de artículos (subcategoría)"""
    linea = models.ForeignKey(LineaArticulo, on_delete=models.CASCADE, related_name='grupos')
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'grupo_articulo'
        verbose_name = 'Grupo de Artículo'
        verbose_name_plural = 'Grupos de Artículos'
    
    def __str__(self):
        return f"{self.linea.nombre} - {self.nombre}"


class Articulo(models.Model):
    """Modelo de Artículo/Producto"""
    grupo = models.ForeignKey(GrupoArticulo, on_delete=models.CASCADE, related_name='articulos')
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    unidad_medida = models.CharField(max_length=20, default='UND')
    ultimo_costo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'articulo'
        verbose_name = 'Artículo'
        verbose_name_plural = 'Artículos'
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class ListaPrecio(models.Model):
    """Lista de precios por empresa/sucursal"""
    TIPO_CHOICES = [
        ('GENERAL', 'General'),
        ('MAYORISTA', 'Mayorista'),
        ('MINORISTA', 'Minorista'),
        ('ESPECIAL', 'Especial'),
    ]
    
    CANAL_CHOICES = [
        ('TIENDA', 'Tienda Física'),
        ('ONLINE', 'Tienda Online'),
        ('DISTRIBUIDOR', 'Distribuidor'),
        ('CORPORATIVO', 'Corporativo'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='listas_precios')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='listas_precios', null=True, blank=True)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, null=True, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lista_precio'
        verbose_name = 'Lista de Precio'
        verbose_name_plural = 'Listas de Precios'
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"{self.nombre} - {self.empresa.nombre}"
    
    def clean(self):
        """Validar que no se solapen vigencias"""
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError('La fecha de fin no puede ser anterior a la fecha de inicio')
        
        # Validar solapamiento de vigencias
        filtro = {
            'empresa': self.empresa,
            'activo': True,
        }
        if self.sucursal:
            filtro['sucursal'] = self.sucursal
        
        listas_existentes = ListaPrecio.objects.filter(**filtro).exclude(pk=self.pk)
        
        for lista in listas_existentes:
            if self._vigencias_se_solapan(lista):
                raise ValidationError(
                    f'Las vigencias se solapan con la lista: {lista.nombre}'
                )
    
    def _vigencias_se_solapan(self, otra_lista):
        """Verificar si las vigencias se solapan"""
        inicio1, fin1 = self.fecha_inicio, self.fecha_fin or timezone.now().date() + timezone.timedelta(days=36500)
        inicio2, fin2 = otra_lista.fecha_inicio, otra_lista.fecha_fin or timezone.now().date() + timezone.timedelta(days=36500)
        
        return inicio1 <= fin2 and inicio2 <= fin1
    
    def esta_vigente(self, fecha=None):
        """Verificar si la lista está vigente en una fecha"""
        fecha = fecha or timezone.now().date()
        vigente = self.activo and self.fecha_inicio <= fecha
        if self.fecha_fin:
            vigente = vigente and fecha <= self.fecha_fin
        return vigente


class PrecioArticulo(models.Model):
    """Precio base de un artículo en una lista"""
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE, related_name='precios')
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='precios')
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    bajo_costo = models.BooleanField(default=False)
    autorizado_bajo_costo = models.BooleanField(default=False)
    descuento_proveedor = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'precio_articulo'
        verbose_name = 'Precio de Artículo'
        verbose_name_plural = 'Precios de Artículos'
        unique_together = [['lista_precio', 'articulo']]
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.lista_precio.nombre}: S/ {self.precio_base}"
    
    def clean(self):
        """Validar que el precio no sea inferior al costo"""
        if self.precio_base < self.articulo.ultimo_costo:
            if not self.bajo_costo or not self.autorizado_bajo_costo:
                if self.descuento_proveedor < 50:
                    raise ValidationError(
                        f'El precio ({self.precio_base}) es inferior al costo ({self.articulo.ultimo_costo}). '
                        f'Requiere autorización o descuento de proveedor >= 50%'
                    )
            self.bajo_costo = True


class ReglaPrecio(models.Model):
    """Reglas de precio dinámicas (políticas comerciales)"""
    TIPO_REGLA_CHOICES = [
        ('CANAL', 'Por Canal de Venta'),
        ('ESCALA_UNIDADES', 'Por Escala de Unidades'),
        ('ESCALA_MONTO', 'Por Escala de Monto'),
        ('MONTO_PEDIDO', 'Por Monto Total de Pedido'),
        ('COMBINACION', 'Por Combinación de Productos'),
    ]
    
    TIPO_DESCUENTO_CHOICES = [
        ('PORCENTAJE', 'Porcentaje'),
        ('MONTO_FIJO', 'Monto Fijo'),
    ]
    
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE, related_name='reglas')
    nombre = models.CharField(max_length=200)
    tipo_regla = models.CharField(max_length=20, choices=TIPO_REGLA_CHOICES)
    prioridad = models.IntegerField(default=0)
    
    # Filtros de aplicación
    canal = models.CharField(max_length=20, choices=ListaPrecio.CANAL_CHOICES, null=True, blank=True)
    linea_articulo = models.ForeignKey(LineaArticulo, on_delete=models.CASCADE, null=True, blank=True)
    grupo_articulo = models.ForeignKey(GrupoArticulo, on_delete=models.CASCADE, null=True, blank=True)
    
    # Condiciones de escala
    cantidad_minima = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cantidad_maxima = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_minimo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_maximo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Descuento
    tipo_descuento = models.CharField(max_length=20, choices=TIPO_DESCUENTO_CHOICES)
    valor_descuento = models.DecimalField(max_digits=10, decimal_places=2)
    
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'regla_precio'
        verbose_name = 'Regla de Precio'
        verbose_name_plural = 'Reglas de Precio'
        ordering = ['-prioridad', 'fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} - {self.lista_precio.nombre}"
    
    def aplicar_descuento(self, precio_base):
        """Aplicar el descuento de la regla al precio base"""
        if self.tipo_descuento == 'PORCENTAJE':
            return precio_base * (1 - self.valor_descuento / 100)
        else:  # MONTO_FIJO
            return max(precio_base - self.valor_descuento, Decimal('0'))


class CombinacionProducto(models.Model):
    """Combinación de productos para descuentos especiales"""
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE, related_name='combinaciones')
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    cantidad_minima = models.IntegerField(default=1)
    tipo_descuento = models.CharField(max_length=20, choices=ReglaPrecio.TIPO_DESCUENTO_CHOICES)
    valor_descuento = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'combinacion_producto'
        verbose_name = 'Combinación de Producto'
        verbose_name_plural = 'Combinaciones de Productos'
    
    def __str__(self):
        return self.nombre


class DetalleCombinacionProducto(models.Model):
    """Detalle de productos en una combinación"""
    combinacion = models.ForeignKey(CombinacionProducto, on_delete=models.CASCADE, related_name='detalles')
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, null=True, blank=True)
    grupo_articulo = models.ForeignKey(GrupoArticulo, on_delete=models.CASCADE, null=True, blank=True)
    linea_articulo = models.ForeignKey(LineaArticulo, on_delete=models.CASCADE, null=True, blank=True)
    cantidad_requerida = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'detalle_combinacion_producto'
        verbose_name = 'Detalle de Combinación'
        verbose_name_plural = 'Detalles de Combinaciones'
    
    def __str__(self):
        if self.articulo:
            return f"{self.combinacion.nombre} - {self.articulo.nombre}"
        elif self.grupo_articulo:
            return f"{self.combinacion.nombre} - Grupo: {self.grupo_articulo.nombre}"
        else:
            return f"{self.combinacion.nombre} - Línea: {self.linea_articulo.nombre}"


class DetalleOrdenCompraCliente(models.Model):
    """Detalle de orden de compra del cliente"""
    # Aquí iría la relación con OrdenCompraCliente si existe
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    reglas_aplicadas = models.JSONField(default=list, blank=True)
    bajo_costo = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'detalle_orden_compra_cliente'
        verbose_name = 'Detalle de Orden'
        verbose_name_plural = 'Detalles de Órdenes'
    
    def __str__(self):
        return f"{self.articulo.nombre} - Cant: {self.cantidad}"


class AuditoriaPrecios(models.Model):
    """Auditoría de cambios en precios"""
    TIPO_OPERACION_CHOICES = [
        ('CREACION', 'Creación'),
        ('MODIFICACION', 'Modificación'),
        ('ELIMINACION', 'Eliminación'),
        ('CALCULO', 'Cálculo de Precio'),
    ]
    
    tipo_operacion = models.CharField(max_length=20, choices=TIPO_OPERACION_CHOICES)
    tabla = models.CharField(max_length=50)
    registro_id = models.IntegerField()
    usuario = models.CharField(max_length=100, blank=True)
    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)
    fecha_operacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'auditoria_precios'
        verbose_name = 'Auditoría de Precio'
        verbose_name_plural = 'Auditorías de Precios'
        ordering = ['-fecha_operacion']
    
    def __str__(self):
        return f"{self.tipo_operacion} - {self.tabla} - {self.fecha_operacion}"