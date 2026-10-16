"""Precios y noticias «siempre al día»: se enseña al momento lo último y se renueva en segundo plano."""

import threading
import time

import ui_comun


def test_devuelve_lo_ultimo_al_instante_y_renueva_en_segundo_plano():
    ui_comun.olvidar_datos_al_dia()
    llamadas = []
    listo = threading.Event()

    def descarga():
        llamadas.append(1)
        if len(llamadas) > 1:
            listo.set()
        return len(llamadas)

    assert ui_comun.al_dia(("prueba",), descarga, 0)[0] == 1          # la primera vez se espera a la descarga
    t0 = time.time()
    assert ui_comun.al_dia(("prueba",), descarga, 0)[0] == 1          # caducado: lo de antes, sin esperar...
    assert time.time() - t0 < 0.5
    assert listo.wait(2)                                               # ...y lo nuevo llega por detrás
    time.sleep(0.05)
    assert ui_comun.al_dia(("prueba",), descarga, 3600)[0] == 2
    ui_comun.olvidar_datos_al_dia()


def test_si_la_renovacion_falla_se_queda_el_ultimo_dato_bueno():
    ui_comun.olvidar_datos_al_dia()
    ui_comun.al_dia(("fallo",), lambda: "bueno", 0)

    def rota():
        raise RuntimeError("Yahoo caído")

    ui_comun.al_dia(("fallo",), rota, 0)
    time.sleep(0.1)
    assert ui_comun.al_dia(("fallo",), rota, 3600)[0] == "bueno"
    ui_comun.olvidar_datos_al_dia()
