from django import forms

from .models import CampoPersonalizado

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
