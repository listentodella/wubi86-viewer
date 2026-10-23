"""Kai-styled 字根 font helpers.

The 黑体字根.ttf distributed in `data-src/` draws every 五笔 root in a PUA slot
(E000..E855) plus nine Unicode slots (9FB0..9FBB).  It is the layout of record
for the site, but no Kai (楷体) counterpart exists, and its licence is unknown.

This module rebuilds that layout with LXGW WenKai (SIL OFL 1.1) outlines:

* every codepoint of 黑体字根.ttf is kept, together with its advance width, so the
  result is a drop-in replacement;
* outlines come from the WenKai glyph of the matching character, scaled from
  WenKai's 1000 units/em to 2048 and centred on the Hei root's bounding box;
* the 15 识别码 glyphs (frame + 末笔 marks) are composed from WenKai parts;
* the PUA -> character mapping is derived from the site data (authoritative
  anchors), hand-written root names, and outline matching validated against the
  known anchors.
"""

import json
import math
from pathlib import Path

import numpy as np
from scipy import ndimage
from fontTools.misc.transform import Transform
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph

KAI_UPEM = 1000          # LXGW WenKai units per em
MATCH_SIZE = 128         # bitmap size used by the outline matcher
SCALE_CLIP = (0.75, 1.7)  # clamp on the ink-area scale of every placed glyph
SS = 3                   # supersampling factor for rasterisation

# ---------------------------------------------------------------- geometry --


class FlattenPen(BasePen):
    """Collect flattened contours (font units, y-up) for rasterising."""

    def __init__(self, glyphSet, steps=8):
        super().__init__(glyphSet)
        self.contours = []
        self._cur = None
        self.steps = steps

    def _flush(self):
        if self._cur and len(self._cur) > 2:
            self.contours.append(np.array(self._cur, dtype=np.float64))
        self._cur = None

    def _moveTo(self, pt):
        self._flush()
        self._cur = [pt]

    def _lineTo(self, pt):
        self._cur.append(pt)

    def _qCurveToOne(self, p1, p2):
        p0 = self._cur[-1]
        t = np.linspace(0, 1, self.steps + 1)[1:]
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        self._cur.extend(zip(x.tolist(), y.tolist()))

    def _curveToOne(self, p1, p2, p3):
        p0 = self._cur[-1]
        t = np.linspace(0, 1, self.steps + 1)[1:]
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1]
        self._cur.extend(zip(x.tolist(), y.tolist()))

    def _closePath(self):
        self._flush()


def flatten(font, gname, steps=8):
    pen = FlattenPen(font.getGlyphSet(), steps=steps)
    font.getGlyphSet()[gname].draw(pen)
    pen._flush()
    return pen.contours


def rasterize(contours, size=MATCH_SIZE, ss=SS, fill=0.92):
    """Bitmap of `contours`, bbox-centred and aspect-preserving, filled with the
    nonzero winding rule (TrueType convention), so overlapping strokes union and
    counters stay open."""
    mask = np.zeros((size, size), dtype=np.float32)
    if not contours:
        return mask
    pts = np.concatenate(contours)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = max((hi - lo).max(), 1e-6)
    scale = size * fill / span
    cx, cy = (lo + hi) / 2.0
    n = size * ss
    cuts = np.zeros((n, n + 2), dtype=np.int32)
    for c in contours:
        p = (c - (cx, cy)) * scale
        x = p[:, 0] + n / 2.0
        y = n / 2.0 - p[:, 1]
        xn, yn = np.roll(x, -1), np.roll(y, -1)
        for i in range(len(x)):
            x0, y0, x1, y1 = x[i], y[i], xn[i], yn[i]
            if y0 == y1:
                continue
            sign = 1 if y1 > y0 else -1
            rows = np.arange(int(math.ceil(min(y0, y1) - 0.5)),
                             int(math.floor(max(y0, y1) - 0.5)) + 1)
            rows = rows[(rows >= 0) & (rows < n)]
            if rows.size == 0:
                continue
            xs = x0 + (rows + 0.5 - y0) * (x1 - x0) / (y1 - y0)
            cols = np.clip(np.floor(xs).astype(np.int64), 0, n)
            np.add.at(cuts, (rows, cols), sign)
    wind = np.cumsum(cuts[:, :n], axis=1)
    bits = (wind != 0).astype(np.float32)
    return bits.reshape(size, ss, size, ss).mean(axis=(1, 3))


