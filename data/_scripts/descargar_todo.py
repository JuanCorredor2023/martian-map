#!/usr/bin/env python3
"""Deja data/ lista en cualquier máquina bajando los archivos grandes directo del origen.

Uso (desde la raíz del repo, Linux/macOS/Windows, solo Python 3 estándar):
    python3 data/_scripts/descargar_todo.py --perfil terreno        # DEM + ortofoto color (~4,9 GB)
    python3 data/_scripts/descargar_todo.py --perfil terreno dl     # + BoulderNet (y AI4Mars si está en el manifiesto)
    python3 data/_scripts/descargar_todo.py --perfil todo           # incluye lo opcional (ortofoto gris 24 GB, crudos 9,4 GB)
    python3 data/_scripts/descargar_todo.py --perfil todo --solo-verificar

- Lee data/_scripts/manifiesto.json. Lo que ya existe con el tamaño correcto se salta.
- Reanudable: si se corta, se vuelve a ejecutar el mismo comando.
- Los zip marcados con "descomprimir" se extraen en una carpeta extraido/ junto al zip.
Los archivos pequeños (waypoints, clima, índices, papers) NO van aquí: viajan en el kit ligero.
"""
import argparse, hashlib, json, os, subprocess, sys, zipfile

AQUI = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.dirname(AQUI)

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""): h.update(c)
    return h.hexdigest()

def extraer(zpath):
    out = os.path.join(os.path.dirname(zpath), "extraido", os.path.splitext(os.path.basename(zpath))[0])
    if os.path.isdir(out): return
    with zipfile.ZipFile(zpath) as z:
        base = os.path.realpath(out)
        for n in z.namelist():  # no permitir rutas que salgan de la carpeta
            if not os.path.realpath(os.path.join(out, n)).startswith(base): sys.exit(f"ruta sospechosa en {zpath}: {n}")
        z.extractall(out)
    print("  extraído en", os.path.relpath(out, DATA))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", nargs="+", default=["terreno"], help="terreno, dl, opcional o todo")
    ap.add_argument("--conns", type=int, default=8); ap.add_argument("--solo-verificar", action="store_true")
    a = ap.parse_args()
    items = json.load(open(os.path.join(AQUI, "manifiesto.json"), encoding="utf-8"))["archivos"]
    fallos = 0
    for it in items:
        if "todo" not in a.perfil and it["perfil"] not in a.perfil: continue
        dest = os.path.join(DATA, *it["dest"].split("/")); ok = os.path.exists(dest) and os.path.getsize(dest) == it["bytes"]
        print(f"[{it['perfil']}] {it['dest']}  ({it['bytes']/1e9:.2f} GB)  ->", "presente" if ok else "falta")
        if a.solo_verificar:
            if ok and it.get("md5"):
                bien = md5(dest) == it["md5"]; print("  md5", "OK" if bien else "NO COINCIDE"); fallos += not bien
            fallos += not ok; continue
        if not ok:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            cmd = [sys.executable, "-I", os.path.join(AQUI, "bajar.py"), it["url"], dest, "--conns", str(a.conns)]
            if it.get("md5"): cmd += ["--md5", it["md5"]]
            if subprocess.call(cmd) != 0 or not os.path.exists(dest): fallos += 1; continue
        if it.get("descomprimir"): extraer(dest)
    sys.exit(1 if fallos else 0)

main()
