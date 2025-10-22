from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta
from rest_framework.test import APITestCase
from rest_framework import status

from .models import (
    Empresa, Sucursal, LineaArticulo, GrupoArticulo, Articulo,
    ListaPrecio, PrecioArticulo, ReglaPrecio, CombinacionProducto,
    DetalleCombinacionProducto
)
from .services import PrecioService


class ModelosTestCase(TestCase):
    """Pruebas para los modelos"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            ruc="20123456789",
            activo=True
        )
        
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal Central",
            codigo="SUC001",
            activo=True
        )
        
        self.linea = LineaArticulo.objects.create(
            nombre="Electrónicos",
            codigo="ELEC",
            activo=True
        )
        
        self.grupo = GrupoArticulo.objects.create(
            linea=self.linea,
            nombre="Laptops",
            codigo="LAP",
            activo=True
        )
        
        self.articulo = Articulo.objects.create(
            grupo=self.grupo,
            codigo="LAP001",
            nombre="Laptop HP",
            ultimo_costo=Decimal('1000.00'),
            activo=True
        )
    
    def test_crear_empresa(self):
        """Verificar creación de empresa"""
        self.assertEqual(self.empresa.nombre, "Empresa Test")
        self.assertTrue(self.empresa.activo)
    
    def test_crear_articulo(self):
        """Verificar creación de artículo"""
        self.assertEqual(self.articulo.nombre, "Laptop HP")
        self.assertEqual(self.articulo.ultimo_costo, Decimal('1000.00'))
    
    def test_lista_precio_vigente(self):
        """Verificar vigencia de lista"""
        lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Test",
            tipo="GENERAL",
            fecha_inicio=date.today() - timedelta(days=10),
            fecha_fin=date.today() + timedelta(days=10),
            activo=True
        )
        
        self.assertTrue(lista.esta_vigente())
    
    def test_lista_precio_no_vigente(self):
        """Verificar lista no vigente"""
        lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Expirada",
            tipo="GENERAL",
            fecha_inicio=date.today() - timedelta(days=20),
            fecha_fin=date.today() - timedelta(days=10),
            activo=True
        )
        
        self.assertFalse(lista.esta_vigente())
    
    def test_precio_bajo_costo_sin_autorizacion(self):
        """Verificar validación de precio bajo costo"""
        lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Test",
            tipo="GENERAL",
            fecha_inicio=date.today(),
            activo=True
        )
        
        precio = PrecioArticulo(
            lista_precio=lista,
            articulo=self.articulo,
            precio_base=Decimal('800.00'),  # Menor al costo de 1000
            bajo_costo=False,
            autorizado_bajo_costo=False,
            descuento_proveedor=0
        )
        
        with self.assertRaises(ValidationError):
            precio.full_clean()
    
    def test_precio_bajo_costo_con_descuento_proveedor(self):
        """Verificar precio bajo costo con descuento de proveedor"""
        lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Test",
            tipo="GENERAL",
            fecha_inicio=date.today(),
            activo=True
        )
        
        precio = PrecioArticulo(
            lista_precio=lista,
            articulo=self.articulo,
            precio_base=Decimal('800.00'),
            bajo_costo=True,
            autorizado_bajo_costo=False,
            descuento_proveedor=Decimal('60.00')
        )
        
        # No debe lanzar error
        precio.full_clean()
        self.assertTrue(precio.bajo_costo)


class PrecioServiceTestCase(TestCase):
    """Pruebas para el servicio de precios"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            ruc="20123456789"
        )
        
        self.linea = LineaArticulo.objects.create(
            nombre="Electrónicos",
            codigo="ELEC"
        )
        
        self.grupo = GrupoArticulo.objects.create(
            linea=self.linea,
            nombre="Laptops",
            codigo="LAP"
        )
        
        self.articulo = Articulo.objects.create(
            grupo=self.grupo,
            codigo="LAP001",
            nombre="Laptop HP",
            ultimo_costo=Decimal('1000.00')
        )
        
        self.lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Minorista",
            tipo="MINORISTA",
            canal="TIENDA",
            fecha_inicio=date.today() - timedelta(days=10),
            activo=True
        )
        
        self.precio_base = PrecioArticulo.objects.create(
            lista_precio=self.lista,
            articulo=self.articulo,
            precio_base=Decimal('1500.00')
        )
    
    def test_obtener_lista_vigente(self):
        """Verificar obtención de lista vigente"""
        lista = PrecioService.obtener_lista_vigente(
            empresa_id=self.empresa.id,
            canal="TIENDA"
        )
        
        self.assertIsNotNone(lista)
        self.assertEqual(lista.nombre, "Lista Minorista")
    
    def test_calcular_precio_base(self):
        """Verificar cálculo de precio base"""
        resultado = PrecioService.calcular_precio(
            empresa_id=self.empresa.id,
            articulo_id=self.articulo.id,
            cantidad=Decimal('1')
        )
        
        self.assertEqual(resultado['precio_base'], 1500.0)
        self.assertEqual(resultado['precio_final'], 1500.0)
        self.assertEqual(len(resultado['reglas_aplicadas']), 0)
    
    def test_calcular_precio_con_regla_escala_unidades(self):
        """Verificar cálculo con regla de escala de unidades"""
        # Crear regla: 10% descuento por 10+ unidades
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento por volumen",
            tipo_regla="ESCALA_UNIDADES",
            prioridad=10,
            cantidad_minima=Decimal('10'),
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('10'),
            activo=True
        )
        
        resultado = PrecioService.calcular_precio(
            empresa_id=self.empresa.id,
            articulo_id=self.articulo.id,
            cantidad=Decimal('15')
        )
        
        self.assertEqual(resultado['precio_base'], 1500.0)
        self.assertEqual(resultado['precio_final'], 1350.0)  # 1500 - 10%
        self.assertEqual(len(resultado['reglas_aplicadas']), 1)
        self.assertEqual(resultado['reglas_aplicadas'][0]['tipo'], 'ESCALA_UNIDADES')
    
    def test_calcular_precio_con_regla_canal(self):
        """Verificar cálculo con regla por canal"""
        # Crear regla: 5% descuento para canal TIENDA
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento tienda física",
            tipo_regla="CANAL",
            canal="TIENDA",
            prioridad=5,
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('5'),
            activo=True
        )
        
        resultado = PrecioService.calcular_precio(
            empresa_id=self.empresa.id,
            articulo_id=self.articulo.id,
            cantidad=Decimal('1'),
            canal="TIENDA"
        )
        
        self.assertEqual(resultado['precio_final'], 1425.0)  # 1500 - 5%
        self.assertEqual(len(resultado['reglas_aplicadas']), 1)
    
    def test_calcular_precio_con_multiples_reglas(self):
        """Verificar cálculo con múltiples reglas aplicadas"""
        # Regla por canal: 5% descuento
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento tienda",
            tipo_regla="CANAL",
            canal="TIENDA",
            prioridad=5,
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('5'),
            activo=True
        )
        
        # Regla por escala: 10% descuento adicional
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento por volumen",
            tipo_regla="ESCALA_UNIDADES",
            prioridad=10,
            cantidad_minima=Decimal('10'),
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('10'),
            activo=True
        )
        
        resultado = PrecioService.calcular_precio(
            empresa_id=self.empresa.id,
            articulo_id=self.articulo.id,
            cantidad=Decimal('15'),
            canal="TIENDA"
        )
        
        # 1500 - 5% = 1425
        # 1425 - 10% = 1282.5
        self.assertAlmostEqual(resultado['precio_final'], 1282.5, places=2)
        self.assertEqual(len(resultado['reglas_aplicadas']), 2)
    
    def test_validar_costo(self):
        """Verificar validación de costo"""
        resultado_valido = PrecioService.validar_costo(
            self.articulo,
            Decimal('1200.00')
        )
        
        self.assertTrue(resultado_valido['valido'])
        self.assertFalse(resultado_valido['requiere_autorizacion'])
        
        resultado_bajo_costo = PrecioService.validar_costo(
            self.articulo,
            Decimal('800.00')
        )
        
        self.assertFalse(resultado_bajo_costo['valido'])
        self.assertTrue(resultado_bajo_costo['requiere_autorizacion'])