def _blur(img, sigma=3.0):
    rad = max(1, int(round(sigma * 3)))
    k = np.exp(-(np.arange(-rad, rad + 1) ** 2) / (2 * sigma ** 2))
    k /= k.sum()
    out = np.apply_along_axis(lambda m: np.convolve(m, k, 'same'), 0, img.astype(np.float64))
    out = np.apply_along_axis(lambda m: np.convolve(m, k, 'same'), 1, out)
    return out.astype(np.float32)


class Shape:
    """Style-tolerant fingerprint of one glyph: coarse ink distribution (blurred),
    chamfer distance field, counter count and aspect ratio."""

    __slots__ = ('soft', 'hard', 'dt', 'holes', 'aspect', 'blur')

    def __init__(self, mask):
        self.soft = mask
        self.hard = mask > 0.5
        self.dt = ndimage.distance_transform_edt(~self.hard)
        lbl, n = ndimage.label(~self.hard, structure=np.ones((3, 3), bool))
        border = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1])
        self.holes = sum(1 for i in range(1, n + 1) if i not in border)
        ys, xs = np.nonzero(self.hard)
        self.aspect = ((xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1)) if len(ys) else 1.0
        b = _blur(mask).ravel()
        v = b - b.mean()
        norm = np.linalg.norm(v)
        self.blur = v / norm if norm > 1e-6 else np.zeros_like(v)


def shape_distance(a, b, size=MATCH_SIZE):
    """1.0 = identical structure; lower is worse."""
    if not a.hard.any() or not b.hard.any():
        return 0.0
    if not (np.isfinite(a.blur).all() and np.isfinite(b.blur).all()):
        return 0.0
    chamfer = 1 - (a.dt[b.hard].mean() + b.dt[a.hard].mean()) / 2 / (size * 1.4)
    bonus = -0.06 * abs(a.holes - b.holes) - 0.10 * abs(math.log((a.aspect + 1e-3) / (b.aspect + 1e-3)))
    # Element-wise reduction avoids platform BLAS warnings on these small float32 vectors.
    similarity = float(np.sum(a.blur.astype(np.float64) * b.blur.astype(np.float64)))
    return 0.55 * similarity + 0.45 * chamfer + bonus


# ------------------------------------------------------------- font loader --


