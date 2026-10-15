"""Avisos al móvil por Telegram (opcional) y vigilancia de la cartera real.

Para activarlos (gratis):
1. En Telegram, habla con @BotFather → /newbot → copia el token.
2. Escribe cualquier cosa a tu bot y abre https://api.telegram.org/bot<TOKEN>/getUpdates para ver tu chat id.
3. En GitHub → tu repositorio → Settings → Secrets and variables → Actions, crea TELEGRAM_TOKEN y TELEGRAM_CHAT_ID.
"""

from __future__ import annotations

from . import bankinter


def enviar_telegram(token: str, chat_id: str, texto: str) -> bool:
    import requests

    partes = [texto[i:i + 3900] for i in range(0, len(texto), 3900)] or [""]
    ok = True
    for parte in partes:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id, "text": parte, "disable_web_page_preview": True}, timeout=20)
        ok &= r.ok
    return ok


def avisos_cartera(cartera_real: dict, ranking: list[dict], umbral_venta: int = 40) -> list[str]:
    """Consejos para cada posición real, usando el informe del día."""
    por_ticker = {r["ticker"]: r for r in ranking}
    avisos = []
    for t, pos in (cartera_real or {}).get("posiciones", {}).items():
        r = por_ticker.get(t)
        if not r:
            continue
        stop_sug = max(r.get("stop") or 0, pos.get("stop") or 0) or None
        nivel, texto = bankinter.consejo_posicion(r["precio"], pos["precio_medio"], pos.get("stop"), stop_sug,
                                                  r["puntuacion"], umbral_venta, r.get("resultados_pronto", False))
        if nivel != "mantener":
            avisos.append(f"• {r['nombre']}: {texto}")
    return avisos


def mensaje_diario(informe: dict, avisos_propios: list[str] | None = None) -> str:
    por_ticker = {r["ticker"]: r for r in informe.get("ranking", [])}
    lineas = [f"📈 Bolsa · {informe['fecha']}", ""]
    lineas += [f"• {f}" for f in informe.get("resumen", [])]
    if informe.get("ideas"):
        lineas += ["", "💡 Ideas del día:"]
        for t in informe["ideas"]:
            r = por_ticker.get(t, {})
            nota = f"nota {r['nota']}/100" if r.get("nota") is not None else f"{r.get('puntuacion')} pts"
            riesgo = f" · riesgo de caída {r['riesgo_nivel']}" if r.get("riesgo_nivel") else ""
            stop = f" · stop {r['stop']:.2f}" if r.get("stop") else ""
            lineas.append(f"  - {r.get('nombre', t)}: {nota}{riesgo}{stop}")
    for clave, c in informe.get("carteras", {}).items():
        if c.get("composicion"):
            lineas += ["", f"📦 {c['nombre']} este mes: " + ", ".join(por_ticker.get(x["ticker"], {}).get("nombre", x["ticker"])
                                                                for x in c["composicion"][:10])]
            break
    if avisos_propios:
        lineas += ["", "🏦 Tu cartera:"] + avisos_propios
    lineas += ["", "Herramienta educativa, no es asesoramiento financiero."]
    return "\n".join(lineas)
