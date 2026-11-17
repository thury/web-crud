from django import forms

from .models import CampoPersonalizado, Cliente, LineaPedido, Pedido, Producto

PREFIJO = "extra_"


def campos_activos(entidad):
    """Columnas personalizadas vigentes de una sección (producto, cliente, pedido)."""
    return list(
        CampoPersonalizado.objects.filter(entidad=entidad, activo=True).order_by("orden", "nombre")
    )


class FormularioConExtras(forms.ModelForm):
    """
    Base para formularios de modelos con columnas personalizadas.

    No se usa directamente: `formulario_con_extras()` crea una subclase con un
    campo `extra_<clave>` por cada columna activa. Al guardar, los valores se
    escriben en `instance.extras` (JSON).
    """

    _campos_extras = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        guardados = self.instance.extras or {}
        for campo in self._campos_extras:
            if campo.clave in guardados:
                self.initial[PREFIJO + campo.clave] = guardados[campo.clave]

    def save(self, commit=True):
        extras = dict(self.instance.extras or {})
        for campo in self._campos_extras:
            extras[campo.clave] = campo.serializar(self.cleaned_data.get(PREFIJO + campo.clave))
        self.instance.extras = extras
        return super().save(commit=commit)


def formulario_con_extras(base, entidad):
    """Devuelve una subclase de `base` con las columnas personalizadas de `entidad`."""
    campos = campos_activos(entidad)
    atributos = {PREFIJO + c.clave: c.campo_formulario() for c in campos}
    atributos["_campos_extras"] = campos
    return type(f"{base.__name__}ConExtras", (base,), atributos)


class ProductoForm(FormularioConExtras):
    class Meta:
        model = Producto
        fields = ["sku", "nombre", "descripcion", "precio", "stock", "stock_minimo", "activo"]


class ClienteForm(FormularioConExtras):
    class Meta:
        model = Cliente
        fields = ["nombre", "telefono", "email"]


class PedidoForm(FormularioConExtras):
    class Meta:
        model = Pedido
        fields = ["cliente", "notas"]


class LineaPedidoForm(forms.ModelForm):
    """Una línea de pedido. Solo ofrece productos activos."""

    class Meta:
        model = LineaPedido
        fields = ["producto", "cantidad", "precio_unitario"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(activo=True)
        self.fields["precio_unitario"].help_text = "Déjalo vacío para usar el precio actual."