class Fonts:
    def __init__(self, hei_path, kai_path):
        self.hei_path = str(hei_path)
        self.hei = TTFont(hei_path, lazy=False)
        self.kai = TTFont(kai_path, lazy=False)
        self.hcmap = self.hei.getBestCmap()
        self.kcmap = self.kai.getBestCmap()
        self.kai_scale = self.hei['head'].unitsPerEm / self.kai['head'].unitsPerEm
        self.hei_glyf = self.hei['glyf']          # kept: build replaces hei['glyf']
        self._hshape = {}
        self._kshape = {}
        self._hink = {}
        self._kink = {}
        self._hstruct = {}
        self._kstruct = {}

    def hei_struct(self, gname):
        if gname not in self._hstruct:
            self._hstruct[gname] = struct_sig(flatten(self.hei, gname, steps=4))
        return self._hstruct[gname]

    def kai_struct(self, ch):
        if ch not in self._kstruct:
            self._kstruct[ch] = struct_sig(flatten(self.kai, self.kcmap[ord(ch)], steps=4))
        return self._kstruct[ch]

    def hei_ink(self, gname):
        """Filled area of a Hei glyph in font units (optical weight)."""
        if gname not in self._hink:
            pen = AreaPen(self.hei.getGlyphSet())
            self.hei.getGlyphSet()[gname].draw(pen)
            self._hink[gname] = abs(pen.value)
        return self._hink[gname]

    def kai_ink(self, ch):
        if ch not in self._kink:
            pen = AreaPen(self.kai.getGlyphSet())
            self.kai.getGlyphSet()[self.kcmap[ord(ch)]].draw(pen)
            self._kink[ch] = abs(pen.value)
        return self._kink[ch]

    def has_kai(self, ch):
        return ord(ch) in self.kcmap

    def hei_shape(self, gname):
        if gname not in self._hshape:
            self._hshape[gname] = Shape(rasterize(flatten(self.hei, gname)))
        return self._hshape[gname]

    def kai_shape(self, ch):
        if ch not in self._kshape:
            self._kshape[ch] = Shape(rasterize(flatten(self.kai, self.kcmap[ord(ch)])))
        return self._kshape[ch]

    def hei_bbox(self, gname):
        g = self.hei_glyf[gname]
        if g.numberOfContours == 0:
            return None
        return (g.xMin, g.yMin, g.xMax, g.yMax)

    def kai_bbox(self, ch):
        g = self.kai['glyf'][self.kcmap[ord(ch)]]
        if g.numberOfContours == 0:
            return None
        return (g.xMin, g.yMin, g.xMax, g.yMax)

    # ---- outline transfer -------------------------------------------------
    def segments(self, ch, transform):
        """Decomposed path of `ch`, curves kept, `transform` applied."""
        gname = self.kcmap[ord(ch)]
        rec = DecomposingRecordingPen(self.kai.getGlyphSet())
        self.kai.getGlyphSet()[gname].draw(TransformPen(rec, transform))
        return rec.value

    def placed_segments(self, ch, hei_gname, extra_scale=1.0):
        """`ch` drawn at the Hei root's position and optical size."""
        hb, kb = self.hei_bbox(hei_gname), self.kai_bbox(ch)
        if hb is None or kb is None:
            return []
        # match the Hei root's *ink* (optical weight), not its bounding box: a
        # four-dot root and a full 米 have similar bboxes but wildly different ink
        h_ink = max(self.hei_ink(hei_gname), 1.0)
        k_ink = max(self.kai_ink(ch), 1.0)
        ratio = math.sqrt(h_ink / (k_ink * self.kai_scale ** 2))
        s = self.kai_scale * extra_scale * min(max(ratio, SCALE_CLIP[0]), SCALE_CLIP[1])
        dx = (hb[0] + hb[2]) / 2 - ((kb[0] + kb[2]) / 2) * s
        dy = (hb[1] + hb[3]) / 2 - ((kb[1] + kb[3]) / 2) * s
        return self.segments(ch, Transform(s, 0, 0, s, dx, dy))

    def box_segments(self, ch, box, fill=0.96, stretch=False):
        """`ch` uniformly scaled to sit centred inside `box` (output units)."""
        kb = self.kai_bbox(ch)
        if kb is None or box is None:
            return []
        bw, bh = box[2] - box[0], box[3] - box[1]
        kw, kh = kb[2] - kb[0], kb[3] - kb[1]
        if kw <= 0 or kh <= 0:
            return []
        if stretch:
            # 非等比：横竖各自铺满（用于「口」这种书上是宽扁形的部件）
            sx, sy = bw / kw * fill, bh / kh * fill
        else:
            sx = sy = min(bw / kw, bh / kh) * fill
        dx = (box[0] + box[2]) / 2 - ((kb[0] + kb[2]) / 2) * sx
        dy = (box[1] + box[3]) / 2 - ((kb[1] + kb[3]) / 2) * sy
        return self.segments(ch, Transform(sx, 0, 0, sy, dx, dy))


def seg_ink(segments):
    """Filled area of a recorded outline, in output units."""
    glyph = to_glyph(segments)
    glyf = newTable('glyf')
    glyf.glyphOrder = ['g']
    glyf.glyphs = {'g': glyph}
    pen = AreaPen(glyf)
    glyph.draw(pen, glyf)
    return abs(pen.value)


def scale_segments(segments, k, center):
    """Scale recorded segments about `center`."""
    out = []
    for op, args in segments:
        pts = []
        for a in args:
            if isinstance(a, tuple) and len(a) == 2:
                pts.append((center[0] + (a[0] - center[0]) * k, center[1] + (a[1] - center[1]) * k))
            else:
                pts.append(a)
        out.append((op, tuple(pts)))
    return out


