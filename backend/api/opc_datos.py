


def listar_equipos_desde_db():
    from api.models import Equipo
    return Equipo.objects.all()

def get_equipos_desde_db():
    return listar_equipos_desde_db().filter(estado="Online")  # ✅ iterable