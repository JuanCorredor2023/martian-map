#!/usr/bin/env python3
"""Copia data/ desde otra máquina de la red local que esté ejecutando servir_lan.py.

Uso:  python3 data/_scripts/clonar_desde_lan.py http://IP:8000 [--solo 01_terreno 03_curiosity] [--excluir 02_imagenes_orbitales/ortofoto_gris_25cm] [--destino RUTA]
- Solo necesita Python 3 (Linux/macOS/Windows). Salta lo que ya está con el tamaño correcto; reanudable.
- Archivos grandes: por segmentos en paralelo (bajar.py). Pequeños: 8 a la vez.
- Los zip que en el origen estaban extraídos se extraen aquí en extraido/<nombre>/.
"""
import argparse, json, os, subprocess, sys, urllib.parse, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
GRANDE = 32 << 20

def url_de(base, ruta): return base.rstrip("/") + "/" + "/".join(urllib.parse.quote(s) for s in ruta.split("/"))

def chico(base, it, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if it["bytes"] == 0: open(dest, "wb").close(); return True
    for _ in range(5):
        try:
            with urllib.request.urlopen(url_de(base, it["ruta"]), timeout=60) as r, open(dest + ".tmp", "wb") as f:
                while True:
                    c = r.read(1 << 18)
                    if not c: break
                    f.write(c)
            if os.path.getsize(dest + ".tmp") == it["bytes"]: os.replace(dest + ".tmp", dest); return True
        except Exception as e: err = e
    print("  FALLO", it["ruta"]); return False

def extraer(zpath):
    out = os.path.join(os.path.dirname(zpath), "extraido", os.path.splitext(os.path.basename(zpath))[0])
    if os.path.isdir(out): return
    with zipfile.ZipFile(zpath) as z:
        base = os.path.realpath(out)
        for n in z.namelist():
            if not os.path.realpath(os.path.join(out, n)).startswith(base): sys.exit(f"ruta sospechosa en {zpath}: {n}")
        z.extractall(out)
    print("  extraído:", out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("base"); ap.add_argument("--solo", nargs="*", default=[])
    ap.add_argument("--excluir", nargs="*", default=[]); ap.add_argument("--destino", default=os.path.dirname(AQUI))
    ap.add_argument("--conns", type=int, default=8); a = ap.parse_args()
    with urllib.request.urlopen(a.base.rstrip("/") + "/_indice.json", timeout=60) as r: items = json.load(r)["archivos"]
    items = [i for i in items if (not a.solo or any(i["ruta"].startswith(p) for p in a.solo)) and not any(i["ruta"].startswith(p) for p in a.excluir)]
    raiz = os.path.realpath(a.destino)
    def dst(i):
        d = os.path.realpath(os.path.join(raiz, *i["ruta"].split("/")))
        if not d.startswith(raiz + os.sep): sys.exit("ruta sospechosa: " + i["ruta"])
        return d
    faltan = [i for i in items if not (os.path.exists(dst(i)) and os.path.getsize(dst(i)) == i["bytes"])]
    print(f"{len(items)} archivos en el origen ({sum(i['bytes'] for i in items)/1e9:.2f} GB); faltan {len(faltan)} ({sum(i['bytes'] for i in faltan)/1e9:.2f} GB)")
    fallos = 0
    with ThreadPoolExecutor(8) as ex:
        fallos += sum(not ok for ok in ex.map(lambda i: chico(a.base, i, dst(i)), [i for i in faltan if i["bytes"] < GRANDE]))
    for i in [i for i in faltan if i["bytes"] >= GRANDE]:
        os.makedirs(os.path.dirname(dst(i)), exist_ok=True); print("grande:", i["ruta"], flush=True)
        if subprocess.call([sys.executable, "-I", os.path.join(AQUI, "bajar.py"), url_de(a.base, i["ruta"]), dst(i), "--conns", str(a.conns)]) != 0: fallos += 1
    for i in items:
        if i.get("extraer") and os.path.exists(dst(i)): extraer(dst(i))
    print("LISTO" if not fallos else f"TERMINÓ CON {fallos} FALLOS (vuelve a ejecutar el mismo comando)"); sys.exit(1 if fallos else 0)

main()
