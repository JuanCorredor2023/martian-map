"""Features del terreno sobre la malla base (issue #3).
Lee data/base/dem_1m_margen.tif, calcula con 64 m de margen y recorta a la caja exacta."""
import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter, uniform_filter

M = 64  # margen en celdas de 1 m

with rasterio.open("base/dem_1m_margen.tif") as s:
    dem = s.read(1, masked=True).filled(np.nan).astype("float32")
with rasterio.open("base/dem_1m.tif") as r:
    perfil = r.profile.copy()
perfil.update(dtype="float32", nodata=np.nan, count=1, compress="deflate", tiled=True)


def recorta(a):
    return a[M:-M, M:-M]


def guarda(nombre, a, unidades):
    a = recorta(a).astype("float32")
    with rasterio.open(f"base/{nombre}", "w", **perfil) as d:
        d.write(a, 1)
    print(f"{nombre:16s} {unidades:8s} min {np.nanmin(a):9.3f}  max {np.nanmax(a):9.3f}  "
          f"media {np.nanmean(a):9.3f}  NaN {int(np.isnan(a).sum())}  forma {a.shape}")
    return a


def std_local(a, w):
    m = uniform_filter(a, w)
    return np.sqrt(np.clip(uniform_filter(a * a, w) - m * m, 0, None))


# 1. Pendiente de gdaldem (Horn), con nodata a NaN
with rasterio.open("base/slope_margen.tif") as s:
    slope = s.read(1, masked=True).filled(np.nan).astype("float32")
slope = guarda("slope_deg.tif", slope, "grados")

# Control con NumPy (diferencias centrales; deben parecerse, no ser idénticas)
gy, gx = np.gradient(dem, 1.0, 1.0)
slope_np = recorta(np.degrees(np.arctan(np.hypot(gx, gy))))
print(f"  control pendiente: diferencia mediana gdaldem vs numpy = {np.nanmedian(np.abs(slope - slope_np)):.2f} grados")
print(f"  celdas con pendiente > 15 grados: {100 * np.nanmean(slope > 15):.1f} %")

# 2. Residuo (detalle fino): DEM menos su versión suavizada
resid = dem - gaussian_filter(dem, sigma=5)
guarda("resid.tif", resid, "m")

# 3. Rugosidad: desviación estándar local del residuo, ventana 7
guarda("rough.tif", std_local(resid, 7), "m")

# 4. TPI: DEM menos su media local, ventana 15
guarda("tpi.tif", dem - uniform_filter(dem, 15), "m")

# 5. Sombreado recortado (uint8, para ver)
with rasterio.open("base/hillshade_margen.tif") as s:
    hs = s.read(1)
p8 = perfil.copy(); p8.update(dtype="uint8", nodata=0)
with rasterio.open("base/hillshade.tif", "w", **p8) as d:
    d.write(recorta(hs), 1)
print("hillshade.tif    listo")
