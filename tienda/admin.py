from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .forms import FormularioConExtras, formulario_con_extras
from .models import CampoPersonalizado, Cliente, LineaPedido, Pedido, Producto


class AdminConExtras(admin.ModelAdmin):
    """Muestra en el formulario las columnas personalizadas del modelo."""

    exclude = ("extras",)

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = formulario_con_extras(FormularioConExtras, self.model.ENTIDAD)
        return super().get_form(request, obj, **kwargs)


@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "entidad", "tipo", "requerido", "activo", "orden")
    list_filter = ("entidad", "activo")
    list_editable = ("orden", "activo")

    def get_readonly_fields(self, request, obj=None):
        # Cambiar sección o tipo de una columna con datos los dejaría inconsistentes.
        return ("entidad", "tipo") if obj else ()


@admin.register(Producto)
class ProductoAdmin(AdminConExtras):
    list_display = ("sku", "nombre", "precio", "stock", "stock_minimo", "stock_bajo", "activo")
    list_filter = ("activo",)
    search_fields = ("sku", "nombre")

    @admin.display(boolean=True, description="Stock bajo")
    def stock_bajo(self, obj):
        return obj.stock_bajo


@admin.register(Cliente)
class ClienteAdmin(AdminConExtras):
    list_display = ("nombre", "telefono", "email")
    search_fields = ("nombre", "telefono", "email")


class LineaPedidoInline(admin.TabularInline):
    model = LineaPedido
    extra = 1
    fields = ("producto", "cantidad", "precio_unitario", "subtotal")
    readonly_fields = ("subtotal",)
    autocomplete_fields = ("producto",)

    # Confirmado el pedido, sus líneas ya no se tocan (el stock ya se descontó).
    def _abierto(self, obj):
        return obj is None or obj.editable

    def has_add_permission(self, request, obj=None):
        return self._abierto(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._abierto(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._abierto(obj) and super().has_delete_permission(request, obj)


@admin.register(Pedido)
class PedidoAdmin(AdminConExtras):
    list_display = ("__str__", "cliente", "fecha", "estado", "total")
    list_filter = ("estado",)
    search_fields = ("cliente__nombre",)
    autocomplete_fields = ("cliente",)
    readonly_fields = ("estado", "total")
    inlines = [LineaPedidoInline]
    actions = ["confirmar", "entregar", "cancelar"]

    def _aplicar(self, request, queryset, accion):
        hechos = 0
        for pedido in queryset:
            try:
                getattr(pedido, accion)()
                hechos += 1
            except ValidationError as error:
                self.message_user(
                    request, f"{pedido}: {' '.join(error.messages)}", messages.ERROR
                )
        if hechos:
            self.message_user(request, f"{hechos} pedido(s) actualizado(s).", messages.SUCCESS)

    @admin.action(description="Confirmar pedidos (descuenta el stock)")
    def confirmar(self, request, queryset):
        self._aplicar(request, queryset, "confirmar")

    @admin.action(description="Marcar como entregados")
    def entregar(self, request, queryset):
        self._aplicar(request, queryset, "entregar")

    @admin.action(description="Cancelar pedidos (devuelve el stock si estaban confirmados)")
    def cancelar(self, request, queryset):
        self._aplicar(request, queryset, "cancelar")
