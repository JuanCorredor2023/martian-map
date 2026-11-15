# E9 · Boulders: BoulderNet as teacher, distilled to a light CNN (`rocas.tif`)

Owner: Aaron (`@aahg1105`) · Issue: #12 · PRs: (this PR) · Status: done (first version) · Last update: 2026-11-15

## Question
Where are the boulders in the 2 × 2 km study box, and can a CNN about 50 times smaller than a published boulder detector reproduce its map well enough to serve as a terrain layer (`rocas.tif`, fraction of each 1 m cell covered by boulders) for route costs and the HUD?

## Data
- **Image:** the 0.25 m greyscale HiRISE orthophoto of Gale [HiRISE-Gale], cropped to the study box by the base grid (`ortho_gray_025.tif` in release `base-grid-v2`, 8000 × 8000 px, uint8, 0 = nodata). Detail from 2006–2011 HiRISE images, before landing.
- **Teacher:** BoulderNet [Prieur2023], a Mask R-CNN with a ResNet-50 + FPN backbone [He2017] in Detectron2 [Wu2019], weights `model_0055999.pth` (the authors' recommended checkpoint) and `config.yaml` from Zenodo record 8171052 (CC-BY-4.0, md5 checked; `data/06_bouldernet/`). It was trained on 953 patches of 500 × 500 px from the Moon, Earth and Mars; only 49 are from Mars (HiRISE) and none is from Gale (`docs/enfoques.md`, correction 5).
- **Labels used for the check:** the authors' hand labels on those 49 Mars patches (39 train, 6 validation, 4 test), in the dataset JSON of the same record.
- Nothing was filtered from the image. Detections are kept from score 0.10 (the authors' inference value) and carried with their score, so the student sees the teacher's confidence.

## Method
1. **Teacher check** (`src/dl_rocas/teacher.py check`). The model is loaded with the authors' config. The loader compares every stored weight with the model and stops if one is missing or left over (it matched exactly). On each Mars patch, predictions with score ≥ 0.5 are matched one-to-one to the hand labels at mask IoU ≥ 0.5 (greedy in score order), giving precision and recall per split.
2. **Teacher over the box** (`teacher.py run`). The authors' inference settings: input resized to 1024 px, ROI score threshold 0.10, NMS 0.30, up to 2000 detections per image. Windows of 500 px (the training patch size) every 250 px. Each window keeps only the detections whose box centre lies in its own block. The blocks split each overlap in the middle and partition the image (checked in `tests/dl_rocas/test_e9.py`), so no boulder is counted twice or cut by a window edge: a kept boulder is ≥ 125 px (31 m) from the inner edges of its window. A final box NMS (0.30) removes rare duplicates at block borders. Each mask becomes a polygon in the DEM's CRS, with score, area and equivalent diameter 2√(A/π). We did not use the authors' graticule stitching from `MLtools.inference` because this ownership rule does the same job in a few lines on a single raster.
3. **Soft target** (`distill.py targets`). Knowledge distillation [Hinton2015]: each 0.25 m pixel takes the score of the teacher mask that covers it (the highest if several), 0 elsewhere. The student learns the teacher's confidence, not a 0/1 mask.
4. **Student** (`distill.py train`). A 3-level U-Net [Ronneberger2015] with widths 32/64/128, batch norm and one input channel: 0.93 M parameters, receptive field about 10 m. Loss is binary cross-entropy on logits against the soft target, with no positive weight. With soft targets the optimum of this loss is the teacher's expected value, so the student's mean cover stays calibrated; a positive weight would inflate it.
   - AdamW, one-cycle learning rate up to 3·10⁻³, 30 epochs × 100 steps × 16 random 256 × 256 crops, rotations by 90° and flips, seed 9.
   - **Spatial split:** the box is cut into 8 × 8 blocks of 250 m, and 13 of the 64 blocks (a fixed diagonal pattern, every 5th; ~20 %) are validation. Crops never straddle blocks. The checkpoint with the lowest validation loss is kept.
5. **`rocas.tif`** (`distill.py predict`). The student runs on the whole orthophoto in 1024 px tiles; a 32 px overlap is discarded so there are no seams. The per-pixel probability is averaged over each 4 × 4 px block, giving the fraction of each 1 m cell covered by boulders. It is written as float32 on the base grid, with NaN where any pixel of the cell is nodata.
6. **Tried and dropped:** a narrower student (widths 16/32/64, 0.23 M parameters, 20 epochs). It ran in 4.4 s, but it agreed less with the teacher on validation (r = 0.56 per 1 m cell, 0.60 at 10 m) and overestimated the mean cover (0.42 % against 0.33 %); outputs in `data/e9/w16/`.
7. **Longer training, kept aside:** the same student and settings trained for 60 epochs instead of 30 (`--epochs 60`, everything else equal, `pos_weight` 1). It is better at finding boulders and worse as a density map (Results). `rocas.tif` stays with the 30-epoch student; the 60-epoch one is in `data/e9/w32_e60/`.

## Results
Sources: `data/e9/summary.json` (written by `src/dl_rocas/paper_figures.py`), `data/e9/teacher_check_mars.json`, `data/e9/boulders_teacher.json`, `data/e9/student_metrics.json`, `data/e9/rocas.json`.

**Teacher against the authors' Mars labels** (score ≥ 0.5, mask IoU ≥ 0.5):

| Split | Patches | Boulders | Precision | Recall |
|---|---:|---:|---:|---:|
| train | 39 | 5536 | 0.75 | 0.58 |
| validation | 6 | 904 | 0.73 | 0.57 |
| test | 4 | 386 | 0.65 | 0.68 |
| all | 49 | 6826 | 0.74 | 0.59 |

**Teacher over the box:**
- 961 windows in 362 s on an NVIDIA T1000 (4 GB).
- 8380 boulders with score ≥ 0.10, and 2525 with score ≥ 0.5 (631 per km²).
- Equivalent diameter: median 1.7 m, 95th percentile 3.8 m.
- Boulders cover 0.37 % of the box in score-weighted area (mean of `data/e9/teacher_cover_1m.tif`). They concentrate in debris at the foot of scarps and along some ridges (Figure 1).

**Student against teacher** (rock cover, validation blocks only, never seen in training):

| | Per 1 m cell | 10 m windows |
|---|---:|---:|
| Pearson r | 0.66 | 0.66 |
| Mean absolute error (cover fraction) | 0.0040 | 0.0030 |
| Mean cover, teacher / student | 0.33 % / 0.35 % | |

On the training blocks the values are similar (r = 0.68 per cell, 0.74 at 10 m), so the student is limited by capacity rather than overfitting.

**Student as a classifier** (`src/dl_rocas/evaluate_student.py` → `data/e9/student_classification.json`). Positive = teacher score ≥ 0.5; student threshold 0.25 (best pixel F1); student boulders are connected regions ≥ 4 px; objects are matched one-to-one at mask IoU ≥ 0.5.

| Level | Reference | ROC-AUC | AP (random) | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|
| Pixel, validation blocks | teacher | 0.986 | 0.47 (0.003) | 0.49 | 0.47 | 0.48 |
| 1 m cell (cover ≥ 0.25), validation blocks | teacher | 0.987 | 0.52 (0.005) | | | |
| Boulder, validation blocks | teacher | | | 0.26 | 0.46 | 0.33 |
| Boulder, 49 Mars patches | human labels | | | 0.24 | 0.31 | 0.27 |
| Boulder, 49 Mars patches (teacher, score ≥ 0.5) | human labels | | | 0.74 | 0.59 | 0.66 |

- **Ranking versus finding:** the student ranks rock against ground very well (AUC 0.99), but boulders are rare (0.3 % of pixels), so AUC flatters it. Average precision (0.47–0.52, against 0.003–0.005 for chance) and F1 are the honest measures.
- **Mars patches:** on the authors' patches, never seen by the student, it finds 31 % of the hand-labelled boulders, against 59 % for the teacher. The validation + test patches alone give F1 0.28 for the student and 0.65 for the teacher.
- **What it is good for:** the student is a usable **density** map, not a boulder detector. Use `boulders_teacher.gpkg` when individual boulders matter.

**More epochs: better detection, worse calibration.** Same student (0.93 M parameters) and settings, 30 against 60 epochs. Sources: `data/e9/w32/` and `data/e9/w32_e60/` (`student_metrics.json` from `distill.py train`, `student_classification.json` from `evaluate_student.py`). All on validation blocks or on the authors' Mars patches.

| | 30 epochs (`rocas.tif`) | 60 epochs |
|---|---:|---:|
| Best validation loss (soft BCE) | 0.0095 | 0.0088 |
| Boulder F1 vs human labels (49 Mars patches) | 0.27 (P 0.24, R 0.31) | **0.41** (P 0.37, R 0.47) |
| Boulder F1 vs teacher | 0.33 (P 0.26, R 0.46) | **0.37** (P 0.27, R 0.55) |
| Pixel AP vs teacher (ROC-AUC) | **0.47** (0.986) | 0.45 (0.986) |
| Cover r vs teacher, 1 m / 10 m | **0.66 / 0.66** | 0.65 / 0.64 |
| Cover MAE per 1 m cell | 0.0040 | **0.0034** |
| Mean cover (teacher 0.33 %) | **0.35 %** | 0.24 % |
| Whole box | 8.6 s | 8.7 s |

- **Why detection improves:**
  - With more steps at a falling learning rate, the student draws tighter, better separated blobs. On the validation blocks it splits the same ground into 792 boulder regions against 704 at 30 epochs (393 teacher boulders): neighbouring boulders that were merged come out as separate ones.
  - Recall and precision of single boulders both rise, so F1 against human labels goes from 0.27 to 0.41. It is still well below the teacher's 0.66.
- **Why calibration gets worse:**
  - The tighter blobs drop the doubtful pixels at boulder edges and in clusters. Some of those are boulder in the teacher's soft target.
  - The mean cover falls from 0.35 % to 0.24 %, about 27 % below the teacher's 0.33 %. The per-cell error is smaller (MAE 0.0034), because the many empty cells get closer to 0. But the rocky cells are underestimated: pixel AP and cover correlation drop slightly.
- **Choice:** `rocas.tif` is used as a density (HUD layer, possible cost factor), where a calibrated mean matters more than separating boulders. It therefore keeps the 30-epoch student.
  - If single boulders are needed, the teacher's polygons remain the better source.
  - The trade-off itself is a result: in this distillation, training longer moves the student from a density estimator towards a detector.

**Cost:** 0.93 M parameters against 43.9 M (47 times fewer). The whole box takes 8.6 s against 362 s for the teacher (42 times faster).

**Effect on the plan** (`src/dl_rocas/route_effect.py` → `data/e9/route_effect.json`).
- **Set-up:**
  - E4's graph, with the habitat at the box centre.
  - 28 goals: the 13 manual stations and the 15 E8 contacts.
  - Minimum-cost round trips with arc energy E3 × (1 + k · cover of the arrival cell).
  - k has no source; it is a sensitivity sweep, and k = 0 is the E4 route.

| k | Route cells with cover ≥ 0.25 | Goals whose route crosses one | Boulder area stepped on (m², sum of cover) | E3 energy vs k = 0, median / max | Length vs k = 0, max |
|---|---:|---:|---:|---:|---:|
| 0 (E4) | 15 | 3 | 45.2 | 0 / 0 | 0 m |
| 1 | 5 | 1 | 30.9 | +0.00 % / +0.12 % | +1 m |
| 3 | 5 | 1 | 24.9 | +0.01 % / +0.53 % | +8 m |
| 10 | 3 | 1 | 21.1 | +0.06 % / +1.22 % | +16 m |

- **Cheap to avoid:** the E4 routes already cross few boulders, and pricing them removes most of the rest for almost no energy. With k = 10, the boulder area along the 28 round trips halves (45 → 21 m²) for a median energy change of +0.06 % and at most +16 m of walking.
- **Low cost for planning:** boulders are a hazard that costs very little to avoid in this box. Pricing them changes local detours, not which stations fit the budget.
- **Unknown weight:** the right k is unknown, which is why `rocas.tif` is offered as a layer and not wired into the cost.

![Figure 1](../figures/e9_fig1_teacher.png)
*Figure 1. (a) BoulderNet detections on a 125 m zoom at the north-west corner (scarp with debris). (b) Teacher rock cover over the box, 10 m windows; the cyan square is the zoom. `src/dl_rocas/paper_figures.py`.*

![Figure 2](../figures/e9_fig2_student.png)
*Figure 2. Rock cover at 10 m from (a) the teacher and (b) the student (`rocas.tif`); cyan squares are the validation blocks. (c) Student against teacher on validation blocks only. White cells in (a) and (b) are orthophoto nodata. `src/dl_rocas/paper_figures.py`.*

## Checks
- **Weights:** every stored weight matches the model (the loader stops otherwise).
- **Teacher against labels:**
  - Precision and recall on the Mars validation and test patches are close to the training ones.
  - The teacher is not memorising Mars.
  - It misses about 4 in 10 labelled boulders at mask IoU 0.5; we did not break the misses down by size.
- **Visual review:** on the zoom, detections sit on blocks of debris and on isolated boulders. The fine texture of the ground is not marked (Figure 1a).
- **Tiling:** the kept blocks partition the image for sizes that are and are not multiples of the stride (`tests/dl_rocas/test_e9.py`). This test found and fixed a gap for the second case, which does not occur in this 8000 px box.
- **Calibration:** the student's mean cover (0.35 %) matches the teacher's (0.33 %) on validation.
- **Independence:** validation blocks are spread over the whole box (every block row and column has one; test).

## Limitations
- **Detection floor:** boulders below about 1 m (4 px at 0.25 m) are not detected; 95 % of the detections are ≥ 1.26 m. `rocas.tif` is a density of the boulders that can be seen from orbit, not a guarantee that a cell is free of rock.
- **Domain:** the teacher saw 49 Mars patches and none from Gale. Its precision and recall here are unknown (no labels in the box). The numbers in the check table are for the authors' Mars patches only.
- **Distillation is relative:** the student is scored mainly against the teacher; its errors add to the teacher's. Against human labels on Mars it reaches boulder F1 0.27, against 0.66 for the teacher (Results).
  - It agrees moderately (r = 0.66). It spreads cover into a halo around clusters and marks some linear ridge edges where the teacher found nothing (Figure 2b).
  - Longer training improves boulder detection but costs calibration (60 against 30 epochs, Results). A larger student or more pseudo-labels from outside the box, where the teacher can run, are the untested options.
- **Age of the image:** detail from 2006–2011 imagery; boulders that moved since then are not represented.
- **Unequal timing:** the teacher's time includes polygonising the masks and covers every pixel about four times (50 % overlap). The student's time is inference on the GPU only. The speed-up compares the two pipelines as used, not the two networks on equal input.
- **No route cost yet:** `rocas.tif` is not in any route cost. How much a given cover should slow or block a walker has no source here.

## What other pieces can use
- **`data/e9/rocas.tif`** (Juan, Sebas): float32 on the base grid, 1 m, NaN nodata. Values are the fraction of the cell covered by boulders (0–1; median 0.0004, 99th percentile 0.087).
  - As a HUD layer, it reads best at 10 m (Figure 2b).
  - As a cost, it could multiply E3's energy like the E1 sand factor in `api/planner.graph(human=True)`. Its weight is a modelling choice to be stated, not a measured number.
- **`data/e9/boulders_teacher.gpkg`** (layer `boulders`): one polygon per boulder with `score`, `area_m2` and `diameter_m`. Filter by `score` (0.5 is a reasonable default).
- **E11 (JB):** with the suit radio at 1.7 m, the largest boulders (≥ 3.8 m for the top 5 %) can block line of sight at short range, and the DEM does not see them.
- **E12 / results table (Juan):** the numbers in Results come from `data/e9/summary.json`.

## Reproduce
Detectron2 needs its own conda env (it does not install in the API env); exact versions in `src/dl_rocas/requirements_bouldernet.txt`:
```
conda create -n bouldernet python=3.11 -y
<env>/python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
# Detectron2 from source (commit 247691a), CPU ops built with MSVC 2022; Mask R-CNN runs on the GPU through torchvision's ops
git clone https://github.com/facebookresearch/detectron2 && cd detectron2
(vcvars64.bat; set DISTUTILS_USE_SDK=1; set FORCE_CUDA=0) <env>/python -m pip install --no-build-isolation .
<env>/python -m pip install rasterio geopandas shapely opencv-python-headless scikit-image pandas
```
Inputs: `gh release download base-grid-v2` into `data/base/`, and `data/06_bouldernet/` (`python data/_scripts/clonar_desde_lan.py <host> --solo 06_bouldernet`). Then, from the repo root:
```
<env>/python src/dl_rocas/teacher.py check     # 1 min
<env>/python src/dl_rocas/teacher.py run       # 6 min on a T1000
<env>/python src/dl_rocas/distill.py targets
<env>/python src/dl_rocas/distill.py train     # 45 min on a T1000
<env>/python src/dl_rocas/distill.py predict   # 9 s
<env>/python src/dl_rocas/evaluate_student.py  # classification metrics, 2 min
python src/dl_rocas/route_effect.py            # effect on E4 round trips, any env with scipy + geopandas
# 60-epoch comparison (overwrites data/e9/student.pt; keep the 30-epoch one aside first)
<env>/python src/dl_rocas/distill.py train --epochs 60     # 90 min on a T1000
<env>/python src/dl_rocas/distill.py predict --out data/e9/w32_e60/rocas.tif
<env>/python src/dl_rocas/evaluate_student.py --student data/e9/student.pt --out data/e9/w32_e60/student_classification.json
python src/dl_rocas/paper_figures.py           # any env with rasterio, geopandas, matplotlib, torch
```
If GDAL plugin errors show up, the API env's `GDAL_DRIVER_PATH` is leaking into the `bouldernet` env; unset it.

## Outputs
In `data/e9/` (not in git):
- `boulders_teacher.gpkg` and `.json`
- `teacher_check_mars.json`
- `teacher_soft_025.tif`
- `teacher_cover_1m.tif`
- `student.pt`
- `student_metrics.json`, `student_classification.json`
- `route_effect.json`
- **`rocas.tif`** and `rocas.json`
- `summary.json`
- `w16/`: the dropped student
- `w32/`: the delivered student (copy of the files above)
- `w32_e60/`: the 60-epoch student, kept aside

Figures: `paper/figures/e9_fig1_teacher.png`, `paper/figures/e9_fig2_student.png`.
