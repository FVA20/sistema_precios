from decimal import Decimal
from django.utils import timezone
from django.db import models, transaction
from django.core.exceptions import ValidationError
from typing import Dict, List, Optional, Tuple
from .models import (
    Empresa, Sucursal, Articulo, ListaPrecio, PrecioArticulo,
    ReglaPrecio, CombinacionProducto, DetalleCombinacionProducto,
    AuditoriaPrecios
)


class PrecioService:
    """
    Servicio para gestionar la lógica de cálculo de precios según políticas comerciales.
    Implementa el cálculo jerárquico: precio base → canal → escala → monto → combinación
    """
    
    @staticmethod
    def obtener_lista_vigente(
        empresa_id: int,
        sucursal_id: Optional[int] = None,
        canal: Optional[str] = None,
        fecha: Optional[str] = None
    ) -> Optional[ListaPrecio]:
        """
        Obtiene la lista de precios vigente para una empresa/sucursal en una fecha
        
        Args:
            empresa_id: ID de la empresa
            sucursal_id: ID de la sucursal (opcional)
            canal: Canal de venta (opcional)
            fecha: Fecha de consulta (opcional, por defecto hoy)
        
        Returns:
            ListaPrecio vigente o None si no existe
        """
        fecha_consulta = fecha or timezone.now().date()
        
        filtros = {
            'empresa_id': empresa_id,
            'activo': True,
            'fecha_inicio__lte': fecha_consulta,
        }
        
        if sucursal_id:
            filtros['sucursal_id'] = sucursal_id
        
        if canal:
            filtros['canal'] = canal
        
        # Buscar lista que no haya expirado
        listas = ListaPrecio.objects.filter(**filtros).filter(
            models.Q(fecha_fin__gte=fecha_consulta) | models.Q(fecha_fin__isnull=True)
        ).order_by('-fecha_inicio')
        
        return listas.first()
    
    @staticmethod
    def calcular_precio(
        empresa_id: int,
        articulo_id: int,
        cantidad: Decimal,
        sucursal_id: Optional[int] = None,
        canal: Optional[str] = None,
        monto_pedido: Optional[Decimal] = None,
        items_pedido: Optional[List[Dict]] = None,
        fecha: Optional[str] = None
    ) -> Dict:
        """
        Calcula el precio final de un artículo aplicando todas las reglas comerciales
        
        Args:
            empresa_id: ID de la empresa
            articulo_id: ID del artículo
            cantidad: Cantidad solicitada
            sucursal_id: ID de la sucursal (opcional)
            canal: Canal de venta (opcional)
            monto_pedido: Monto total del pedido (opcional)
            items_pedido: Lista de items del pedido para validar combinaciones (opcional)
            fecha: Fecha de consulta (opcional)
        
        Returns:
            Dict con precio_base, precio_final, reglas_aplicadas, bajo_costo, etc.
        """
        try:
            # 1. Obtener lista vigente
            lista = PrecioService.obtener_lista_vigente(
                empresa_id, sucursal_id, canal, fecha
            )
            
            if not lista:
                raise ValidationError('No existe una lista de precios vigente')
            
            # 2. Obtener artículo y precio base
            articulo = Articulo.objects.get(pk=articulo_id, activo=True)
            precio_articulo = PrecioArticulo.objects.filter(
                lista_precio=lista,
                articulo=articulo
            ).first()
            
            if not precio_articulo:
                raise ValidationError(f'No existe precio para el artículo {articulo.nombre}')
            
            precio_base = precio_articulo.precio_base
            precio_actual = precio_base
            reglas_aplicadas = []
            
            # 3. Aplicar reglas por prioridad jerárquica
            
            # 3.1 Regla por canal
            if canal:
                precio_actual, regla_canal = PrecioService._aplicar_regla_canal(
                    lista, articulo, precio_actual, canal
                )
                if regla_canal:
                    reglas_aplicadas.append(regla_canal)
            
            # 3.2 Regla por escala de unidades
            precio_actual, regla_escala_unidades = PrecioService._aplicar_regla_escala_unidades(
                lista, articulo, precio_actual, cantidad
            )
            if regla_escala_unidades:
                reglas_aplicadas.append(regla_escala_unidades)
            
            # 3.3 Regla por escala de monto
            monto_item = precio_actual * cantidad
            precio_actual, regla_escala_monto = PrecioService._aplicar_regla_escala_monto(
                lista, articulo, precio_actual, monto_item
            )
            if regla_escala_monto:
                reglas_aplicadas.append(regla_escala_monto)
            
            # 3.4 Regla por monto total del pedido
            if monto_pedido:
                precio_actual, regla_monto_pedido = PrecioService._aplicar_regla_monto_pedido(
                    lista, articulo, precio_actual, monto_pedido
                )
                if regla_monto_pedido:
                    reglas_aplicadas.append(regla_monto_pedido)
            
            # 3.5 Regla por combinación de productos
            if items_pedido:
                precio_actual, regla_combinacion = PrecioService._aplicar_regla_combinacion(
                    lista, articulo, precio_actual, items_pedido
                )
                if regla_combinacion:
                    reglas_aplicadas.append(regla_combinacion)
            
            # 4. Validar costo
            bajo_costo = precio_actual < articulo.ultimo_costo
            autorizado = precio_articulo.autorizado_bajo_costo if bajo_costo else True
            
            # 5. Registrar auditoría
            PrecioService._registrar_auditoria_calculo(
                articulo_id=articulo_id,
                precio_base=precio_base,
                precio_final=precio_actual,
                reglas_aplicadas=reglas_aplicadas,
                bajo_costo=bajo_costo
            )
            
            return {
                'articulo_id': articulo_id,
                'articulo_nombre': articulo.nombre,
                'cantidad': float(cantidad),
                'precio_base': float(precio_base),
                'precio_final': float(precio_actual),
                'monto_total': float(precio_actual * cantidad),
                'descuento_total': float(precio_base - precio_actual),
                'porcentaje_descuento': float((precio_base - precio_actual) / precio_base * 100) if precio_base > 0 else 0,
                'reglas_aplicadas': reglas_aplicadas,
                'bajo_costo': bajo_costo,
                'autorizado_bajo_costo': autorizado,
                'ultimo_costo': float(articulo.ultimo_costo),
                'descuento_proveedor': float(precio_articulo.descuento_proveedor),
                'lista_precio': lista.nombre,
            }
            
        except Articulo.DoesNotExist:
            raise ValidationError(f'Artículo con ID {articulo_id} no existe')
        except Exception as e:
            raise ValidationError(f'Error al calcular precio: {str(e)}')
    
    @staticmethod
    def _aplicar_regla_canal(
        lista: ListaPrecio,
        articulo: Articulo,
        precio_actual: Decimal,
        canal: str
    ) -> Tuple[Decimal, Optional[Dict]]:
        """Aplica regla de precio por canal de venta"""
        reglas = ReglaPrecio.objects.filter(
            lista_precio=lista,
            tipo_regla='CANAL',
            canal=canal,
            activo=True
        ).filter(
            models.Q(linea_articulo=articulo.grupo.linea) |
            models.Q(grupo_articulo=articulo.grupo) |
            models.Q(linea_articulo__isnull=True, grupo_articulo__isnull=True)
        ).order_by('-prioridad')
        
        regla = reglas.first()
        if regla:
            nuevo_precio = regla.aplicar_descuento(precio_actual)
            return nuevo_precio, {
                'tipo': 'CANAL',
                'nombre': regla.nombre,
                'descuento': float(regla.valor_descuento),
                'tipo_descuento': regla.tipo_descuento
            }
        
        return precio_actual, None
    
    @staticmethod
    def _aplicar_regla_escala_unidades(
        lista: ListaPrecio,
        articulo: Articulo,
        precio_actual: Decimal,
        cantidad: Decimal
    ) -> Tuple[Decimal, Optional[Dict]]:
        """Aplica regla de precio por escala de unidades"""
        from django.db.models import Q
        
        reglas = ReglaPrecio.objects.filter(
            lista_precio=lista,
            tipo_regla='ESCALA_UNIDADES',
            activo=True
        ).filter(
            Q(linea_articulo=articulo.grupo.linea) |
            Q(grupo_articulo=articulo.grupo) |
            Q(linea_articulo__isnull=True, grupo_articulo__isnull=True)
        ).filter(
            Q(cantidad_minima__lte=cantidad) | Q(cantidad_minima__isnull=True),
            Q(cantidad_maxima__gte=cantidad) | Q(cantidad_maxima__isnull=True)
        ).order_by('-prioridad')
        
        regla = reglas.first()
        if regla:
            nuevo_precio = regla.aplicar_descuento(precio_actual)
            return nuevo_precio, {
                'tipo': 'ESCALA_UNIDADES',
                'nombre': regla.nombre,
                'descuento': float(regla.valor_descuento),
                'tipo_descuento': regla.tipo_descuento,
                'cantidad_minima': float(regla.cantidad_minima) if regla.cantidad_minima else None,
                'cantidad_maxima': float(regla.cantidad_maxima) if regla.cantidad_maxima else None,
            }
        
        return precio_actual, None
    
    @staticmethod
    def _aplicar_regla_escala_monto(
        lista: ListaPrecio,
        articulo: Articulo,
        precio_actual: Decimal,
        monto_item: Decimal
    ) -> Tuple[Decimal, Optional[Dict]]:
        """Aplica regla de precio por escala de monto del item"""
        from django.db.models import Q
        
        reglas = ReglaPrecio.objects.filter(
            lista_precio=lista,
            tipo_regla='ESCALA_MONTO',
            activo=True
        ).filter(
            Q(linea_articulo=articulo.grupo.linea) |
            Q(grupo_articulo=articulo.grupo) |
            Q(linea_articulo__isnull=True, grupo_articulo__isnull=True)
        ).filter(
            Q(monto_minimo__lte=monto_item) | Q(monto_minimo__isnull=True),
            Q(monto_maximo__gte=monto_item) | Q(monto_maximo__isnull=True)
        ).order_by('-prioridad')
        
        regla = reglas.first()
        if regla:
            nuevo_precio = regla.aplicar_descuento(precio_actual)
            return nuevo_precio, {
                'tipo': 'ESCALA_MONTO',
                'nombre': regla.nombre,
                'descuento': float(regla.valor_descuento),
                'tipo_descuento': regla.tipo_descuento,
                'monto_minimo': float(regla.monto_minimo) if regla.monto_minimo else None,
                'monto_maximo': float(regla.monto_maximo) if regla.monto_maximo else None,
            }
        
        return precio_actual, None
    
    @staticmethod
    def _aplicar_regla_monto_pedido(
        lista: ListaPrecio,
        articulo: Articulo,
        precio_actual: Decimal,
        monto_pedido: Decimal
    ) -> Tuple[Decimal, Optional[Dict]]:
        """Aplica regla de precio por monto total del pedido"""
        from django.db.models import Q
        
        reglas = ReglaPrecio.objects.filter(
            lista_precio=lista,
            tipo_regla='MONTO_PEDIDO',
            activo=True
        ).filter(
            Q(monto_minimo__lte=monto_pedido) | Q(monto_minimo__isnull=True),
            Q(monto_maximo__gte=monto_pedido) | Q(monto_maximo__isnull=True)
        ).order_by('-prioridad')
        
        regla = reglas.first()
        if regla:
            nuevo_precio = regla.aplicar_descuento(precio_actual)
            return nuevo_precio, {
                'tipo': 'MONTO_PEDIDO',
                'nombre': regla.nombre,
                'descuento': float(regla.valor_descuento),
                'tipo_descuento': regla.tipo_descuento,
            }
        
        return precio_actual, None
    
    @staticmethod
    def _aplicar_regla_combinacion(
        lista: ListaPrecio,
        articulo: Articulo,
        precio_actual: Decimal,
        items_pedido: List[Dict]
    ) -> Tuple[Decimal, Optional[Dict]]:
        """Aplica regla de precio por combinación de productos"""
        combinaciones = CombinacionProducto.objects.filter(
            lista_precio=lista,
            activo=True
        ).prefetch_related('detalles')
        
        for combinacion in combinaciones:
            if PrecioService._validar_combinacion(combinacion, items_pedido):
                if combinacion.tipo_descuento == 'PORCENTAJE':
                    nuevo_precio = precio_actual * (1 - combinacion.valor_descuento / 100)
                else:
                    nuevo_precio = max(precio_actual - combinacion.valor_descuento, Decimal('0'))
                
                return nuevo_precio, {
                    'tipo': 'COMBINACION',
                    'nombre': combinacion.nombre,
                    'descuento': float(combinacion.valor_descuento),
                    'tipo_descuento': combinacion.tipo_descuento,
                }
        
        return precio_actual, None
    
    @staticmethod
    def _validar_combinacion(
        combinacion: CombinacionProducto,
        items_pedido: List[Dict]
    ) -> bool:
        """Valida si el pedido cumple con una combinación de productos"""
        detalles = combinacion.detalles.all()
        
        for detalle in detalles:
            cantidad_encontrada = 0
            
            for item in items_pedido:
                articulo_id = item.get('articulo_id')
                cantidad = item.get('cantidad', 0)
                
                try:
                    articulo = Articulo.objects.get(pk=articulo_id)
                    
                    if detalle.articulo and detalle.articulo.id == articulo_id:
                        cantidad_encontrada += cantidad
                    elif detalle.grupo_articulo and detalle.grupo_articulo.id == articulo.grupo.id:
                        cantidad_encontrada += cantidad
                    elif detalle.linea_articulo and detalle.linea_articulo.id == articulo.grupo.linea.id:
                        cantidad_encontrada += cantidad
                        
                except Articulo.DoesNotExist:
                    continue
            
            if cantidad_encontrada < detalle.cantidad_requerida:
                return False
        
        return True
    
    @staticmethod
    @transaction.atomic
    def registrar_descuento_proveedor(
        precio_articulo_id: int,
        descuento_porcentaje: Decimal,
        observaciones: str = ''
    ) -> PrecioArticulo:
        """
        Registra un descuento especial otorgado por el proveedor
        
        Args:
            precio_articulo_id: ID del precio del artículo
            descuento_porcentaje: Porcentaje de descuento (50-70%)
            observaciones: Observaciones sobre el descuento
        
        Returns:
            PrecioArticulo actualizado
        """
        if not (50 <= descuento_porcentaje <= 70):
            raise ValidationError('El descuento de proveedor debe estar entre 50% y 70%')
        
        precio_articulo = PrecioArticulo.objects.get(pk=precio_articulo_id)
        precio_articulo.descuento_proveedor = descuento_porcentaje
        precio_articulo.autorizado_bajo_costo = True
        precio_articulo.observaciones = observaciones
        precio_articulo.save()
        
        return precio_articulo
    
    @staticmethod
    def _registrar_auditoria_calculo(
        articulo_id: int,
        precio_base: Decimal,
        precio_final: Decimal,
        reglas_aplicadas: List[Dict],
        bajo_costo: bool
    ):
        """Registra en auditoría el cálculo de precio"""
        AuditoriaPrecios.objects.create(
            tipo_operacion='CALCULO',
            tabla='precio_calculo',
            registro_id=articulo_id,
            datos_nuevos={
                'articulo_id': articulo_id,
                'precio_base': float(precio_base),
                'precio_final': float(precio_final),
                'reglas_aplicadas': reglas_aplicadas,
                'bajo_costo': bajo_costo,
            }
        )
    
    @staticmethod
    def validar_costo(articulo: Articulo, precio_propuesto: Decimal) -> Dict:
        """
        Valida si un precio propuesto es válido respecto al costo
        
        Returns:
            Dict con 'valido', 'mensaje', 'requiere_autorizacion'
        """
        if precio_propuesto >= articulo.ultimo_costo:
            return {
                'valido': True,
                'mensaje': 'Precio válido',
                'requiere_autorizacion': False
            }
        else:
            return {
                'valido': False,
                'mensaje': f'Precio ({precio_propuesto}) inferior al costo ({articulo.ultimo_costo})',
                'requiere_autorizacion': True
            }