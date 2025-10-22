from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
import json
from .models import (
    ListaPrecio, PrecioArticulo, ReglaPrecio,
    CombinacionProducto, AuditoriaPrecios
)


def serializar_instancia(instancia):
    """Convierte una instancia del modelo a diccionario para auditoría"""
    from datetime import date, datetime
    from decimal import Decimal
    
    data = {}
    for field in instancia._meta.fields:
        valor = getattr(instancia, field.name)
        if hasattr(valor, 'pk'):  # Es una ForeignKey
            data[field.name] = valor.pk
        elif isinstance(valor, (date, datetime)):  # Es una fecha
            data[field.name] = valor.isoformat() if valor else None
        elif isinstance(valor, Decimal):  # Es un Decimal
            data[field.name] = float(valor)
        else:
            data[field.name] = valor
    return data


# ============= AUDITORÍA DE LISTA DE PRECIOS =============

@receiver(pre_save, sender=ListaPrecio)
def lista_precio_pre_save(sender, instance, **kwargs):
    """Guardar estado anterior antes de modificar"""
    if instance.pk:
        try:
            instance._estado_anterior = serializar_instancia(
                ListaPrecio.objects.get(pk=instance.pk)
            )
        except ListaPrecio.DoesNotExist:
            instance._estado_anterior = None
    else:
        instance._estado_anterior = None


@receiver(post_save, sender=ListaPrecio)
def lista_precio_post_save(sender, instance, created, **kwargs):
    """Registrar creación o modificación de lista"""
    tipo_operacion = 'CREACION' if created else 'MODIFICACION'
    
    datos_nuevos = serializar_instancia(instance)
    datos_anteriores = getattr(instance, '_estado_anterior', None)
    
    AuditoriaPrecios.objects.create(
        tipo_operacion=tipo_operacion,
        tabla='lista_precio',
        registro_id=instance.pk,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        usuario=''  # Aquí podrías obtener el usuario del request
    )


@receiver(post_delete, sender=ListaPrecio)
def lista_precio_post_delete(sender, instance, **kwargs):
    """Registrar eliminación de lista"""
    AuditoriaPrecios.objects.create(
        tipo_operacion='ELIMINACION',
        tabla='lista_precio',
        registro_id=instance.pk,
        datos_anteriores=serializar_instancia(instance),
        datos_nuevos=None,
        usuario=''
    )


# ============= AUDITORÍA DE PRECIO ARTÍCULO =============

@receiver(pre_save, sender=PrecioArticulo)
def precio_articulo_pre_save(sender, instance, **kwargs):
    """Guardar estado anterior antes de modificar"""
    if instance.pk:
        try:
            instance._estado_anterior = serializar_instancia(
                PrecioArticulo.objects.get(pk=instance.pk)
            )
        except PrecioArticulo.DoesNotExist:
            instance._estado_anterior = None
    else:
        instance._estado_anterior = None


@receiver(post_save, sender=PrecioArticulo)
def precio_articulo_post_save(sender, instance, created, **kwargs):
    """Registrar creación o modificación de precio"""
    tipo_operacion = 'CREACION' if created else 'MODIFICACION'
    
    datos_nuevos = serializar_instancia(instance)
    datos_anteriores = getattr(instance, '_estado_anterior', None)
    
    # Agregar información adicional para mejor auditoría
    datos_nuevos['articulo_nombre'] = instance.articulo.nombre
    datos_nuevos['lista_nombre'] = instance.lista_precio.nombre
    
    if datos_anteriores:
        # Calcular cambios específicos
        cambios = {}
        if datos_anteriores.get('precio_base') != datos_nuevos.get('precio_base'):
            cambios['precio_base'] = {
                'anterior': float(datos_anteriores.get('precio_base', 0)),
                'nuevo': float(datos_nuevos.get('precio_base', 0))
            }
        datos_nuevos['cambios_detectados'] = cambios
    
    AuditoriaPrecios.objects.create(
        tipo_operacion=tipo_operacion,
        tabla='precio_articulo',
        registro_id=instance.pk,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        usuario=''
    )


@receiver(post_delete, sender=PrecioArticulo)
def precio_articulo_post_delete(sender, instance, **kwargs):
    """Registrar eliminación de precio"""
    datos = serializar_instancia(instance)
    datos['articulo_nombre'] = instance.articulo.nombre
    datos['lista_nombre'] = instance.lista_precio.nombre
    
    AuditoriaPrecios.objects.create(
        tipo_operacion='ELIMINACION',
        tabla='precio_articulo',
        registro_id=instance.pk,
        datos_anteriores=datos,
        datos_nuevos=None,
        usuario=''
    )


# ============= AUDITORÍA DE REGLA DE PRECIO =============

@receiver(post_save, sender=ReglaPrecio)
def regla_precio_post_save(sender, instance, created, **kwargs):
    """Registrar creación o modificación de regla"""
    tipo_operacion = 'CREACION' if created else 'MODIFICACION'
    
    datos = serializar_instancia(instance)
    datos['lista_nombre'] = instance.lista_precio.nombre
    
    AuditoriaPrecios.objects.create(
        tipo_operacion=tipo_operacion,
        tabla='regla_precio',
        registro_id=instance.pk,
        datos_nuevos=datos,
        usuario=''
    )


@receiver(post_delete, sender=ReglaPrecio)
def regla_precio_post_delete(sender, instance, **kwargs):
    """Registrar eliminación de regla"""
    datos = serializar_instancia(instance)
    datos['lista_nombre'] = instance.lista_precio.nombre
    
    AuditoriaPrecios.objects.create(
        tipo_operacion='ELIMINACION',
        tabla='regla_precio',
        registro_id=instance.pk,
        datos_anteriores=datos,
        datos_nuevos=None,
        usuario=''
    )


# ============= AUDITORÍA DE COMBINACIÓN =============

@receiver(post_save, sender=CombinacionProducto)
def combinacion_post_save(sender, instance, created, **kwargs):
    """Registrar creación o modificación de combinación"""
    tipo_operacion = 'CREACION' if created else 'MODIFICACION'
    
    datos = serializar_instancia(instance)
    datos['lista_nombre'] = instance.lista_precio.nombre
    
    AuditoriaPrecios.objects.create(
        tipo_operacion=tipo_operacion,
        tabla='combinacion_producto',
        registro_id=instance.pk,
        datos_nuevos=datos,
        usuario=''
    )


@receiver(post_delete, sender=CombinacionProducto)
def combinacion_post_delete(sender, instance, **kwargs):
    """Registrar eliminación de combinación"""
    datos = serializar_instancia(instance)
    datos['lista_nombre'] = instance.lista_precio.nombre
    
    AuditoriaPrecios.objects.create(
        tipo_operacion='ELIMINACION',
        tabla='combinacion_producto',
        registro_id=instance.pk,
        datos_anteriores=datos,
        datos_nuevos=None,
        usuario=''
    )