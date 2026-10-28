"""Expressoes geoespaciais reutilizadas nas consultas.

A coluna geom e do tipo geography (WGS 84). Nesse tipo, ST_Distance e
ST_DWithin trabalham em metros sobre o elipsoide, sem conversao manual.
"""

from geoalchemy2.elements import WKTElement
from sqlalchemy import func

from app.models import Ocorrencia

latitude = func.ST_Y(func.geometry(Ocorrencia.geom))
longitude = func.ST_X(func.geometry(Ocorrencia.geom))


def ponto(lat: float, lon: float):
    """Ponto geography para usar como parametro de consulta."""
    return func.geography(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326))


def ponto_para_gravar(lat: float, lon: float) -> WKTElement:
    # WKT usa a ordem (longitude latitude)
    return WKTElement(f"POINT({lon} {lat})", srid=4326)