class CombinacionProductoTestCase(TestCase):
    """Pruebas para combinaciones de productos"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        self.empresa = Empresa.objects.create(nombre="Empresa Test", ruc="20123456789")
        
        self.linea = LineaArticulo.objects.create(nombre="Bebidas", codigo="BEB")
        self.grupo = GrupoArticulo.objects.create(linea=self.linea, nombre="Gaseosas", codigo="GAS")
        
        self.articulo1 = Articulo.objects.create(
            grupo=self.grupo,
            codigo="COCA001",
            nombre="Coca Cola 1L",
            ultimo_costo=Decimal('3.00')
        )
        
        self.articulo2 = Articulo.objects.create(
            grupo=self.grupo,
            codigo="FANTA001",
            nombre="Fanta 1L",
            ultimo_costo=Decimal('3.00')
        )
        
        self.lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Test",
            tipo="GENERAL",
            fecha_inicio=date.today(),
            activo=True
        )
        
        PrecioArticulo.objects.create(
            lista_precio=self.lista,
            articulo=self.articulo1,
            precio_base=Decimal('5.00')
        )
        
        PrecioArticulo.objects.create(
            lista_precio=self.lista,
            articulo=self.articulo2,
            precio_base=Decimal('5.00')
        )
    
    def test_combinacion_de_productos(self):
        """Verificar descuento por combinación de productos"""
        # Crear combo: 2 gaseosas = 15% descuento
        combo = CombinacionProducto.objects.create(
            lista_precio=self.lista,
            nombre="Combo 2 Gaseosas",
            cantidad_minima=2,
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('15'),
            activo=True
        )
        
        # Agregar artículos al combo
        DetalleCombinacionProducto.objects.create(
            combinacion=combo,
            grupo_articulo=self.grupo,
            cantidad_requerida=2
        )
        
        # Items del pedido
        items_pedido = [
            {'articulo_id': self.articulo1.id, 'cantidad': 1},
            {'articulo_id': self.articulo2.id, 'cantidad': 1}
        ]
        
        resultado = PrecioService.calcular_precio(
            empresa_id=self.empresa.id,
            articulo_id=self.articulo1.id,
            cantidad=Decimal('1'),
            items_pedido=items_pedido
        )
        
        # 5.00 - 15% = 4.25
        self.assertEqual(resultado['precio_final'], 4.25)
        self.assertTrue(any(r['tipo'] == 'COMBINACION' for r in resultado['reglas_aplicadas']))


class APITestCase(APITestCase):
    """Pruebas para la API REST"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        self.empresa = Empresa.objects.create(nombre="Empresa API", ruc="20987654321")
        
        self.linea = LineaArticulo.objects.create(nombre="Tecnología", codigo="TEC")
        self.grupo = GrupoArticulo.objects.create(linea=self.linea, nombre="Celulares", codigo="CEL")
        
        self.articulo = Articulo.objects.create(
            grupo=self.grupo,
            codigo="CEL001",
            nombre="iPhone 13",
            ultimo_costo=Decimal('3000.00')
        )
        
        self.lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista API Test",
            tipo="GENERAL",
            fecha_inicio=date.today(),
            activo=True
        )
        
        self.precio = PrecioArticulo.objects.create(
            lista_precio=self.lista,
            articulo=self.articulo,
            precio_base=Decimal('4000.00')
        )
    
    def test_listar_empresas(self):
        """Verificar endpoint de listado de empresas"""
        response = self.client.get('/api/empresas/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_listar_articulos(self):
        """Verificar endpoint de listado de artículos"""
        response = self.client.get('/api/articulos/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_calcular_precio_endpoint(self):
        """Verificar endpoint de cálculo de precio"""
        data = {
            'empresa_id': self.empresa.id,
            'articulo_id': self.articulo.id,
            'cantidad': 1
        }
        
        response = self.client.post('/api/precios/calcular/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['precio_base'], 4000.0)
        self.assertEqual(response.data['articulo_nombre'], 'iPhone 13')
    
    def test_calcular_precio_multiple_endpoint(self):
        """Verificar endpoint de cálculo múltiple"""
        data = {
            'empresa_id': self.empresa.id,
            'items': [
                {'articulo_id': self.articulo.id, 'cantidad': 2}
            ]
        }
        
        response = self.client.post('/api/precios/calcular-multiple/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items_procesados'], 1)
    
    def test_obtener_lista_vigente_endpoint(self):
        """Verificar endpoint de lista vigente"""
        response = self.client.get(f'/api/listas-precios/vigentes/?empresa_id={self.empresa.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre'], 'Lista API Test')
    
    def test_crear_lista_precio(self):
        """Verificar creación de lista por API"""
        data = {
            'empresa': self.empresa.id,
            'nombre': 'Lista Nueva',
            'tipo': 'MAYORISTA',
            'fecha_inicio': date.today().isoformat(),
            'activo': True
        }
        
        response = self.client.post('/api/listas-precios/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nombre'], 'Lista Nueva')


