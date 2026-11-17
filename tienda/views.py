from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import F, ProtectedError, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    ClienteForm,
    LineaPedidoForm,
    PedidoForm,
    ProductoForm,
    campos_activos,
    formulario_con_extras,
)
from .models import CampoPersonalizado, Cliente, LineaPedido, Pedido, Producto


def mostrar(valor):
    """Texto para una columna personalizada en pantalla."""
    if valor is None:
        return ""
    if valor is True:
        return "Sí"
    if valor is False:
        return "No"
    return str(valor)


def errores_texto(error):
    """Une los mensajes de un ValidationError (de modelo) en una sola frase."""
    return " ".join(error.messages)


# --- Piezas compartidas -----------------------------------------------------


class Acceso(LoginRequiredMixin):
    """Todas las pantallas de la tienda piden sesión iniciada."""


class ListaConExtras(Acceso, ListView):
    """Lista paginada que añade las columnas personalizadas activas."""

    paginate_by = 25
    buscar_en = ()  # campos para el buscador ?q=

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.buscar_en:
            filtro = Q()
            for campo in self.buscar_en:
                filtro |= Q(**{f"{campo}__icontains": q})
            qs = qs.filter(filtro)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        columnas = campos_activos(self.model.ENTIDAD)
        ctx["columnas_extra"] = columnas
        ctx["q"] = self.request.GET.get("q", "").strip()
        ctx["filas"] = [
            (obj, [mostrar(obj.extras.get(c.clave)) for c in columnas])
            for obj in ctx["object_list"]
        ]
        return ctx


class FormularioConExtrasMixin:
    """Arma el formulario con las columnas personalizadas vigentes."""

    form_base = None
    template_name = "tienda/form.html"
    titulo = ""
    cancelar_url = reverse_lazy("inicio")

    def get_form_class(self):
        return formulario_con_extras(self.form_base, self.model.ENTIDAD)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = self.titulo
        ctx["cancelar_url"] = self.cancelar_url
        return ctx


class Borrar(Acceso, DeleteView):
    """Confirmación de borrado. Si hay pedidos que lo usan, avisa en vez de fallar."""

    template_name = "tienda/confirmar_borrado.html"
    mensaje_protegido = "No se puede borrar porque tiene pedidos asociados."
    cancelar_url = reverse_lazy("inicio")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancelar_url"] = self.cancelar_url
        return ctx

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.mensaje_protegido)
            return redirect(self.success_url)


# --- Inicio -----------------------------------------------------------------


class Inicio(Acceso, TemplateView):
    template_name = "tienda/inicio.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stock_bajo"] = Producto.objects.filter(activo=True, stock__lte=F("stock_minimo"))
        ctx["borradores"] = Pedido.objects.filter(estado=Pedido.Estado.BORRADOR).count()
        ctx["confirmados"] = Pedido.objects.filter(estado=Pedido.Estado.CONFIRMADO).count()
        return ctx


# --- Productos --------------------------------------------------------------


class ProductoLista(ListaConExtras):
    model = Producto
    template_name = "tienda/producto_list.html"
    buscar_en = ("nombre", "sku")


class ProductoNuevo(Acceso, FormularioConExtrasMixin, CreateView):
    model = Producto
    form_base = ProductoForm
    titulo = "Nuevo producto"
    cancelar_url = reverse_lazy("producto_lista")
    success_url = reverse_lazy("producto_lista")

    def form_valid(self, form):
        messages.success(self.request, "Producto guardado.")
        return super().form_valid(form)


class ProductoEditar(Acceso, FormularioConExtrasMixin, UpdateView):
    model = Producto
    form_base = ProductoForm
    titulo = "Editar producto"
    cancelar_url = reverse_lazy("producto_lista")
    success_url = reverse_lazy("producto_lista")

    def form_valid(self, form):
        messages.success(self.request, "Producto actualizado.")
        return super().form_valid(form)


class ProductoBorrar(Borrar):
    model = Producto
    success_url = reverse_lazy("producto_lista")
    cancelar_url = reverse_lazy("producto_lista")
    mensaje_protegido = "No se puede borrar: ya aparece en pedidos. Desactívalo en su lugar."


# --- Clientes ---------------------------------------------------------------


class ClienteLista(ListaConExtras):
    model = Cliente
    template_name = "tienda/cliente_list.html"
    buscar_en = ("nombre", "telefono", "email")


class ClienteNuevo(Acceso, FormularioConExtrasMixin, CreateView):
    model = Cliente
    form_base = ClienteForm
    titulo = "Nuevo cliente"
    cancelar_url = reverse_lazy("cliente_lista")
    success_url = reverse_lazy("cliente_lista")

    def form_valid(self, form):
        messages.success(self.request, "Cliente guardado.")
        return super().form_valid(form)