def seg_bounds(segments):
    xs = [p[0] for _, args in segments for p in args if isinstance(p, tuple) and len(p) == 2]
    ys = [p[1] for _, args in segments for p in args if isinstance(p, tuple) and len(p) == 2]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def compose_from_boxes(fonts, hei_gname, ch, fill=0.96):
    """Draw `ch` once per contour box of the Hei glyph.

    For roots that are *not* a character but a small constellation of strokes —
    the four dots of 灬 in 鬯/鹵/滷, for instance — this keeps the original
    layout instead of substituting a single look-alike character.  The result is
    rescaled so its ink matches the Hei root's ink.
    """
    # `ch` may be one char, a string of chars, or a list: one per contour (in the
    # order the contours appear in the glyph), so each dot can have its own angle.
    sources = list(ch) if isinstance(ch, (list, tuple)) else list(str(ch))
    sources = [c for c in sources if fonts.has_kai(c)]
    if not sources:
        return []
    seq = []
    for i, c in enumerate(flatten(fonts.hei, hei_gname)):
        lo, hi = c.min(axis=0), c.max(axis=0)
        seq += fonts.box_segments(sources[min(i, len(sources) - 1)], (lo[0], lo[1], hi[0], hi[1]), fill=fill)
    if not seq:
        return seq
    bounds = seg_bounds(seq)
    ink, target = seg_ink(seq), fonts.hei_ink(hei_gname)
    if bounds and ink > 0 and target > 0:
        k = min(max(math.sqrt(target / ink), 0.9), 1.05)   # 位置/大小以原字为准，只微调重量
        if abs(k - 1.0) > 0.02:
            seq = scale_segments(seq, k, ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2))
    return seq

def raise_bottom(segments, deg=16.0, band=0.40):
    """把最下方那条横画写成提：对底部笔画带做局部剪切（single-contour 友好）。

    楷书里「青字头」压在月/日上时，第三横习惯写成提（青、靑、表的上部）。
    文楷的 龶 底横是平的，且整字是一条连通轮廓（竖穿过三横），没法按轮廓拆；
    所以这里对 y 落在底部 band 内的点做水平相关剪切：dy = tan(deg)*(x-cx)，
    并在带顶平滑收敛到 0，保证与竖画的连接处不撕裂。
    """
    import math
    if not segments:
        return segments
    pts = [p for _, args in segments for p in args if isinstance(p, tuple) and len(p) == 2]
    if not pts:
        return segments
    ymin = min(p[1] for p in pts)
    ymax = max(p[1] for p in pts)
    xmin = min(p[0] for p in pts)
    xmax = max(p[0] for p in pts)
    h = max(ymax - ymin, 1e-6)
    top = ymin + band * h              # 底部笔画带的上沿
    cx = (xmin + xmax) / 2.0
    slope = math.tan(math.radians(deg))

    def warp(p):
        x, y = p
        if y >= top:
            return p
        t = (top - y) / max(top - ymin, 1e-6)     # 0 在带顶，1 在最底
        w = t * t * (3 - 2 * t)                   # smoothstep，避免连接处出现折角
        return (x, y + slope * (x - cx) * w)

    out = []
    for op, args in segments:
        out.append((op, tuple(warp(p) if isinstance(p, tuple) and len(p) == 2 else p for p in args)))
    return out


def squeeze_x(segments, k=0.85):
    """横向压窄到 k 倍（高度、笔画粗细不变），绕墨迹中心。

    「王旁」这类部件在原书里比单字王瘦：横向压缩既能变窄，又不会像等比缩放
    那样连带把字压矮。
    """
    if not segments or k <= 0:
        return segments
    pts = [p for _, args in segments for p in args if isinstance(p, tuple) and len(p) == 2]
    if not pts:
        return segments
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2.0
    out = []
    for op, args in segments:
        out.append((op, tuple((cx + (p[0] - cx) * k, p[1])
                              if isinstance(p, tuple) and len(p) == 2 else p for p in args)))
    return out


