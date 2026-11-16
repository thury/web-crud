from django.contrib import admin
from django.urls import path

admin.site.site_header = "Inventario y pedidos"
admin.site.site_title = "Inventario y pedidos"
admin.site.index_title = "Panel de administración"

urlpatterns = [
    path("admin/", admin.site.urls),
]
