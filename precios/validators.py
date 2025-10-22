from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import timedelta


def validar_ruc(value):
    """
    Valida que el RUC peruano sea válido
    - Debe tener 11 dígitos
    - Debe comenzar con 10, 15, 16, 17 o 20
    """
    if not value:
        return
    
    value = str(value).strip()
    
    if len(value) != 11:
        raise ValidationError('El RUC debe tener 11 dígitos')
    
    if not value.isdigit():
        raise ValidationError('El RUC solo debe contener números')
    
    prefijos_validos = ['10', '15', '16', '17', '20']
    if not any(value.startswith(prefijo) for prefijo in prefijos_validos):
        raise ValidationError(
            'El RUC debe comenzar con 10, 15, 16, 17 o 20'
        )


def validar_codigo_articulo(value):
    """
    Valida formato de código de artículo
    - Máximo 50 caracteres
    - Solo alfanuméricos y guiones
    """
    if not value:
        return
    
    value = str(value).strip()
    
    if len(value) > 50:
        raise ValidationError('El código no puede tener más de 50 caracteres')
    
    if not all(c.isalnum() or c in ['-', '_'] for c in value):
        raise ValidationError(
            'El código solo puede contener letras, números, guiones y guiones bajos'
        )


def validar_precio_positivo(value):
    """
    Valida que el precio sea un número positivo
    """
    if value is None:
        return
    
    try:
        precio = Decimal(str(value))
    except:
        raise ValidationError('El precio debe ser un número válido')
    
    if precio < 0:
        raise ValidationError('El precio no puede ser negativo')
    
    if precio > Decimal('999999.99'):
        raise ValidationError('El precio no puede ser mayor a 999,999.99')


def validar_porcentaje(value):
    """
    Valida que el valor sea un porcentaje válido (0-100)
    """
    if value is None:
        return
    
    try:
        porcentaje = Decimal(str(value))
    except:
        raise ValidationError('El porcentaje debe ser un número válido')
    
    if porcentaje < 0 or porcentaje > 100:
        raise ValidationError('El porcentaje debe estar entre 0 y 100')


def validar_cantidad_positiva(value):
    """
    Valida que la cantidad sea positiva
    """
    if value is None:
        return
    
    try:
        cantidad = Decimal(str(value))
    except:
        raise ValidationError('La cantidad debe ser un número válido')
    
    if cantidad <= 0:
        raise ValidationError('La cantidad debe ser mayor a 0')


def validar_fecha_vigencia(fecha_inicio, fecha_fin):
    """
    Valida que las fechas de vigencia sean coherentes
    """
    if fecha_fin and fecha_inicio:
        if fecha_fin < fecha_inicio:
            raise ValidationError(
                'La fecha de fin no puede ser anterior a la fecha de inicio'
            )


def validar_escala(minimo, maximo):
    """
    Valida que los valores de escala sean coherentes
    """
    if minimo is not None and maximo is not None:
        if Decimal(str(maximo)) < Decimal(str(minimo)):
            raise ValidationError(
                'El valor máximo no puede ser menor que el valor mínimo'
            )


def validar_margen_ganancia(precio_venta, precio_costo, margen_minimo=0):
    """
    Valida que el margen de ganancia sea aceptable
    """
    if precio_costo <= 0:
        return True
    
    margen = ((precio_venta - precio_costo) / precio_costo) * 100
    
    if margen < margen_minimo:
        raise ValidationError(
            f'El margen de ganancia ({margen:.2f}%) es menor al mínimo permitido ({margen_minimo}%)'
        )


def validar_descuento_proveedor(value):
    """
    Valida que el descuento de proveedor esté en el rango permitido
    """
    if value is None or value == 0:
        return
    
    try:
        descuento = Decimal(str(value))
    except:
        raise ValidationError('El descuento debe ser un número válido')
    
    if descuento < 50 or descuento > 70:
        raise ValidationError(
            'El descuento de proveedor debe estar entre 50% y 70%'
        )


def validar_combinacion_productos(combinacion):
    """
    Valida que una combinación de productos sea coherente
    """
    detalles = combinacion.detalles.all()
    
    if not detalles.exists():
        raise ValidationError(
            'La combinación debe tener al menos un producto'
        )
    
    # Validar que al menos un detalle tenga artículo, grupo o línea
    for detalle in detalles:
        if not any([detalle.articulo, detalle.grupo_articulo, detalle.linea_articulo]):
            raise ValidationError(
                'Cada detalle debe tener al menos un artículo, grupo o línea especificada'
            )


