from bolsa import aprendizaje, costes


def test_glosario_sin_duplicados_y_categorias_validas():
    nombres = [t.termino for t in aprendizaje.GLOSARIO]
    assert len(nombres) == len(set(nombres))
    assert {t.categoria for t in aprendizaje.GLOSARIO} == set(aprendizaje.CATEGORIAS)
    assert all(t.definicion.strip() for t in aprendizaje.GLOSARIO)


def test_ver_tambien_apunta_a_terminos_existentes():
    nombres = {t.termino for t in aprendizaje.GLOSARIO}
    rotos = [(t.termino, v) for t in aprendizaje.GLOSARIO for v in t.ver if v not in nombres]
    assert rotos == []


def test_buscar_sin_tildes_y_prioriza_nombre():
    r = aprendizaje.buscar("tobin")
    assert r[0].termino == "Tasa Tobin"
    assert aprendizaje.buscar("comision")[0].termino == "Comisión"
    assert all(t.categoria == "Órdenes" for t in aprendizaje.buscar(categoria="Órdenes"))
    assert aprendizaje.buscar("palabra que no existe") == []
    assert "vender" in aprendizaje.definicion("stop-loss")


def test_preguntas_bien_formadas():
    for p in aprendizaje.PREGUNTAS:
        assert 0 <= p.correcta < len(p.opciones) and len(set(p.opciones)) == len(p.opciones)


def test_ejemplo_de_tamano_del_test_coincide_con_la_calculadora():
    assert costes.tamano_por_riesgo(10_000, 1, 50, 45) == 20
    assert costes.tamano_por_riesgo(10_000, 1, 20, 18) == 50
