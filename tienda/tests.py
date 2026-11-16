from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .forms import FormularioConExtras, formulario_con_extras
from .models import CampoPersonalizado, Cliente, LineaPedido, Pedido, Producto


def crear_producto(sku="P1", precio="10.00", stock=5, **kwargs):
    return Producto.objects.create(
        sku=sku, nombre=f"Producto {sku}", precio=Decimal(precio), stock=stock, **kwargs
    )


class PedidosYStockTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(stock=5)
        self.pedido = Pedido.objects.create()

    def agregar(self, producto, cantidad):
        return LineaPedido.objects.create(pedido=self.pedido, producto=producto, cantidad=cantidad)

    def test_confirmar_descuenta_stock(self):
        self.agregar(self.producto, 3)
        self.pedido.confirmar()
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 2)
        self.assertEqual(self.pedido.estado, Pedido.Estado.CONFIRMADO)

    def test_stock_insuficiente_no_descuenta_nada(self):
        otro = crear_producto(sku="P2", stock=1)
        self.agregar(self.producto, 2)
        self.agregar(otro, 5)
        with self.assertRaises(ValidationError):
            self.pedido.confirmar()
        self.producto.refresh_from_db()
        otro.refresh_from_db()
        self.assertEqual((self.producto.stock, otro.stock), (5, 1))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.BORRADOR)

    def test_mismo_producto_en_dos_lineas_se_suma(self):
        self.agregar(self.producto, 3)
        self.agregar(self.producto, 3)
        with self.assertRaises(ValidationError):
            self.pedido.confirmar()

    def test_pedido_vacio_no_se_confirma(self):
        with self.assertRaises(ValidationError):
            self.pedido.confirmar()

    def test_cancelar_confirmado_devuelve_stock(self):
        self.agregar(self.producto, 4)
        self.pedido.confirmar()
        self.pedido.cancelar()
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)

    def test_entregado_no_se_cancela(self):
        self.agregar(self.producto, 1)
        self.pedido.confirmar()
        self.pedido.entregar()
        with self.assertRaises(ValidationError):
            self.pedido.cancelar()

    def test_lineas_no_se_modifican_tras_confirmar(self):
        linea = self.agregar(self.producto, 1)
        self.pedido.confirmar()
        linea.cantidad = 2
        with self.assertRaises(ValidationError):
            linea.save()
        with self.assertRaises(ValidationError):
            linea.delete()

    def test_precio_queda_congelado_en_la_linea(self):
        linea = self.agregar(self.producto, 2)
        self.producto.precio = Decimal("99.00")
        self.producto.save()
        linea.refresh_from_db()
        self.assertEqual(linea.precio_unitario, Decimal("10.00"))
        self.assertEqual(self.pedido.total, Decimal("20.00"))

    def test_producto_desactivado_no_se_puede_agregar(self):
        inactivo = crear_producto(sku="P3", activo=False)
        linea = LineaPedido(pedido=self.pedido, producto=inactivo, cantidad=1)
        with self.assertRaises(ValidationError):
            linea.full_clean()


