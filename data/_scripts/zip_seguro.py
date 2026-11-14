"""Extracción de zip compartida por clonar_desde_lan.py y descargar_todo.py.

- Comprueba cada ruta sin tocar el disco (nada de `..`, rutas absolutas ni letras de unidad).
- En Windows usa el prefijo de ruta larga, para que no falle con rutas de más de 260 caracteres.
- Omite basura que no hace falta (`.ipynb_checkpoints`, `__MACOSX`).
- Es reanudable: salta lo ya extraído con el tamaño correcto y solo da el zip por terminado
  cuando deja la marca `.extraccion_completa`.
"""
import os, shutil, sys, zipfile

OMITIR = {".ipynb_checkpoints", "__MACOSX"}
MARCA = ".extraccion_completa"


def ruta_larga(p):
    """Ruta absoluta; en Windows, con el prefijo que permite más de 260 caracteres."""
    p = os.path.abspath(p)
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\UNC\\" + p[2:] if p.startswith("\\\\") else "\\\\?\\" + p
    return p


def partes_seguras(nombre):
    """Parte un nombre de archivo del zip (o del índice) en componentes; None si es peligroso."""
    n = nombre.replace("\\", "/")
    partes = [s for s in n.split("/") if s not in ("", ".")]
    if n.startswith("/") or ".." in partes or (partes and ":" in partes[0]):
        return None
    return partes


def extraer(zpath, out):
    """Extrae zpath en out. Devuelve (extraídos, omitidos, fallos), o None si ya estaba completo."""
    if os.path.exists(ruta_larga(os.path.join(out, MARCA))):
        return None
    ok = omitidos = fallos = 0
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            partes = partes_seguras(m.filename)
            if partes is None:
                sys.exit(f"ruta sospechosa en {zpath}: {m.filename}")
            if not partes:
                continue
            if OMITIR & set(partes):
                omitidos += 1
                continue
            dest = ruta_larga(os.path.join(out, *partes))
            try:
                if m.is_dir():
                    os.makedirs(dest, exist_ok=True)
                    continue
                if os.path.exists(dest) and os.path.getsize(dest) == m.file_size:
                    ok += 1
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(m) as src, open(dest + ".tmp", "wb") as f:
                    shutil.copyfileobj(src, f, 1 << 20)
                os.replace(dest + ".tmp", dest)
                ok += 1
            except OSError as e:
                fallos += 1
                print(f"  no se pudo extraer {m.filename}: {e}")
    if not fallos:
        os.makedirs(ruta_larga(out), exist_ok=True)
        open(ruta_larga(os.path.join(out, MARCA)), "w").close()
    return ok, omitidos, fallos
