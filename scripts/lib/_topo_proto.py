"""Structural signature: how many separate ink pieces, counters, stroke ends, crossings,
and which way the ink runs.  Deliberately invariant to stroke weight and curvature."""
import math
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

S8 = np.ones((3, 3), bool)


def _holes(hard):
    lbl, n = ndimage.label(~hard, structure=S8)
    if n == 0:
        return 0
    border = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1])
    border.discard(0)
    return sum(1 for i in range(1, n + 1) if i not in border)


def topo(mask, min_piece=20):
    hard = mask > 0.5
    if not hard.any():
        return {'comps': 0, 'ends': 0, 'juncs': 0, 'holes': 0, 'dir': np.zeros(8), 'len': 0.0}
    lbl, n = ndimage.label(hard, structure=S8)
    sizes = ndimage.sum(hard, lbl, range(1, n + 1))
    comps = int((sizes >= min_piece).sum())          # 4 dots = 4 pieces, 米 = 1
    sk = skeletonize(hard)
    nb = ndimage.convolve(sk.astype(np.int8), np.ones((3, 3), np.int8) - np.eye(3, dtype=np.int8),
                          mode='constant')
    big = np.isin(lbl, [i + 1 for i, s in enumerate(sizes) if s >= min_piece])
    ends = int((sk & (nb == 1) & big).sum())
    juncs = int(ndimage.label(sk & (nb >= 3) & big, structure=S8)[1])
    ys, xs = np.nonzero(sk & big)
    hist = np.zeros(8)
    for y, x in zip(ys, xs):
        # local direction from the two-step neighbourhood of skeleton pixels
        y0, y1 = max(0, y - 2), min(sk.shape[0], y + 3)
        x0, x1 = max(0, x - 2), min(sk.shape[1], x + 3)
        win = sk[y0:y1, x0:x1]
        wy, wx = np.nonzero(win)
        if len(wy) < 2:
            continue
        wy = (wy - wy.mean()).astype(float)
        wx = (wx - wx.mean()).astype(float)
        # principal axis of the local skeleton neighbourhood
        cov = np.cov(np.vstack([wx, wy])) if len(wx) > 2 else None
        if cov is None or not np.isfinite(cov).all():
            continue
        evals, evecs = np.linalg.eigh(cov)
        vx, vy = evecs[:, np.argmax(evals)]
        a = math.atan2(vy, vx) % math.pi
        hist[min(7, int(a / math.pi * 8))] += 1
    if hist.sum():
        hist /= hist.sum()
    return {'comps': comps, 'ends': ends, 'juncs': juncs, 'holes': _holes(hard),
            'dir': hist, 'len': float(len(ys))}


def topo_score(a, b):
    def rel(x, y, span):
        return 1.0 - min(abs(x - y) / max(span, 1.0), 1.0)
    d = float(a['dir'] @ b['dir']) if a['dir'].any() and b['dir'].any() else 0.5
    return (0.34 * rel(a['comps'], b['comps'], 3)
            + 0.24 * rel(a['ends'], b['ends'], 6)
            + 0.18 * rel(a['juncs'], b['juncs'], 4)
            + 0.10 * rel(a['holes'], b['holes'], 2)
            + 0.14 * d)