def drop_contours(segments, keep='largest'):
    """按轮廓取舍（用来做「寸去点」这类：只去掉那个点）。

    keep='largest' 保留墨量最大的若干条、丢弃最小的那一条（点）。
    轮廓按 M 切分，面积用鞋带公式粗算。
    """
    if not segments:
        return segments
    groups, cur = [], []
    for op, args in segments:
        if op == 'moveTo' and cur:
            groups.append(cur)
            cur = []
        cur.append((op, args))
    if cur:
        groups.append(cur)
    if len(groups) < 2:
        return segments

    def area(g):
        pts = [p for _, a in g for p in a if isinstance(p, tuple) and len(p) == 2]
        if len(pts) < 3:
            return 0.0
        s = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            s += x0 * y1 - x1 * y0
        return abs(s) / 2.0

    areas = [area(g) for g in groups]
    drop = areas.index(min(areas))       # 最小的轮廓 = 那一点
    out = []
    for i, g in enumerate(groups):
        if i != drop:
            out += g
    return out


def clip_below(segments, frac=0.62):
    """只保留横线以下的部分（用来做「革去掉上面廿」这种切分）。

    frac 是切分线在字形高度中的位置（0=最底，1=最顶），保留切分线**以下**的部分
    （用来去掉「革」顶上的廿）。逐条轮廓用半平面 y <= y_cut 裁剪，切口是一条平线。
    """
    if not segments:
        return segments
    cs = flatten(_segset(segments), "x", steps=6) if False else None
    # 直接用 segments 点集算 y 范围
    pts = [p for _, a in segments for p in a if isinstance(p, tuple) and len(p) == 2]
    if not pts:
        return segments
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    ycut = y0 + frac * (y1 - y0)

    groups, cur = [], []
    for op, args in segments:
        if op == 'moveTo' and cur:
            groups.append(cur)
            cur = []
        cur.append((op, args))
    if cur:
        groups.append(cur)

    out = []
    for g in groups:
        poly = [p for _, a in g for p in a if isinstance(p, tuple) and len(p) == 2]
        if len(poly) < 3:
            continue
        clipped = []
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            ain, bin_ = a[1] <= ycut, b[1] <= ycut
            if ain:
                clipped.append(a)
            if ain != bin_:
                t = (ycut - a[1]) / (b[1] - a[1])
                clipped.append((a[0] + t * (b[0] - a[0]), ycut))
        if len(clipped) < 3:
            continue
        out.append(('moveTo', (clipped[0],)))
        for p in clipped[1:]:
            out.append(('lineTo', (p,)))
        out.append(('closePath', ()))
    return out


def fit_to_box(segments, box, fill=0.96):
    """把已有轮廓等比缩放并居中放进 box（用于裁剪后的自造字形）。"""
    if not segments or not box:
        return segments
    pts = [p for _, a in segments for p in a if isinstance(p, tuple) and len(p) == 2]
    if not pts:
        return segments
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    bw, bh = max(box[2] - box[0], 1e-6), max(box[3] - box[1], 1e-6)
    s = min(bw / w, bh / h) * fill
    dx = (box[0] + box[2]) / 2 - ((x0 + x1) / 2) * s
    dy = (box[1] + box[3]) / 2 - ((y0 + y1) / 2) * s
    out = []
    for op, args in segments:
        out.append((op, tuple((p[0] * s + dx, p[1] * s + dy)
                              if isinstance(p, tuple) and len(p) == 2 else p for p in args)))
    return out


def to_glyph(segments):
    """Replay recorded segments into a real TrueType glyph (no components)."""
    pen = TTGlyphPen(None)
    for op, args in segments:
        getattr(pen, op)(*args)
    return pen.glyph()

# ------------------------------------------------- structural signature ----

def _holes(hard):
    lbl, n = ndimage.label(~hard, structure=np.ones((3, 3), bool))
    if n == 0:
        return 0
    border = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1])
    border.discard(0)
    return sum(1 for i in range(1, n + 1) if i not in border)


