from types import SimpleNamespace as NS

import pytest

from bolsa import chat


class FakeStream:
    def __init__(self, mensaje, trozos):
        self.mensaje, self.trozos = mensaje, trozos

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter([NS(type="text", text=t) for t in self.trozos])

    def get_final_message(self):
        return self.mensaje


class FakeCliente:
    """Devuelve las respuestas preparadas en orden y guarda lo que se le pide."""

    def __init__(self, respuestas):
        self.respuestas, self.peticiones = list(respuestas), []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kw):
        self.peticiones.append(kw)
        mensaje, trozos = self.respuestas.pop(0)
        return FakeStream(mensaje, trozos)


def msg(contenido, stop="end_turn", entrada=1000, salida=200):
    return NS(content=contenido, stop_reason=stop,
              usage=NS(input_tokens=entrada, output_tokens=salida, cache_read_input_tokens=0))


def texto(t):
    return NS(type="text", text=t)


def test_respuesta_simple_streaming_coste_y_parametros():
    cli = FakeCliente([(msg([texto("El RSI mide...")]), ["El RSI ", "mide..."])])
    escrito = []
    res = chat.conversar(cli, "claude-opus-5-5", [], "¿Qué es el RSI?", "contexto", dict, lambda q: None,
                         escrito.append)
    assert res.texto == "El RSI mide..." and "".join(escrito) == "El RSI mide..."
    assert res.uso.coste_usd() == pytest.approx((1000 * 4 + 200 * 20) / 1e6)
    kw = cli.peticiones[0]
    assert kw["model"] == "claude-opus-5-5" and kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"] == {"effort": "medium"}
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert all(t["eager_input_streaming"] for t in kw["tools"])
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and "contexto" in kw["system"][1]["text"]
    assert kw["messages"][-1] == {"role": "user", "content": "¿Qué es el RSI?"}


def test_haiku_sin_fallback_y_con_historia():
    cli = FakeCliente([(msg([texto("ok")]), ["ok"])])
    historia = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola"}]
    chat.conversar(cli, "claude-haiku-5-5", historia, "¿y?", "", dict, lambda q: None)
    kw = cli.peticiones[0]
    assert "fallbacks" not in kw and len(kw["messages"]) == 3 and historia[-1]["content"] == "hola"


def test_bucle_de_herramientas_valida_y_devuelve_resultados():
    llamada = NS(type="tool_use", id="t1", name="datos_valor", input={"ticker": "idr.mc"})
    mala = NS(type="tool_use", id="t2", name="datos_valor", input={"ticker": "rm -rf /"})
    cli = FakeCliente([(msg([texto("Miro los datos."), llamada, mala], stop="tool_use"), ["Miro los datos."]),
                       (msg([texto("El RSI de Indra es 60.")]), ["El RSI de Indra es 60."])])
    pedidos = []
    res = chat.conversar(cli, "claude-opus-5-5", [], "RSI de Indra", "", lambda t: pedidos.append(t) or {"rsi_14": 60},
                         lambda q: None)
    assert pedidos == ["IDR.MC"]
    resultados = cli.peticiones[1]["messages"][-1]["content"]
    assert resultados[0]["tool_use_id"] == "t1" and "60" in resultados[0]["content"]
    assert resultados[1]["is_error"] is True
    assert res.texto.endswith("El RSI de Indra es 60.") and len(res.herramientas) == 2
    assert res.uso.entrada == 2000


def test_rechazo_y_tope_de_vueltas():
    cli = FakeCliente([(msg([], stop="refusal"), [])])
    assert chat.conversar(cli, "claude-opus-5-5", [], "x", "", dict, lambda q: None).rechazada
    bucle = NS(type="tool_use", id="t", name="buscar_valor", input={"consulta": "Indra"})
    cli = FakeCliente([(msg([bucle], stop="tool_use"), [])] * 3)
    res = chat.conversar(cli, "claude-opus-5-5", [], "x", "", dict, lambda q: {"symbol": "IDR.MC"}, max_vueltas=3)
    assert "varias consultas" in res.texto