class CamposPersonalizadosTests(TestCase):
    def test_clave_se_genera_y_no_se_repite(self):
        campo = CampoPersonalizado(entidad="producto", nombre="Código de barras")
        campo.full_clean()
        campo.save()
        self.assertEqual(campo.clave, "codigo_de_barras")

        repetido = CampoPersonalizado(entidad="producto", nombre="Codigo de barras")
        with self.assertRaises(ValidationError):
            repetido.full_clean()
        # en otra sección sí se puede repetir
        CampoPersonalizado(entidad="cliente", nombre="Código de barras").full_clean()

    def test_lista_exige_opciones(self):
        campo = CampoPersonalizado(entidad="producto", nombre="Talla", tipo="lista")
        with self.assertRaises(ValidationError):
            campo.full_clean()

    def test_formulario_valida_y_guarda_extras(self):
        CampoPersonalizado.objects.create(
            entidad="producto", nombre="Peso (kg)", tipo="numero", requerido=True
        )
        CampoPersonalizado.objects.create(
            entidad="producto", nombre="Talla", tipo="lista", opciones="CH\nM\nG"
        )
        CampoPersonalizado.objects.create(entidad="producto", nombre="Caduca", tipo="fecha")
        CampoPersonalizado.objects.create(entidad="producto", nombre="Orgánico", tipo="si_no")

        class ProductoForm(FormularioConExtras):
            class Meta:
                model = Producto
                fields = ["sku", "nombre", "precio", "stock", "stock_minimo", "activo"]

        Form = formulario_con_extras(ProductoForm, "producto")
        datos = {
            "sku": "X1",
            "nombre": "Camisa",
            "precio": "150",
            "stock": 3,
            "stock_minimo": 1,
            "activo": "on",
            "extra_talla": "M",
            "extra_caduca": "2027-01-31",
            "extra_organico": "on",
        }

        # falta la columna requerida
        self.assertFalse(Form(datos).is_valid())
        # opción que no está en la lista
        self.assertFalse(Form({**datos, "extra_peso_kg": "2", "extra_talla": "XXL"}).is_valid())

        form = Form({**datos, "extra_peso_kg": "2.5"})
        self.assertTrue(form.is_valid(), form.errors)
        producto = form.save()
        self.assertEqual(
            producto.extras,
            {"peso_kg": 2.5, "talla": "M", "caduca": "2027-01-31", "organico": True},
        )

        # al editar, los valores guardados aparecen como iniciales
        editar = Form(instance=producto)
        self.assertEqual(editar.initial["extra_talla"], "M")

    def test_columna_desactivada_se_oculta_pero_conserva_datos(self):
        campo = CampoPersonalizado.objects.create(entidad="cliente", nombre="Apodo")

        class ClienteForm(FormularioConExtras):
            class Meta:
                model = Cliente
                fields = ["nombre"]

        cliente = Cliente.objects.create(nombre="Ana", extras={"apodo": "Anita"})
        campo.activo = False
        campo.save()
        Form = formulario_con_extras(ClienteForm, "cliente")
        self.assertNotIn("extra_apodo", Form(instance=cliente).fields)
        form = Form({"nombre": "Ana María"}, instance=cliente)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().extras["apodo"], "Anita")


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            "admin", password="una-clave-larga-123"
        )
        CampoPersonalizado.objects.create(entidad="producto", nombre="Marca")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_formulario_de_producto_muestra_columna_personalizada(self):
        respuesta = self.client.get(reverse("admin:tienda_producto_add"))
        self.assertContains(respuesta, 'name="extra_marca"')

    def test_crear_producto_desde_el_admin_guarda_extras(self):
        respuesta = self.client.post(
            reverse("admin:tienda_producto_add"),
            {
                "sku": "A1",
                "nombre": "Taza",
                "descripcion": "",
                "precio": "50",
                "stock": "10",
                "stock_minimo": "2",
                "activo": "on",
                "extra_marca": "Acme",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Producto.objects.get(sku="A1").extras, {"marca": "Acme"})

    def test_confirmar_pedido_desde_la_accion_del_admin(self):
        producto = crear_producto(stock=5)
        pedido = Pedido.objects.create()
        LineaPedido.objects.create(pedido=pedido, producto=producto, cantidad=2)
        self.client.post(
            reverse("admin:tienda_pedido_changelist"),
            {"action": "confirmar", "_selected_action": [pedido.pk]},
        )
        producto.refresh_from_db()
        pedido.refresh_from_db()
        self.assertEqual(producto.stock, 3)
        self.assertEqual(pedido.estado, Pedido.Estado.CONFIRMADO)

    def test_pedido_confirmado_ya_no_acepta_lineas(self):
        producto = crear_producto(stock=5)
        pedido = Pedido.objects.create()
        LineaPedido.objects.create(pedido=pedido, producto=producto, cantidad=1)
        pedido.confirmar()
        respuesta = self.client.get(reverse("admin:tienda_pedido_change", args=[pedido.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "lineas-0-cantidad")
