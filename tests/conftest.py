import os
import tempfile

# Las copias en disco de las pruebas van a una carpeta temporal (ni se mezclan con las de la app ni entre pruebas).
os.environ.setdefault("BOLSA_RESPALDO", tempfile.mkdtemp(prefix="bolsa_pruebas_"))
