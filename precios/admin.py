from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Empresa, Sucursal, LineaArticulo, GrupoArticulo, Articulo,
    ListaPrecio, PrecioArticulo, ReglaPrecio, CombinacionProducto,
    DetalleCombinacionProducto, AuditoriaPrecios
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'ruc', 'activo', 'fecha_creacion']
    list_filter = ['activo']
    search_fields = ['nombre', 'ruc']
    date_hierarchy = 'fecha_creacion'


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'codigo', 'activo', 'fecha_creacion']
    list_filter = ['empresa', 'activo']
    search_fields = ['nombre', 'codigo', 'empresa__nombre']
    date_hierarchy = 'fecha_creacion'


@admin.register(LineaArticulo)
class LineaArticuloAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre', 'codigo']


@admin.register(GrupoArticulo)
class GrupoArticuloAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'linea', 'codigo', 'activo']
    list_filter = ['linea', 'activo']
    search_fields = ['nombre', 'codigo', 'linea__nombre']


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'grupo', 'ultimo_costo', 'unidad_medida', 'activo']
    list_filter = ['grupo__linea', 'grupo', 'activo']
    search_fields = ['codigo', 'nombre']
    readonly_fields = ['fecha_creacion']


class PrecioArticuloInline(admin.TabularInline):
    model = PrecioArticulo
    extra = 1
    fields = ['articulo', 'precio_base', 'bajo_costo', 'autorizado_bajo_costo', 'descuento_proveedor']
    autocomplete_fields = ['articulo']


class ReglaPrecioInline(admin.TabularInline):
    model = ReglaPrecio
    extra = 1
    fields = ['nombre', 'tipo_regla', 'prioridad', 'tipo_descuento', 'valor_descuento', 'activo']


class CombinacionProductoInline(admin.TabularInline):
    model = CombinacionProducto
    extra = 0
    fields = ['nombre', 'cantidad_minima', 'tipo_descuento', 'valor_descuento', 'activo']


@admin.register(ListaPrecio)
class ListaPrecioAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'empresa', 'sucursal', 'tipo', 'canal',
        'fecha_inicio', 'fecha_fin', 'vigente_badge', 'activo'
    ]
    list_filter = ['empresa', 'tipo', 'canal', 'activo', 'fecha_inicio']
    search_fields = ['nombre', 'empresa__nombre']
    date_hierarchy = 'fecha_inicio'
    inlines = [PrecioArticuloInline, ReglaPrecioInline, CombinacionProductoInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'empresa', 'sucursal', 'tipo', 'canal')
        }),
        ('Vigencia', {
            'fields': ('fecha_inicio', 'fecha_fin', 'activo')
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    def vigente_badge(self, obj):
        if obj.esta_vigente():
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✓ VIGENTE</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">✗ NO VIGENTE</span>'
            )
    vigente_badge.short_description = 'Estado'


@admin.register(PrecioArticulo)
class PrecioArticuloAdmin(admin.ModelAdmin):
    list_display = [
        'articulo', 'lista_precio', 'precio_base', 'ultimo_costo_articulo',
        'margen_badge', 'bajo_costo_badge', 'autorizado_bajo_costo'
    ]
    list_filter = ['lista_precio__empresa', 'lista_precio', 'bajo_costo', 'autorizado_bajo_costo']
    search_fields = ['articulo__nombre', 'articulo__codigo', 'lista_precio__nombre']
    autocomplete_fields = ['articulo', 'lista_precio']
    
    fieldsets = (
        ('Información General', {
            'fields': ('lista_precio', 'articulo', 'precio_base')
        }),
        ('Control de Costos', {
            'fields': ('bajo_costo', 'autorizado_bajo_costo', 'descuento_proveedor', 'observaciones')
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    def ultimo_costo_articulo(self, obj):
        return f"S/ {obj.articulo.ultimo_costo}"
    ultimo_costo_articulo.short_description = 'Último Costo'
    
    def margen_badge(self, obj):
        if obj.articulo.ultimo_costo > 0:
            margen = (obj.precio_base - obj.articulo.ultimo_costo) / obj.articulo.ultimo_costo * 100
            color = '#28a745' if margen >= 0 else '#dc3545'
            margen_texto = f'{margen:.2f}'  # ← FORMATEAR PRIMERO
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}%</span>',
                color, margen_texto  # ← USAR VARIABLE FORMATEADA
            )
        return '-'
    margen_badge.short_description = 'Margen'
    
    def bajo_costo_badge(self, obj):
        if obj.bajo_costo:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 10px; border-radius: 3px;">⚠ BAJO COSTO</span>'
            )
        return format_html(
            '<span style="background-color: #e9ecef; color: black; padding: 3px 10px; border-radius: 3px;">NORMAL</span>'
        )
    bajo_costo_badge.short_description = 'Estado'


@admin.register(ReglaPrecio)
class ReglaPrecioAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'lista_precio', 'tipo_regla', 'prioridad',
        'tipo_descuento', 'valor_descuento', 'activo'
    ]
    list_filter = ['tipo_regla', 'tipo_descuento', 'activo', 'lista_precio__empresa']
    search_fields = ['nombre', 'lista_precio__nombre']
    autocomplete_fields = ['lista_precio', 'linea_articulo', 'grupo_articulo']
    
    fieldsets = (
        ('Información General', {
            'fields': ('lista_precio', 'nombre', 'tipo_regla', 'prioridad', 'activo')
        }),
        ('Filtros de Aplicación', {
            'fields': ('canal', 'linea_articulo', 'grupo_articulo')
        }),
        ('Condiciones de Escala', {
            'fields': ('cantidad_minima', 'cantidad_maxima', 'monto_minimo', 'monto_maximo')
        }),
        ('Descuento', {
            'fields': ('tipo_descuento', 'valor_descuento')
        }),
    )


class DetalleCombinacionInline(admin.TabularInline):
    model = DetalleCombinacionProducto
    extra = 1
    fields = ['articulo', 'grupo_articulo', 'linea_articulo', 'cantidad_requerida']
    autocomplete_fields = ['articulo', 'grupo_articulo', 'linea_articulo']


@admin.register(CombinacionProducto)
class CombinacionProductoAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'lista_precio', 'cantidad_minima',
        'tipo_descuento', 'valor_descuento', 'activo'
    ]
    list_filter = ['lista_precio__empresa', 'lista_precio', 'tipo_descuento', 'activo']
    search_fields = ['nombre', 'descripcion']
    inlines = [DetalleCombinacionInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('lista_precio', 'nombre', 'descripcion', 'cantidad_minima', 'activo')
        }),
        ('Descuento', {
            'fields': ('tipo_descuento', 'valor_descuento')
        }),
    )


@admin.register(AuditoriaPrecios)
class AuditoriaPreciosAdmin(admin.ModelAdmin):
    list_display = ['tipo_operacion', 'tabla', 'registro_id', 'usuario', 'fecha_operacion']
    list_filter = ['tipo_operacion', 'tabla', 'fecha_operacion']
    search_fields = ['usuario', 'tabla']
    date_hierarchy = 'fecha_operacion'
    readonly_fields = [
        'tipo_operacion', 'tabla', 'registro_id', 'usuario',
        'datos_anteriores', 'datos_nuevos', 'fecha_operacion'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Configurar búsqueda de autocompletado
admin.site.site_header = "Sistema de Gestión de Precios"
admin.site.site_title = "Admin Precios"
admin.site.index_title = "Panel de Administración"