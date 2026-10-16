from bolsa import conclusiones, noticias

FILAS = {"BBVA.MC": {"ticker": "BBVA.MC", "nota": 71, "riesgo_nivel": "normal", "puntuacion": 60, "color": "orange",
                     "veredicto": "Neutral", "momentum": 0.1, "mercado_alcista": True, "resultados_pronto": False}}
MIAS = {"SAN.MC", "IDR.MC", "REP.MC"}


def concluir(titulo):
    n = noticias.analizar(noticias.Noticia(titulo, "", "x", None))
    return conclusiones.concluir(titulo, "", noticias.detectar_empresas(titulo.lower()), n.sentimiento, FILAS, MIAS)


def test_resultados_proximos_y_publicados():
    c = concluir("BBVA presentará sus resultados el jueves")
    assert c["tipo"] == "vigilar" and c["donde"].startswith("BBVA") and "Evita comprar justo antes" in c["oportunidad"]
    assert "Hoy la app ve BBVA así" in c["oportunidad"] and "nota 71/100" in c["oportunidad"]
    c = concluir("BBVA se hunde tras unos resultados que decepcionan")
    assert "flojos" in c["efecto"] and c["tipo"] == "oportunidad"


def test_tipos_y_conflictos_dicen_quien_gana_y_quien_pierde():
    sube = concluir("El BCE sube los tipos de interés")
    assert "📈" in sube["donde"] and "banca" in sube["donde"].split("📈")[1]
    assert sube["te_afecta"] == "Te afecta: a favor de Banco Santander."
    baja = concluir("El BCE recorta los tipos de interés")
    assert baja["tipo"] == "oportunidad" and "en contra para Banco Santander" in baja["te_afecta"]
    petroleo = concluir("El petróleo se dispara un 6% por el conflicto en Oriente Medio")
    assert "aerolíneas" in petroleo["efecto"] and "a favor de Repsol" in petroleo["te_afecta"]
    assert "Indra" in concluir("Estalla un conflicto armado en Oriente Medio")["te_afecta"]


def test_noticias_condicionales_no_toman_partido():
    c = concluir("El IPC de EEUU sale hoy y el mercado contiene la respiración")
    assert c["tipo"] == "vigilar" and "a favor" not in c["te_afecta"] and "según cómo salga" in c["te_afecta"]


def test_opa_empresa_propia_y_sin_conclusion():
    c = concluir("Indra lanza una OPA sobre Escribano")
    assert "Te afecta: tienes Indra." == c["te_afecta"]
    assert concluir("Apple presenta un nuevo iPhone") is None
    assert "Riesgo" in conclusiones.resumen_corto(concluir("Trump anuncia nuevos aranceles a los coches europeos"))


def test_frescura_de_las_noticias():
    from datetime import datetime, timedelta, timezone

    from bolsa import noticias

    ahora = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc)
    lista = [noticias.Noticia("a", "x", "Expansión", ahora - timedelta(minutes=3)),
             noticias.Noticia("b", "x", "CNBC", ahora - timedelta(minutes=45)),
             noticias.Noticia("c", "x", "Expansión", ahora - timedelta(minutes=30)),
             noticias.Noticia("d", "x", "Finnhub · Reuters", ahora - timedelta(minutes=1))]
    f = noticias.frescura(lista, ahora)
    assert round(f["minutos"]) == 1
    assert list(f["por_fuente"]) == ["Finnhub", "Expansión", "CNBC"] and round(f["por_fuente"]["Expansión"]) == 3
