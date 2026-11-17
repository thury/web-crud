from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "Inventario y pedidos"
admin.site.site_title = "Inventario y pedidos"
admin.site.index_title = "Panel de administración"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    # En Django 5 el cierre de sesión solo acepta POST (formulario con CSRF).
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("tienda.urls")),
]
