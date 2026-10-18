"""Del resultado de un turno del agente al JSON de la API (spec 008, research R7).

La interfaz solo muestra lo que el agente devuelve: los avisos son exactamente los del resultado
y nunca se deducen del texto. Toda la salida pasa por `redactar` (defensa en profundidad: la traza
ya viene redactada de #7).
"""

from __future__ import annotations

import json

from crediagil.agent.traza import ResultadoTurno
from crediagil.config import redactar

# Única tabla de rótulos: la interfaz pinta el rótulo que llega, no uno escrito a mano.
ROTULOS_AVISO = {
    "credito_preaprobado": "Crédito preaprobado",
    "informacion_solicitada": "Información solicitada",
    "escalamiento": "Escalado a un analista",
    "bloqueo_regla": "Bloqueado por una regla de negocio",
}


def turno_a_dict(resultado: ResultadoTurno, id_turno: int) -> dict:
    datos = {
        "id_turno": id_turno,
        "respuesta": resultado.respuesta,
        "error": resultado.error,
        "parada": resultado.parada.value,
        "razon_parada": resultado.razon_parada,
        "costo_usd": resultado.costo_usd,
        "avisos": [
            {
                "tipo": aviso.tipo,
                "rotulo": ROTULOS_AVISO.get(aviso.tipo, aviso.tipo),
                "contenido": aviso.contenido,
            }
            for aviso in resultado.avisos
        ],
        "traza": [
            {
                "tipo": evento.tipo,
                "nombre": evento.nombre,
                "entrada": evento.entrada,
                "salida": evento.salida,
                "es_error": evento.es_error,
                "de_subagente": evento.de_subagente,
                "stop_reason": evento.stop_reason,
            }
            for evento in resultado.traza
        ],
        "negaciones": [
            {
                "herramienta": n.herramienta,
                "codigo": n.codigo,
                "mensaje": n.mensaje,
                "accion": n.accion,
            }
            for n in resultado.negaciones
        ],
        "pedidos_informacion": [
            {"datos": list(p.datos), "motivo": p.motivo} for p in resultado.pedidos_informacion
        ],
    }
    # Se redacta el JSON completo y se vuelve a cargar: ningún campo escapa a la redacción.
    return json.loads(redactar(json.dumps(datos, ensure_ascii=False, default=str)))
