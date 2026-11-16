from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify


class CampoPersonalizado(models.Model):
    """
    Una "columna extra" que el cliente define sin tocar código, como agregar
    una columna en Excel. Los valores se guardan en el campo `extras` (JSON)
    de cada Producto, Cliente o Pedido, indexados por `clave`.
    """

    class Entidad(models.TextChoices):
        PRODUCTO = "producto", "Producto"
        CLIENTE = "cliente", "Cliente"
        PEDIDO = "pedido", "Pedido"

    class Tipo(models.TextChoices):
        TEXTO = "texto", "Texto"
        NUMERO = "numero", "Número"
        FECHA = "fecha", "Fecha"
        SI_NO = "si_no", "Sí / No"
        LISTA = "lista", "Lista de opciones"

    entidad = models.CharField("Sección", max_length=20, choices=Entidad.choices)
    nombre = models.CharField(
        "Nombre de la columna", max_length=60, help_text="Como lo escribiría en Excel."
    )
    clave = models.SlugField(max_length=60, editable=False)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.TEXTO)
    opciones = models.TextField(blank=True, help_text="Solo para listas: una opción por línea.")
    requerido = models.BooleanField(default=False)
    activo = models.BooleanField(
        default=True, help_text="Desactivar oculta la columna sin borrar sus datos."
    )
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "columna personalizada"
        verbose_name_plural = "columnas personalizadas"
        ordering = ["entidad", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["entidad", "clave"], name="clave_unica_por_entidad")
        ]

    def __str__(self):
        return f"{self.get_entidad_display()}: {self.nombre}"

    @property
    def lista_opciones(self):
        return [o.strip() for o in self.opciones.splitlines() if o.strip()]

    def _generar_clave(self):
        return slugify(self.nombre).replace("-", "_") or "campo"

    def clean(self):
        super().clean()
        if self.tipo == self.Tipo.LISTA and not self.lista_opciones:
            raise ValidationError({"opciones": "Escribe al menos una opción, una por línea."})
        if not self.pk:
            clave = self._generar_clave()
            if CampoPersonalizado.objects.filter(entidad=self.entidad, clave=clave).exists():
                raise ValidationError(
                    {"nombre": "Ya existe una columna con ese nombre en esta sección."}
                )
            self.clave = clave

    def save(self, *args, **kwargs):
        if not self.clave:
            self.clave = self._generar_clave()
        super().save(*args, **kwargs)

    def campo_formulario(self):
        """Devuelve el campo de formulario de Django que corresponde al tipo."""
        comunes = {"label": self.nombre, "required": self.requerido}
        if self.tipo == self.Tipo.NUMERO:
            return forms.FloatField(**comunes)
        if self.tipo == self.Tipo.FECHA:
            widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            return forms.DateField(widget=widget, **comunes)
        if self.tipo == self.Tipo.SI_NO:
            return forms.BooleanField(required=False, label=self.nombre)
        if self.tipo == self.Tipo.LISTA:
            opciones = [("", "---------")] + [(o, o) for o in self.lista_opciones]
            return forms.ChoiceField(choices=opciones, **comunes)
        return forms.CharField(max_length=255, **comunes)

    def serializar(self, valor):
        """Convierte el valor limpio del formulario a algo que cabe en JSON."""
        if valor is None or valor == "":
            return None
        if self.tipo == self.Tipo.FECHA:
            return valor.isoformat()
        if self.tipo == self.Tipo.NUMERO:
            numero = float(valor)
            return int(numero) if numero.is_integer() else numero
        return valor


class ConCamposPersonalizados(models.Model):
    """Mezcla para los modelos que admiten columnas definidas por el cliente."""

    ENTIDAD = None  # cada modelo indica a qué sección de CampoPersonalizado pertenece

    extras = models.JSONField("Columnas personalizadas", default=dict, blank=True)

    class Meta:
        abstract = True