def struct_sig(contours, size=256, min_piece=40):
    """How many separate pieces of ink, counters, stroke ends and crossings.

    Deliberately ignores stroke weight and curvature: this is the coarse
    "is it even the same kind of shape" check that pixel metrics are blind to.
    """
    from skimage.morphology import skeletonize
    mask = rasterize(contours, size=size, ss=1, fill=0.9)
    hard = mask > 0.5
    if not hard.any():
        return {'comps': 0, 'ends': 0, 'juncs': 0, 'holes': 0}
    lbl, n = ndimage.label(hard, structure=np.ones((3, 3), bool))
    sizes = ndimage.sum(hard, lbl, range(1, n + 1))
    keep = [i + 1 for i, v in enumerate(sizes) if v >= min_piece]
    sk = skeletonize(hard)
    nb = ndimage.convolve(sk.astype(np.int8), np.ones((3, 3), np.int8) - np.eye(3, dtype=np.int8),
                          mode='constant')
    big = np.isin(lbl, keep) if keep else np.zeros_like(hard)
    return {'comps': len(keep),
            'ends': int((sk & (nb == 1) & big).sum()),
            'juncs': int(ndimage.label(sk & (nb >= 3) & big, structure=np.ones((3, 3), bool))[1]),
            'holes': _holes(hard)}


def struct_mismatch(a, b):
    """(is_mismatch, short_reason).  Only gross differences count — a stroke that
    touches in one style and not the other must not raise a flag."""
    d = abs(a['comps'] - b['comps'])
    if min(a['comps'], b['comps']) >= 2 and d >= 2:
        return True, f"墨块 {a['comps']} vs {b['comps']}"
    if (a['comps'] == 1) != (b['comps'] == 1) and max(a['comps'], b['comps']) >= 3:
        return True, f"墨块 {a['comps']} vs {b['comps']}"
    if abs(a['holes'] - b['holes']) >= 2:
        return True, f"孔洞 {a['holes']} vs {b['holes']}"
    return False, ''


# ------------------------------------------------------------------ naming --

# 字根名是笔画描述时，直接用 CJK 笔画字符（文楷 36 个笔画全覆盖），比用近似的汉字准确
STROKE_NAMES = {
    '横': '㇐', '竖': '㇑', '撇': '㇒', '捺': '㇏', '点': '㇔', '提': '㇀',
    '竖提': '㇙', '竖钩': '㇚', '竖折': '㇗', '竖弯': '㇄',
    '横折': '㇕', '横钩': '㇖', '横折钩': '㇆', '横撇': '㇇',
    '撇折': '㇜', '撇点': '㇛', '弯钩': '㇁', '斜钩': '㇂', '卧钩': '㇃',
}
STROKE_CHARS = ''.join(chr(c) for c in range(0x31C0, 0x31E4))

# 识别码 glyphs are a frame plus 1..3 marks of the 末笔; the zone picks the mark.
IDCODE_ZONE_MARK = {'1': '一', '2': '丨', '3': '丿', '4': '丶', '5': '乙'}
IDCODE_ZONE_FRAME = '囗'

# Only the nine Unicode-encoded roots are safe extra candidates; the rest of the
# radical block misleads the matcher (dense rare glyphs score well by accident).
EXTRA_ROOTS = '龰龴龵龶龷龸龹龺龻'

# 核对用的部件字表（见 scripts/kai-roots-palette.json）：只作为人工选项，
# 不参与自动匹配——把部首并进候选池会让 艹/⺿、曰/⺲ 之类的近似形互抢，准确率反而下降。
PALETTE_FILE = Path(__file__).resolve().parent.parent / 'kai-roots-palette.json'
PALETTE_GROUPS = json.loads(PALETTE_FILE.read_text(encoding='utf-8'))['groups']
COMPONENT_PALETTE = ''.join(g['chars'] for g in PALETTE_GROUPS)


