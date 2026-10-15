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


def test_alias_ingles_y_siglas():
    assert aprendizaje.buscar("spread")[0].termino == "Horquilla"
    assert aprendizaje.buscar("drawdown")[0].termino == "Caída máxima"
    assert aprendizaje.buscar("plusvalia")[0].termino == "Ganancia patrimonial"
    nombres = {t.termino for t in aprendizaje.GLOSARIO}
    assert set(aprendizaje.ALIAS) <= nombres


def test_busqueda_por_inicio_de_palabra():
    # «oco» no debe encontrar «poco» ni «coco»: solo el alias OCO.
    assert [t.termino for t in aprendizaje.buscar("OCO")] == ["Stop relacionadas"]


def test_parecidos_corrige_errores_y_busca_en_guias():
    assert aprendizaje.parecidos("dividedno")[0].termino == "Dividendo"
    assert any("renta" in g.titulo for g in aprendizaje.buscar_guias("renta"))
    assert aprendizaje.parecidos("") == [] and aprendizaje.buscar_guias("") == []


def test_palabras_de_cada_pagina_estan_en_el_diccionario():
    import ast
    import pathlib

    nombres = {t.termino for t in aprendizaje.GLOSARIO}
    raiz = pathlib.Path(__file__).resolve().parent.parent
    usados = []
    for archivo in ["app.py", "paginas_hoy.py", "paginas_extra.py", "paginas_virtual.py"]:
        for nodo in ast.walk(ast.parse((raiz / archivo).read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "palabras_de_la_pagina":
                usados += [e.value for e in nodo.args[0].elts]
    assert len(usados) > 40
    assert [u for u in usados if u not in nombres] == []