class Producto(ConCamposPersonalizados):
    ENTIDAD = CampoPersonalizado.Entidad.PRODUCTO

    sku = models.CharField("Código (SKU)", max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField("Descripción", blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField("Stock mínimo", default=0)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.sku} · {self.nombre}"

    @property
    def stock_bajo(self):
        return self.stock <= self.stock_minimo


class Cliente(ConCamposPersonalizados):
    ENTIDAD = CampoPersonalizado.Entidad.CLIENTE

    nombre = models.CharField(max_length=120)
    telefono = models.CharField("Teléfono", max_length=30, blank=True)
    email = models.EmailField("Correo", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Pedido(ConCamposPersonalizados):
    ENTIDAD = CampoPersonalizado.Entidad.PEDIDO

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        CONFIRMADO = "confirmado", "Confirmado"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    # cliente vacío = venta de mostrador
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="pedidos"
    )
    fecha = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Pedido #{self.pk}"

    @property
    def total(self):
        return sum((linea.subtotal for linea in self.lineas.all()), Decimal("0"))

    @property
    def editable(self):
        return self.estado == self.Estado.BORRADOR

    def _cantidades_por_producto(self):
        cantidades = {}
        for linea in self.lineas.all():
            cantidades[linea.producto_id] = cantidades.get(linea.producto_id, 0) + linea.cantidad
        return cantidades

    # Estas operaciones usan transaction.atomic(). Con SQLite configurado en
    # modo IMMEDIATE (ver settings.py) las escrituras se serializan, así que
    # revisar el stock y descontarlo no se puede cruzar con otra venta.

    @transaction.atomic
    def confirmar(self):
        """Borrador -> Confirmado. Descuenta el stock de cada producto."""
        if self.estado != self.Estado.BORRADOR:
            raise ValidationError("Solo se puede confirmar un pedido en borrador.")
        cantidades = self._cantidades_por_producto()
        if not cantidades:
            raise ValidationError("El pedido no tiene productos.")

        productos = Producto.objects.in_bulk(cantidades.keys())
        faltantes = [
            f"{productos[pid].nombre} (hay {productos[pid].stock}, pide {cant})"
            for pid, cant in cantidades.items()
            if productos[pid].stock < cant
        ]
        if faltantes:
            raise ValidationError("Stock insuficiente: " + "; ".join(faltantes) + ".")

        for pid, cant in cantidades.items():
            Producto.objects.filter(pk=pid).update(stock=F("stock") - cant)
        self.estado = self.Estado.CONFIRMADO
        self.save(update_fields=["estado"])

    @transaction.atomic
    def entregar(self):
        """Confirmado -> Entregado."""
        if self.estado != self.Estado.CONFIRMADO:
            raise ValidationError("Solo se puede entregar un pedido confirmado.")
        self.estado = self.Estado.ENTREGADO
        self.save(update_fields=["estado"])

    @transaction.atomic
    def cancelar(self):
        """Borrador o Confirmado -> Cancelado. Si estaba confirmado, devuelve el stock."""
        if self.estado == self.Estado.CONFIRMADO:
            for pid, cant in self._cantidades_por_producto().items():
                Producto.objects.filter(pk=pid).update(stock=F("stock") + cant)
        elif self.estado != self.Estado.BORRADOR:
            raise ValidationError("Este pedido ya no se puede cancelar.")
        self.estado = self.Estado.CANCELADO
        self.save(update_fields=["estado"])


class LineaPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="lineas")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    # Precio al momento de la venta: si el precio del producto cambia después,
    # los pedidos viejos no cambian. Vacío = usar el precio actual del producto.
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "línea de pedido"
        verbose_name_plural = "líneas de pedido"

    def __str__(self):
        return f"{self.cantidad} × {self.producto.nombre}"

    @property
    def subtotal(self):
        precio = self.precio_unitario if self.precio_unitario is not None else self.producto.precio
        return precio * self.cantidad

    def clean(self):
        super().clean()
        if self.producto_id and not self.pk and not self.producto.activo:
            raise ValidationError({"producto": "Este producto está desactivado."})

    def save(self, *args, **kwargs):
        if not self.pedido.editable:
            raise ValidationError("No se pueden modificar las líneas de un pedido ya confirmado.")
        if self.precio_unitario is None:
            self.precio_unitario = self.producto.precio
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.pedido.editable:
            raise ValidationError("No se pueden modificar las líneas de un pedido ya confirmado.")
        return super().delete(*args, **kwargs)