class ClienteEditar(Acceso, FormularioConExtrasMixin, UpdateView):
    model = Cliente
    form_base = ClienteForm
    titulo = "Editar cliente"
    cancelar_url = reverse_lazy("cliente_lista")
    success_url = reverse_lazy("cliente_lista")

    def form_valid(self, form):
        messages.success(self.request, "Cliente actualizado.")
        return super().form_valid(form)


class ClienteBorrar(Borrar):
    model = Cliente
    success_url = reverse_lazy("cliente_lista")
    cancelar_url = reverse_lazy("cliente_lista")
    mensaje_protegido = "No se puede borrar: tiene pedidos asociados."


# --- Pedidos ----------------------------------------------------------------


class PedidoLista(ListaConExtras):
    model = Pedido
    template_name = "tienda/pedido_list.html"

    def get_queryset(self):
        qs = super().get_queryset().select_related("cliente").prefetch_related("lineas__producto")
        estado = self.request.GET.get("estado", "")
        if estado in Pedido.Estado.values:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["estados"] = Pedido.Estado.choices
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        return ctx


class PedidoNuevo(Acceso, FormularioConExtrasMixin, CreateView):
    model = Pedido
    form_base = PedidoForm
    titulo = "Nuevo pedido"
    cancelar_url = reverse_lazy("pedido_lista")

    def get_success_url(self):
        return reverse("pedido_detalle", args=[self.object.pk])


class PedidoEditar(Acceso, FormularioConExtrasMixin, UpdateView):
    """Solo los pedidos en borrador se pueden editar."""

    model = Pedido
    form_base = PedidoForm
    titulo = "Editar pedido"

    def get_queryset(self):
        return Pedido.objects.filter(estado=Pedido.Estado.BORRADOR)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancelar_url"] = reverse("pedido_detalle", args=[self.object.pk])
        return ctx

    def get_success_url(self):
        return reverse("pedido_detalle", args=[self.object.pk])


class PedidoDetalle(Acceso, DetailView):
    model = Pedido
    template_name = "tienda/pedido_detail.html"
    context_object_name = "pedido"

    def get_queryset(self):
        return Pedido.objects.select_related("cliente").prefetch_related("lineas__producto")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pedido = self.object
        ctx["extras"] = [
            (c.nombre, mostrar(pedido.extras.get(c.clave)))
            for c in campos_activos(CampoPersonalizado.Entidad.PEDIDO)
        ]
        ctx["form_linea"] = LineaPedidoForm()
        return ctx


class PedidoBorrar(Borrar):
    """Solo se borran borradores; un pedido confirmado se cancela, no se borra."""

    model = Pedido
    success_url = reverse_lazy("pedido_lista")
    cancelar_url = reverse_lazy("pedido_lista")

    def get_queryset(self):
        return Pedido.objects.filter(estado=Pedido.Estado.BORRADOR)


class PedidoAccion(Acceso, View):
    """Confirmar, entregar o cancelar. Solo POST: cambia el stock."""

    http_method_names = ["post"]
    acciones = {
        "confirmar": "Pedido confirmado: el stock ya se descontó.",
        "entregar": "Pedido marcado como entregado.",
        "cancelar": "Pedido cancelado.",
    }

    def post(self, request, pk, accion):
        if accion not in self.acciones:
            raise Http404
        pedido = get_object_or_404(Pedido, pk=pk)
        try:
            getattr(pedido, accion)()
        except ValidationError as error:
            messages.error(request, errores_texto(error))
        else:
            messages.success(request, self.acciones[accion])
        return redirect("pedido_detalle", pk=pk)


class LineaAgregar(Acceso, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        if not pedido.editable:
            messages.error(request, "Este pedido ya no se puede modificar.")
            return redirect("pedido_detalle", pk=pk)
        form = LineaPedidoForm(request.POST)
        if form.is_valid():
            linea = form.save(commit=False)
            linea.pedido = pedido
            try:
                linea.save()
            except ValidationError as error:
                messages.error(request, errores_texto(error))
            else:
                messages.success(request, "Producto agregado.")
        else:
            detalle = " ".join(m for errores in form.errors.values() for m in errores)
            messages.error(request, f"Revisa la línea: {detalle}")
        return redirect("pedido_detalle", pk=pk)


class LineaBorrar(Acceso, View):
    http_method_names = ["post"]

    def post(self, request, pk, linea_pk):
        linea = get_object_or_404(LineaPedido, pk=linea_pk, pedido_id=pk)
        try:
            linea.delete()
        except ValidationError as error:
            messages.error(request, errores_texto(error))
        else:
            messages.success(request, "Línea quitada.")
        return redirect("pedido_detalle", pk=pk)