class ReglasJerarquicasTestCase(TestCase):
    """Pruebas para verificar la aplicación jerárquica de reglas"""
    
    def setUp(self):
        """Configurar escenario complejo"""
        self.empresa = Empresa.objects.create(nombre="Empresa Test", ruc="20123456789")
        
        self.linea = LineaArticulo.objects.create(nombre="Alimentos", codigo="ALI")
        self.grupo = GrupoArticulo.objects.create(linea=self.linea, nombre="Lácteos", codigo="LAC")
        
        self.articulo = Articulo.objects.create(
            grupo=self.grupo,
            codigo="LECHE001",
            nombre="Leche Entera 1L",
            ultimo_costo=Decimal('3.50')
        )
        
        self.lista = ListaPrecio.objects.create(
            empresa=self.empresa,
            nombre="Lista Completa",
            tipo="GENERAL",
            canal="TIENDA",
            fecha_inicio=date.today(),
            activo=True
        )
        
        PrecioArticulo.objects.create(
            lista_precio=self.lista,
            articulo=self.articulo,
            precio_base=Decimal('5.00')
        )
        
        # Crear todas las reglas jerárquicas
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento Canal Tienda",
            tipo_regla="CANAL",
            canal="TIENDA",
            prioridad=1,
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('5'),
            activo=True
        )
        
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento Escala Unidades",
            tipo_regla="ESCALA_UNIDADES",
            cantidad_minima=Decimal('6'),
            prioridad=2,
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('10'),
            activo=True
        )
        
        ReglaPrecio.objects.create(
            lista_precio=self.lista,
            nombre="Descuento Monto Pedido",
            tipo_regla="MONTO_PEDIDO",
            monto_minimo=Decimal('100'),
            prioridad=3,
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal('5'),
            activo=True
        )
    
    def test_jerarquia_completa(self):
        """Verificar que se aplican todas las reglas en orden jerárquico"""
        resultado = PrecioService.calcular_precio(
            empresa_id=self.empresa.id,
            articulo_id=self.articulo.id,
            cantidad=Decimal('10'),
            canal="TIENDA",
            monto_pedido=Decimal('150')
        )
        
        # Precio base: 5.00
        # Canal -5%: 4.75
        # Escala -10%: 4.275
        # Monto pedido -5%: 4.06125
        
        self.assertAlmostEqual(resultado['precio_final'], 4.06, places=2)
        self.assertEqual(len(resultado['reglas_aplicadas']), 3)
        
        # Verificar orden de aplicación
        tipos_reglas = [r['tipo'] for r in resultado['reglas_aplicadas']]
        self.assertEqual(tipos_reglas, ['CANAL', 'ESCALA_UNIDADES', 'MONTO_PEDIDO'])


# Ejecutar tests
if __name__ == '__main__':
    import django
    django.setup()
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["precios"])