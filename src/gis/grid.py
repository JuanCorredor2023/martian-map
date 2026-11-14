"""Genera data/base/grid.json: la ficha de la malla base (contrato del issue #2)."""
import json
import rasterio

d = rasterio.open("base/dem_1m.tif")
o = rasterio.open("base/orto_color_025.tif")
t, to = d.transform, o.transform
grid = {
    "crs_wkt": "data/base/crs.wkt (en el repo: docs/contratos/crs.wkt)",
    "crs_proj4": d.crs.to_proj4(),
    "caja": {"xmin": t.c, "ymin": t.f + t.e * d.height, "xmax": t.c + t.a * d.width, "ymax": t.f},
    "caja_margen_64m": {"xmin": t.c - 64, "ymin": t.f + t.e * d.height - 64, "xmax": t.c + t.a * d.width + 64, "ymax": t.f + 64},
    "malla_1m": {"archivo": "data/base/dem_1m.tif", "celda_m": t.a, "columnas": d.width, "filas": d.height,
                  "origen_x": t.c, "origen_y": t.f, "affine": list(t)[:6]},
    "malla_025m": {"archivo": "data/base/orto_color_025.tif", "celda_m": to.a, "columnas": o.width, "filas": o.height,
                    "affine": list(to)[:6]},
    "dtype": "float32",
    "nodata": "NaN",
    "notas": [
        "Origen = esquina superior izquierda de la celda (0, 0). Fila 0 = norte.",
        "Centro de la celda (fila, col): x = origen_x + (col + 0.5) * celda; y = origen_y - (fila + 0.5) * celda.",
        "Para recortar: gdalwarp -te xmin ymin xmax ymax -tr 1 1 (sin -tap).",
        "Cada celda de 1 m equivale a 4 x 4 celdas de 0.25 m.",
    ],
}
with open("base/grid.json", "w", encoding="utf-8") as f:
    json.dump(grid, f, indent=2, ensure_ascii=False)
print(json.dumps(grid, indent=2, ensure_ascii=False))