class ValidadorReglasPrecio:
    """
    Clase validadora para reglas de precio
    """
    
    @staticmethod
    def validar_regla_canal(regla):
        """Valida regla por canal"""
        if regla.tipo_regla == 'CANAL' and not regla.canal:
            raise ValidationError('Debe especificar un canal para este tipo de regla')
    
    @staticmethod
    def validar_regla_escala_unidades(regla):
        """Valida regla por escala de unidades"""
        if regla.tipo_regla == 'ESCALA_UNIDADES':
            if regla.cantidad_minima is None:
                raise ValidationError('Debe especificar cantidad mínima')
            validar_cantidad_positiva(regla.cantidad_minima)
            if regla.cantidad_maxima:
                validar_escala(regla.cantidad_minima, regla.cantidad_maxima)
    
    @staticmethod
    def validar_regla_escala_monto(regla):
        """Valida regla por escala de monto"""
        if regla.tipo_regla == 'ESCALA_MONTO':
            if regla.monto_minimo is None:
                raise ValidationError('Debe especificar monto mínimo')
            validar_precio_positivo(regla.monto_minimo)
            if regla.monto_maximo:
                validar_escala(regla.monto_minimo, regla.monto_maximo)
    
    @staticmethod
    def validar_regla_monto_pedido(regla):
        """Valida regla por monto de pedido"""
        if regla.tipo_regla == 'MONTO_PEDIDO':
            if regla.monto_minimo is None:
                raise ValidationError('Debe especificar monto mínimo')
            validar_precio_positivo(regla.monto_minimo)
    
    @staticmethod
    def validar_regla_completa(regla):
        """Valida una regla completa según su tipo"""
        validadores = {
            'CANAL': ValidadorReglasPrecio.validar_regla_canal,
            'ESCALA_UNIDADES': ValidadorReglasPrecio.validar_regla_escala_unidades,
            'ESCALA_MONTO': ValidadorReglasPrecio.validar_regla_escala_monto,
            'MONTO_PEDIDO': ValidadorReglasPrecio.validar_regla_monto_pedido,
        }
        
        validador = validadores.get(regla.tipo_regla)
        if validador:
            validador(regla)


def validar_no_duplicar_precio(lista_precio, articulo, precio_id=None):
    """
    Valida que no exista un precio duplicado para el mismo artículo en la lista
    """
    from .models import PrecioArticulo
    
    query = PrecioArticulo.objects.filter(
        lista_precio=lista_precio,
        articulo=articulo
    )
    
    if precio_id:
        query = query.exclude(pk=precio_id)
    
    if query.exists():
        raise ValidationError(
            f'Ya existe un precio para el artículo {articulo.nombre} en esta lista'
        )


def validar_vigencia_no_solapada(empresa, sucursal, fecha_inicio, fecha_fin, lista_id=None):
    """
    Valida que no haya solapamiento de vigencias entre listas
    """
    from .models import ListaPrecio
    from django.db.models import Q
    
    query = ListaPrecio.objects.filter(
        empresa=empresa,
        activo=True
    )
    
    if sucursal:
        query = query.filter(sucursal=sucursal)
    
    if lista_id:
        query = query.exclude(pk=lista_id)
    
    # Buscar solapamientos
    for lista in query:
        inicio_existente = lista.fecha_inicio
        fin_existente = lista.fecha_fin
        
        # Si no tiene fecha fin, considerar como infinito
        if not fin_existente:
            fin_existente = fecha_inicio + timedelta(days=36500)
        
        if not fecha_fin:
            fecha_fin_temp = fecha_inicio + timedelta(days=36500)
        else:
            fecha_fin_temp = fecha_fin
        
        # Verificar solapamiento
        if fecha_inicio <= fin_existente and inicio_existente <= fecha_fin_temp:
            raise ValidationError(
                f'Las fechas se solapan con la lista "{lista.nombre}" '
                f'({lista.fecha_inicio} - {lista.fecha_fin or "indefinido"})'
            )