def test_errores_de_la_api_pasan_a_modo_sin_conexion():
    import anthropic
    import httpx2

    def err(cls, codigo, mensaje):
        r = httpx2.Response(codigo, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
        return cls(mensaje, response=r, body=None)

    texto_, offline = chat.explicar_error(err(anthropic.BadRequestError, 400,
                                              "Your credit balance is too low to access the Anthropic API."))
    assert "saldo" in texto_ and offline
    assert chat.explicar_error(err(anthropic.AuthenticationError, 401, "invalid x-api-key"))[1]
    assert not chat.explicar_error(err(anthropic.RateLimitError, 429, "rate"))[1]


def test_modo_sin_conexion_y_pregunta_para_claude_ai():
    r = chat.respuesta_sin_conexion("¿Qué es un stop-loss y cómo pongo uno?")
    assert "**Stop-loss**" in r and "Poner un stop-loss" in r and "Apalancamiento" not in r
    assert "claude.ai" in chat.respuesta_sin_conexion("xyz qwerty")
    p = chat.pregunta_para_claude_ai("¿Vendo Indra?", "Su cartera: Indra 53 %")
    assert "Indra 53 %" in p and p.endswith("¿Vendo Indra?")


def test_contexto_resume_cartera_y_mercado():
    c = chat.contexto_usuario("15/10/2026", "Bankinter", "Moderado",
                              [{"ticker": "IDR.MC", "nombre": "Indra", "clase": "Acciones", "valor": 94_000,
                                "ganancia_pct": 3.8, "stop": None},
                               {"ticker": "SAN.MC", "nombre": "Santander", "clase": "Acciones", "valor": 30_000,
                                "ganancia_pct": -3.7, "stop": 11.0}],
                              {"hallazgos": [{"gravedad": "alta", "titulo": "Indra pesa el 53 %"}]},
                              {"semaforo": "verde", "vix": 17.5}, [{"lectura": "Oro: en tendencia bajista."}])
    assert "Indra (IDR.MC, Acciones): 76 % · +3,8 % · sin stop" in c and "stop 11,00" in c
    assert "Indra pesa el 53 %" in c and "VIX 17.5" in c and "Oro" in c


DATOS_INDRA = {"ticker": "IDR.MC", "nombre": "Indra", "ultimo_cierre": 62.68, "fecha": "2026-10-15",
               "variacion_1d_pct": 0.13, "variacion_1m_pct": 1.2, "variacion_1a_pct": 48.9,
               "tendencia": "alcista (sobre su media de 200 sesiones)", "distancia_al_maximo_1a_pct": -4.0,
               "volatilidad_anual_pct": 29, "rsi_14": 75,
               "fundamentales": {"PER": 19.1, "opinión de analistas": "buy", "número de analistas": 16},
               "app": {"veredicto": "Candidata a comprar", "explicacion": "x", "nota_0_100": 87,
                       "riesgo_de_caida": "normal"}}


def test_asistente_gratis_con_datos_reales_y_cartera():
    assert chat.valores_en_pregunta("¿Cómo está el RSI de Indra y el oro? ¿Y el bitcoin?") == \
        ["IDR.MC", "GC=F", "BTC-EUR"]
    r = chat.respuesta_gratis("¿Cómo está el RSI de Indra?", "", lambda t: DATOS_INDRA)
    assert "62,68 €" in r and "15/10/2026" in r and "sobrecompra" in r and "comprar (16 analistas)" in r
    assert "nota 87/100" in r and "**RSI**: Indicador" in r
    ctx = "Fecha: x\nSu cartera (peso · ganancia desde la compra):\n- Indra (IDR.MC): 53 % · +3,8 %"
    assert "Indra (IDR.MC): 53 %" in chat.respuesta_gratis("¿Cómo va mi cartera?", ctx, lambda t: None)
    assert "claude.ai" in chat.respuesta_gratis("xyz qwerty", ctx, lambda t: None)


def test_asistente_gratis_sobrevive_a_fallos_de_datos():
    def falla(t):
        raise RuntimeError("sin red")
    r = chat.respuesta_gratis("¿Qué es el PER de Indra?", "", falla)
    assert "**PER**" in r
