from django.urls import path

from . import views

urlpatterns = [
    path("", views.Inicio.as_view(), name="inicio"),
    # Productos
    path("productos/", views.ProductoLista.as_view(), name="producto_lista"),
    path("productos/nuevo/", views.ProductoNuevo.as_view(), name="producto_nuevo"),
    path("productos/<int:pk>/editar/", views.ProductoEditar.as_view(), name="producto_editar"),
    path("productos/<int:pk>/borrar/", views.ProductoBorrar.as_view(), name="producto_borrar"),
    # Clientes
    path("clientes/", views.ClienteLista.as_view(), name="cliente_lista"),
    path("clientes/nuevo/", views.ClienteNuevo.as_view(), name="cliente_nuevo"),
    path("clientes/<int:pk>/editar/", views.ClienteEditar.as_view(), name="cliente_editar"),
    path("clientes/<int:pk>/borrar/", views.ClienteBorrar.as_view(), name="cliente_borrar"),
    # Pedidos
    path("pedidos/", views.PedidoLista.as_view(), name="pedido_lista"),
    path("pedidos/nuevo/", views.PedidoNuevo.as_view(), name="pedido_nuevo"),
    path("pedidos/<int:pk>/", views.PedidoDetalle.as_view(), name="pedido_detalle"),
    path("pedidos/<int:pk>/editar/", views.PedidoEditar.as_view(), name="pedido_editar"),
    path("pedidos/<int:pk>/borrar/", views.PedidoBorrar.as_view(), name="pedido_borrar"),
    path("pedidos/<int:pk>/accion/<str:accion>/", views.PedidoAccion.as_view(), name="pedido_accion"),
    path("pedidos/<int:pk>/lineas/nueva/", views.LineaAgregar.as_view(), name="linea_agregar"),
    path(
        "pedidos/<int:pk>/lineas/<int:linea_pk>/borrar/",
        views.LineaBorrar.as_view(),
        name="linea_borrar",
    ),
]