def build_mapping(fonts, roots, root_names, unicode_map):
    """PUA -> character, each entry carrying its provenance and alternatives."""
    anchors = {int(k, 16): v['n'] for k, v in roots.items() if v.get('n')}
    keys = {int(k, 16): v['k'] for k, v in roots.items()}
    idcode = {int(k, 16) for k, v in roots.items() if v.get('id')}
    proposals = {int(r['id'], 16): r for r in unicode_map}
    by_key = {}
    for cp, ch in anchors.items():
        by_key.setdefault(keys[cp], set()).add(ch)
    out = {}
    for cp in sorted(fonts.hcmap):
        gname = fonts.hcmap[cp]
        if fonts.hei_bbox(gname) is None:      # empty slot in the Hei font
            continue
        if cp == 0x00A0:                       # nbsp, nothing to draw
            continue
        if cp < 0xE000:                        # 9FB0..9FBB are already characters
            ch = chr(cp)
            if fonts.has_kai(ch):
                out[cp] = {'ch': ch, 'src': 'unicode', 'score': 1.0, 'conf': '高', 'alts': []}
            continue
        if cp in idcode:
            continue                           # composed separately
        if anchors.get(cp):
            out[cp] = {'ch': anchors[cp], 'src': 'anchor', 'score': 1.0, 'conf': '高', 'alts': []}
            continue
        name = (root_names.get(f'{cp:04x}') or '').strip()
        named = STROKE_NAMES.get(name, name if len(name) == 1 else '')
        if named and fonts.has_kai(named):
            out[cp] = {'ch': named, 'src': 'name', 'score': 1.0, 'conf': '高', 'alts': []}
            continue
        cands, prior = set(), {}
        cands |= by_key.get(keys.get(cp, ''), set())
        prop = proposals.get(cp)
        if prop and prop.get('proposed'):
            cands.add(prop['proposed'])
            prior[prop['proposed']] = {'高': 0.05, '中': 0.03, '低': 0.012}.get(prop.get('conf'), 0)
            for c in prop.get('cands', []):
                if isinstance(c, (list, tuple)) and c and isinstance(c[0], str) and len(c[0]) == 1:
                    cands.add(c[0])
                    prior.setdefault(c[0], 0.02)
        if not cands:                          # no key data: fall back to every root
            cands = set(anchors.values()) | set(EXTRA_ROOTS)
        cands = {c for c in cands if c != ' ' and fonts.has_kai(c)}
        if not cands:
            continue
        # 结构否决：墨块数/孔洞差太多的候选直接排除（像素分对此不敏感）
        h_struct = fonts.hei_struct(gname)
        ok = {c for c in cands if not struct_mismatch(h_struct, fonts.kai_struct(c))[0]}
        if ok:
            cands = ok
        sig = fonts.hei_shape(gname)
        scored = sorted(((shape_distance(sig, fonts.kai_shape(c)) + prior.get(c, 0.0), c) for c in cands),
                        reverse=True)
        best, ch = scored[0]
        alts = [(c, round(v, 3)) for v, c in scored[1:7]]
        margin = best - scored[1][0] if len(scored) > 1 else 1.0
        conf = '高' if (best >= 0.93 and margin >= 0.015) else ('中' if best >= 0.88 else '低')
        out[cp] = {'ch': ch, 'src': 'shape', 'score': round(best, 3), 'conf': conf,
                   'alts': alts, 'margin': round(margin, 4)}
    return out


# ------------------------------------------------------------ 识别码 glyphs --


def idcode_parts(fonts, hei_gname):
    """Split a 识别码 glyph into (frame box, [mark boxes])."""
    contours = flatten(fonts.hei, hei_gname)
    boxes = []
    for c in contours:
        lo, hi = c.min(axis=0), c.max(axis=0)
        boxes.append((lo[0], lo[1], hi[0], hi[1]))
    boxes.sort(key=lambda b: -((b[2] - b[0]) * (b[3] - b[1])))
    frame = boxes[0] if boxes else None
    marks = [b for b in boxes[1:] if b[2] - b[0] > 40 or b[3] - b[1] > 40]
    return frame, marks


def compose_idcode(fonts, hei_gname, zone):
    """Frame plus 1..3 末笔 marks, assembled from WenKai parts."""
    frame, marks = idcode_parts(fonts, hei_gname)
    if frame is None:
        return []
    box = (frame[0], frame[1], frame[2], frame[3])
    seq = []
    if fonts.has_kai(IDCODE_ZONE_FRAME):
        seq += fonts.box_segments(IDCODE_ZONE_FRAME, box, fill=0.99)
    mark_ch = IDCODE_ZONE_MARK.get(zone, '一')
    for b in marks:
        # the first "mark" is the frame's inner box: keep it out of the marks
        if abs(b[0] - box[0]) < 200 and abs(b[2] - box[2]) < 200:
            continue
        if fonts.has_kai(mark_ch):
            seq += fonts.box_segments(mark_ch, b, fill=0.88)
    return seq
