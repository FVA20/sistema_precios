from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from precios.models import (
    Empresa, Sucursal, LineaArticulo, GrupoArticulo, Articulo,
    ListaPrecio, PrecioArticulo, ReglaPrecio, CombinacionProducto,
    DetalleCombinacionProducto
)


class Command(BaseCommand):
    help = 'Carga datos de demostración en el sistema de precios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Elimina todos los datos antes de cargar',
        )

    def handle(self, *args, **options):
        if options['limpiar']:
            self.stdout.write(self.style.WARNING('Limpiando datos existentes...'))
            self.limpiar_datos()

        self.stdout.write(self.style.SUCCESS('Cargando datos de demostración...'))
        
        # 1. Crear empresa y sucursales
        empresa = self.crear_empresa()
        self.stdout.write(self.style.SUCCESS(f'✓ Empresa creada: {empresa.nombre}'))
        
        sucursales = self.crear_sucursales(empresa)
        self.stdout.write(self.style.SUCCESS(f'✓ {len(sucursales)} sucursales creadas'))
        
        # 2. Crear catálogo de productos
        lineas = self.crear_lineas()
        self.stdout.write(self.style.SUCCESS(f'✓ {len(lineas)} líneas creadas'))
        
        grupos = self.crear_grupos(lineas)
        self.stdout.write(self.style.SUCCESS(f'✓ {len(grupos)} grupos creados'))
        
        articulos = self.crear_articulos(grupos)
        self.stdout.write(self.style.SUCCESS(f'✓ {len(articulos)} artículos creados'))
        
        # 3. Crear listas de precios
        listas = self.crear_listas_precios(empresa, sucursales)
        self.stdout.write(self.style.SUCCESS(f'✓ {len(listas)} listas de precios creadas'))
        
        # 4. Asignar precios a artículos
        total_precios = self.asignar_precios(listas, articulos)
        self.stdout.write(self.style.SUCCESS(f'✓ {total_precios} precios asignados'))
        
        # 5. Crear reglas de precio
        total_reglas = self.crear_reglas(listas, grupos)
        self.stdout.write(self.style.SUCCESS(f'✓ {total_reglas} reglas creadas'))
        
        # 6. Crear combinaciones
        total_combos = self.crear_combinaciones(listas, grupos, articulos)
        self.stdout.write(self.style.SUCCESS(f'✓ {total_combos} combinaciones creadas'))
        
        self.stdout.write(self.style.SUCCESS('\n¡Datos de demostración cargados exitosamente!'))
        self.mostrar_resumen()

    def limpiar_datos(self):
        """Elimina todos los datos del sistema"""
        CombinacionProducto.objects.all().delete()
        ReglaPrecio.objects.all().delete()
        PrecioArticulo.objects.all().delete()
        ListaPrecio.objects.all().delete()
        Articulo.objects.all().delete()
        GrupoArticulo.objects.all().delete()
        LineaArticulo.objects.all().delete()
        Sucursal.objects.all().delete()
        Empresa.objects.all().delete()

    def crear_empresa(self):
        """Crea empresa de demostración"""
        empresa, created = Empresa.objects.get_or_create(
            ruc="20123456789",
            defaults={
                'nombre': 'Distribuidora El Sol SAC',
                'activo': True
            }
        )
        return empresa

    def crear_sucursales(self, empresa):
        """Crea sucursales de demostración"""
        sucursales_data = [
            {'nombre': 'Sucursal Central', 'codigo': 'SUC001', 'direccion': 'Av. Principal 123, Lima'},
            {'nombre': 'Sucursal Norte', 'codigo': 'SUC002', 'direccion': 'Av. Norte 456, Lima'},
            {'nombre': 'Sucursal Sur', 'codigo': 'SUC003', 'direccion': 'Av. Sur 789, Lima'},
        ]
        
        sucursales = []
        for data in sucursales_data:
            sucursal, created = Sucursal.objects.get_or_create(
                empresa=empresa,
                codigo=data['codigo'],
                defaults={
                    'nombre': data['nombre'],
                    'direccion': data['direccion'],
                    'activo': True
                }
            )
            sucursales.append(sucursal)
        
        return sucursales

    def crear_lineas(self):
        """Crea líneas de artículos"""
        lineas_data = [
            {'nombre': 'Alimentos y Bebidas', 'codigo': 'ALI'},
            {'nombre': 'Electrónicos', 'codigo': 'ELEC'},
            {'nombre': 'Hogar y Limpieza', 'codigo': 'HOG'},
        ]
        
        lineas = []
        for data in lineas_data:
            linea, created = LineaArticulo.objects.get_or_create(
                codigo=data['codigo'],
                defaults={'nombre': data['nombre'], 'activo': True}
            )
            lineas.append(linea)
        
        return lineas

    def crear_grupos(self, lineas):
        """Crea grupos de artículos"""
        grupos_data = [
            {'linea': 0, 'nombre': 'Lácteos', 'codigo': 'LAC'},
            {'linea': 0, 'nombre': 'Bebidas Gaseosas', 'codigo': 'GAS'},
            {'linea': 0, 'nombre': 'Snacks', 'codigo': 'SNK'},
            {'linea': 1, 'nombre': 'Computadoras', 'codigo': 'COMP'},
            {'linea': 1, 'nombre': 'Celulares', 'codigo': 'CEL'},
            {'linea': 2, 'nombre': 'Detergentes', 'codigo': 'DET'},
        ]
        
        grupos = []
        for data in grupos_data:
            grupo, created = GrupoArticulo.objects.get_or_create(
                codigo=data['codigo'],
                defaults={
                    'linea': lineas[data['linea']],
                    'nombre': data['nombre'],
                    'activo': True
                }
            )
            grupos.append(grupo)
        
        return grupos

    def crear_articulos(self, grupos):
        """Crea artículos de demostración"""
        articulos_data = [
            # Lácteos
            {'grupo': 0, 'codigo': 'LECHE001', 'nombre': 'Leche Gloria Entera 1L', 'costo': 3.50},
            {'grupo': 0, 'codigo': 'YOGURT001', 'nombre': 'Yogurt Gloria Frutado 1L', 'costo': 4.00},
            {'grupo': 0, 'codigo': 'QUESO001', 'nombre': 'Queso Bonlé 500g', 'costo': 12.00},
            
            # Gaseosas
            {'grupo': 1, 'codigo': 'COCA001', 'nombre': 'Coca Cola 1L', 'costo': 2.50},
            {'grupo': 1, 'codigo': 'INCA001', 'nombre': 'Inca Kola 1L', 'costo': 2.50},
            {'grupo': 1, 'codigo': 'SPRITE001', 'nombre': 'Sprite 1L', 'costo': 2.50},
            
            # Snacks
            {'grupo': 2, 'codigo': 'PAPAS001', 'nombre': 'Papas Lays 150g', 'costo': 3.00},
            {'grupo': 2, 'codigo': 'CHOCO001', 'nombre': 'Chocolate Sublime', 'costo': 2.00},
            
            # Computadoras
            {'grupo': 3, 'codigo': 'LAP001', 'nombre': 'Laptop HP Pavilion i5', 'costo': 2500.00},
            {'grupo': 3, 'codigo': 'LAP002', 'nombre': 'Laptop Dell Inspiron i7', 'costo': 3500.00},
            
            # Celulares
            {'grupo': 4, 'codigo': 'CEL001', 'nombre': 'iPhone 13', 'costo': 3000.00},
            {'grupo': 4, 'codigo': 'CEL002', 'nombre': 'Samsung Galaxy S21', 'costo': 2800.00},
            
            # Detergentes
            {'grupo': 5, 'codigo': 'DET001', 'nombre': 'Ariel 1kg', 'costo': 12.00},
            {'grupo': 5, 'codigo': 'DET002', 'nombre': 'Bolívar 1kg', 'costo': 10.00},
        ]
        
        articulos = []
        for data in articulos_data:
            articulo, created = Articulo.objects.get_or_create(
                codigo=data['codigo'],
                defaults={
                    'grupo': grupos[data['grupo']],
                    'nombre': data['nombre'],
                    'ultimo_costo': Decimal(str(data['costo'])),
                    'unidad_medida': 'UND',
                    'activo': True
                }
            )
            articulos.append(articulo)
        
        return articulos

    def crear_listas_precios(self, empresa, sucursales):
        """Crea listas de precios"""
        hoy = date.today()
        
        listas_data = [
            {
                'nombre': 'Lista Mayorista 2024',
                'tipo': 'MAYORISTA',
                'canal': 'DISTRIBUIDOR',
                'sucursal': None
            },
            {
                'nombre': 'Lista Minorista Central',
                'tipo': 'MINORISTA',
                'canal': 'TIENDA',
                'sucursal': sucursales[0]
            },
            {
                'nombre': 'Lista Online',
                'tipo': 'ESPECIAL',
                'canal': 'ONLINE',
                'sucursal': None
            },
        ]
        
        listas = []
        for data in listas_data:
            lista, created = ListaPrecio.objects.get_or_create(
                empresa=empresa,
                nombre=data['nombre'],
                defaults={
                    'tipo': data['tipo'],
                    'canal': data['canal'],
                    'sucursal': data['sucursal'],
                    'fecha_inicio': hoy - timedelta(days=30),
                    'activo': True
                }
            )
            listas.append(lista)
        
        return listas

    def asignar_precios(self, listas, articulos):
        """Asigna precios a los artículos"""
        total = 0
        
        for lista in listas:
            # Margen según tipo de lista
            margen = {
                'MAYORISTA': 1.25,
                'MINORISTA': 1.40,
                'ESPECIAL': 1.35
            }.get(lista.tipo, 1.30)
            
            for articulo in articulos:
                precio_base = articulo.ultimo_costo * Decimal(str(margen))
                
                PrecioArticulo.objects.get_or_create(
                    lista_precio=lista,
                    articulo=articulo,
                    defaults={
                        'precio_base': precio_base.quantize(Decimal('0.01')),
                        'bajo_costo': False,
                        'autorizado_bajo_costo': False,
                        'descuento_proveedor': Decimal('0')
                    }
                )
                total += 1
        
        return total

    def crear_reglas(self, listas, grupos):
        """Crea reglas de precio"""
        total = 0
        
        for lista in listas:
            # Regla por canal
            if lista.canal:
                ReglaPrecio.objects.get_or_create(
                    lista_precio=lista,
                    nombre=f'Descuento {lista.canal}',
                    tipo_regla='CANAL',
                    defaults={
                        'canal': lista.canal,
                        'prioridad': 5,
                        'tipo_descuento': 'PORCENTAJE',
                        'valor_descuento': Decimal('5'),
                        'activo': True
                    }
                )
                total += 1
            
            # Regla por volumen para lácteos (grupo 0)
            if len(grupos) > 0:
                ReglaPrecio.objects.get_or_create(
                    lista_precio=lista,
                    nombre='Descuento volumen lácteos',
                    tipo_regla='ESCALA_UNIDADES',
                    defaults={
                        'grupo_articulo': grupos[0],
                        'cantidad_minima': Decimal('10'),
                        'prioridad': 10,
                        'tipo_descuento': 'PORCENTAJE',
                        'valor_descuento': Decimal('10'),
                        'activo': True
                    }
                )
                total += 1
            
            # Regla por monto de pedido
            ReglaPrecio.objects.get_or_create(
                lista_precio=lista,
                nombre='Descuento pedido grande',
                tipo_regla='MONTO_PEDIDO',
                defaults={
                    'monto_minimo': Decimal('500'),
                    'prioridad': 15,
                    'tipo_descuento': 'PORCENTAJE',
                    'valor_descuento': Decimal('3'),
                    'activo': True
                }
            )
            total += 1
        
        return total

    def crear_combinaciones(self, listas, grupos, articulos):
        """Crea combinaciones de productos"""
        total = 0
        
        # Combo gaseosas (grupo 1 si existe)
        if len(grupos) > 1:
            for lista in listas:
                combo, created = CombinacionProducto.objects.get_or_create(
                    lista_precio=lista,
                    nombre='Combo 2 Gaseosas',
                    defaults={
                        'descripcion': 'Descuento por compra de 2 gaseosas',
                        'cantidad_minima': 2,
                        'tipo_descuento': 'PORCENTAJE',
                        'valor_descuento': Decimal('15'),
                        'activo': True
                    }
                )
                
                if created:
                    DetalleCombinacionProducto.objects.create(
                        combinacion=combo,
                        grupo_articulo=grupos[1],
                        cantidad_requerida=2
                    )
                    total += 1
        
        return total

    def mostrar_resumen(self):
        """Muestra resumen de datos cargados"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE DATOS CARGADOS'))
        self.stdout.write('='*50)
        self.stdout.write(f'Empresas: {Empresa.objects.count()}')
        self.stdout.write(f'Sucursales: {Sucursal.objects.count()}')
        self.stdout.write(f'Líneas: {LineaArticulo.objects.count()}')
        self.stdout.write(f'Grupos: {GrupoArticulo.objects.count()}')
        self.stdout.write(f'Artículos: {Articulo.objects.count()}')
        self.stdout.write(f'Listas de Precios: {ListaPrecio.objects.count()}')
        self.stdout.write(f'Precios de Artículos: {PrecioArticulo.objects.count()}')
        self.stdout.write(f'Reglas de Precio: {ReglaPrecio.objects.count()}')
        self.stdout.write(f'Combinaciones: {CombinacionProducto.objects.count()}')
        self.stdout.write('='*50 + '\n')