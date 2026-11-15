<!-- Owner: Aaron · Sources: E9_boulders.md · Status: drafted from the notes by JB's Claude; owner to confirm -->

### 3.6 Boulders (BoulderNet, distillation and uncertainty)

**Teacher.** BoulderNet, a Mask R-CNN [@He2017] in Detectron2 [@Wu2019] with the authors' weights [@Prieur2023], is run over the 0.25 m grey orthophoto in 500 px windows every 250 px. Each detection is owned by the window whose central block contains its box centre, so no boulder is counted twice. On the authors' Mars patches it reaches precision 0.74 and recall 0.59 (score ≥ 0.5, mask IoU ≥ 0.5). None of its training patches is from Gale. Over the box it finds 8,380 boulders with score ≥ 0.10 (median equivalent diameter 1.7 m, 95th percentile 3.8 m), covering 0.37 % of the box, mostly in debris at the foot of scarps.

**Student.** A 3-level U-Net [@Ronneberger2015] about 50 times smaller is trained by distillation [@Hinton2015] on the teacher's per-pixel score. On held-out blocks its 1 m rock cover correlates with the teacher's at r = 0.66, with mean cover 0.35 % against 0.33 %. It ranks rock well (pixel AUC 0.986), but its boulder-level F1 against human labels is 0.27, against 0.66 for the teacher. The product, `rocas.tif`, is a density of boulders visible from orbit; boulders below about 1 m are not detected.

**Uncertainty (X1).** A Gaussian process on 20 m blocks gives a mean and a standard deviation of rock cover. The standard deviation grows with the mean, and the 90 % interval covers about 80 % in rocky blocks. It is presented as the confidence of the orbital map, not as a guarantee. The optional rock-risk term in the route cost stays off, because no price was validated (E1, Section 3.2).
