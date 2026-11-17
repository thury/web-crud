from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CampoPersonalizado, Pedido, Producto


class VistasBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("ana", password="clave-larga-123")
        cls.producto = Producto.objects.create(sku="A1", nombre="Jabón", precio="10.00", stock=5)

    def entrar(self):
        self.client.force_login(self.usuario)


class AccesoTests(VistasBase):
    def test_sin_sesion_redirige_al_login(self):
        for nombre in ["inicio", "producto_lista", "cliente_lista", "pedido_lista"]:
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 302, nombre)
            self.assertTrue(respuesta["Location"].startswith(reverse("login")), nombre)

    def test_acciones_de_pedido_piden_sesion(self):
        pedido = Pedido.objects.create()
        url = reverse("pedido_accion", args=[pedido.pk, "confirmar"])
        self.assertEqual(self.client.post(url).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.BORRADOR)

    def test_login_correcto_lleva_al_inicio(self):
        respuesta = self.client.post(
            reverse("login"), {"username": "ana", "password": "clave-larga-123"}
        )
        self.assertRedirects(respuesta, reverse("inicio"))


class ProductoTests(VistasBase):
    def test_crear_producto_con_columna_personalizada(self):
        CampoPersonalizado.objects.create(
            entidad="producto", nombre="Marca", tipo="texto", requerido=True
        )
        self.entrar()
        respuesta = self.client.post(
            reverse("producto_nuevo"),
            {
                "sku": "B2",
                "nombre": "Cloro",
                "precio": "25.50",
                "stock": 3,
                "stock_minimo": 1,
                "activo": "on",
                "extra_marca": "Clorox",
            },
        )
        self.assertRedirects(respuesta, reverse("producto_lista"))
        self.assertEqual(Producto.objects.get(sku="B2").extras["marca"], "Clorox")

    def test_lista_muestra_la_columna_personalizada(self):
        CampoPersonalizado.objects.create(entidad="producto", nombre="Marca")
        self.producto.extras = {"marca": "Zote"}
        self.producto.save()
        self.entrar()
        respuesta = self.client.get(reverse("producto_lista"))
        self.assertContains(respuesta, "Marca")
        self.assertContains(respuesta, "Zote")

    def test_buscador(self):
        Producto.objects.create(sku="C3", nombre="Suavizante", precio="30", stock=1)
        self.entrar()
        respuesta = self.client.get(reverse("producto_lista"), {"q": "suav"})
        self.assertContains(respuesta, "Suavizante")
        self.assertNotContains(respuesta, "Jabón")

    def test_borrar_producto_usado_en_pedido_avisa_y_no_falla(self):
        pedido = Pedido.objects.create()
        pedido.lineas.create(producto=self.producto, cantidad=1)
        self.entrar()
        respuesta = self.client.post(reverse("producto_borrar", args=[self.producto.pk]))
        self.assertRedirects(respuesta, reverse("producto_lista"))
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())


class PedidoFlujoTests(VistasBase):
    def test_flujo_completo_descuenta_y_devuelve_stock(self):
        self.entrar()
        self.client.post(reverse("pedido_nuevo"), {"notas": ""})
        pedido = Pedido.objects.get()

        self.client.post(
            reverse("linea_agregar", args=[pedido.pk]),
            {"producto": self.producto.pk, "cantidad": 2},
        )
        self.assertEqual(pedido.lineas.count(), 1)

        self.client.post(reverse("pedido_accion", args=[pedido.pk, "confirmar"]))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 3)

        self.client.post(reverse("pedido_accion", args=[pedido.pk, "cancelar"]))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)

    def test_no_confirma_con_stock_insuficiente(self):
        self.entrar()
        pedido = Pedido.objects.create()
        pedido.lineas.create(producto=self.producto, cantidad=99)
        self.client.post(reverse("pedido_accion", args=[pedido.pk, "confirmar"]))
        pedido.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.BORRADOR)
        self.assertEqual(self.producto.stock, 5)

    def test_pedido_confirmado_no_acepta_lineas_ni_edicion(self):
        self.entrar()
        pedido = Pedido.objects.create()
        pedido.lineas.create(producto=self.producto, cantidad=1)
        pedido.confirmar()
        self.client.post(
            reverse("linea_agregar", args=[pedido.pk]),
            {"producto": self.producto.pk, "cantidad": 1},
        )
        self.assertEqual(pedido.lineas.count(), 1)
        self.assertEqual(self.client.get(reverse("pedido_editar", args=[pedido.pk])).status_code, 404)

    def test_accion_desconocida_da_404(self):
        self.entrar()
        pedido = Pedido.objects.create()
        respuesta = self.client.post(reverse("pedido_accion", args=[pedido.pk, "borrar_todo"]))
        self.assertEqual(respuesta.status_code, 404)

    def test_acciones_no_aceptan_get(self):
        self.entrar()
        pedido = Pedido.objects.create()
        respuesta = self.client.get(reverse("pedido_accion", args=[pedido.pk, "confirmar"]))
        self.assertEqual(respuesta.status_code, 405)
