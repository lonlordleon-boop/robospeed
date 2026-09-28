# -*- coding: utf-8 -*-
"""前髪の生えぎわの下の額・こめかみに描かれた「白〜灰色の地に髪の筋」の絵を、髪の色で塗る。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、右前から見ると前髪のすき間が白っぽく見えた（「反対の角度だって酷い」）。前髪をどけて描くと、
   目の上の額の帯に、肌色ではなく白〜灰色の地に髪の筋が描かれていた。面の形は肌（額）なので、面ごとの判定では拾えない。
   1) 箱（額・こめかみ）の中の面の、絵の画素ごとに 3D の位置を出す
   2) 灰色〜白の画素（明るさ ≥ VMIN・彩度 < SMAX）を塗る。肌色（彩度 0.1 以上のうすいだいだい）は塗らない
   3) 目のまわりの楕円（中心 x=±EX・高さ EZ、横の半径 AX・縦の半径 AZ）の中は塗らない（白目が同じ色）
   4) まわり（半径 5 画素）の半分以上が肌色の画素は塗らない（額の肌のハイライトを黒くしないため）
   --mask で塗る所だけ緑のマスク、--check で塗る所を緑にした確かめ用の glb を書く（--check のときは出力の絵を書かない）
   灰色だけ塗ると、額の帯のうすい肌色（彩度 0.10〜0.12）が残って、かえって欠片に見えた → お嬢様は --smax 0.25 --skinr 1.1（帯の明るい画素をすべて髪の色に）
   実行: blender -b --factory-startup -P greypaint.py -- 入力.glb 出力.png [--box x0,x1,y0,y1,z0,z1] [--smax 0.10] [--skinr 0.5] [--mask マスク.png] [--check 確かめ.glb]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
BOX = tuple(map(float, opt('--box', '-0.13,0.13,-0.2,-0.06,0.955,1.05').split(',')))
VMIN = float(opt('--vmin', 0.55)); SMAX = float(opt('--smax', 0.10))
EX, EZ, AX, AZ = map(float, opt('--eye', '0.05,0.957,0.042,0.030').split(','))
SKINR = float(opt('--skinr', 0.5))   # まわりの肌色の割合がこれ以上なら塗らない（1.1 で無効。額の帯は肌色寄りの画素も髪の色にする時）
# --occl FRAC：前から見るいろいろな向き（横 −60〜60 度・上下 −10〜25 度）のうち、FRAC 以上の向きで髪（暗い面）に隠れる画素だけ塗る。
#   額の帯を全部塗ると、前髪の先より下の、正面からふつうに見える額（眉間）まで黒くなった。前髪の陰の画素は、前髪のすき間からしか見えない
OCCL = float(opt('--occl', 0)); SMAX2 = float(opt('--smax2', 0.25))   # 隠れ具合で塗るのは、彩度 SMAX2 未満の明るい画素（肌色寄りも）。彩度 SMAX 未満の灰色は隠れ具合を見ずに塗る
MASK = opt('--mask', None); CHECK = opt('--check', None)
SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
mx = px[..., :3].max(2); mn = px[..., :3].min(2); sat = (mx - mn) / np.maximum(mx, 1e-6)
grey = (mx >= VMIN) & (sat < SMAX)
skin = (mx >= 0.55) & (sat >= 0.10) & (sat < 0.4) & (px[..., 0] >= px[..., 2])
# まわり 5 画素の肌色の割合（箱のたたみ込み）
def boxmean(A, r):
    c = np.cumsum(np.cumsum(np.pad(A.astype(np.float32), ((1, 0), (1, 0))), 0), 1)
    H, W = A.shape; y0 = np.clip(np.arange(H) - r, 0, H); y1 = np.clip(np.arange(H) + r + 1, 0, H)
    x0 = np.clip(np.arange(W) - r, 0, W); x1 = np.clip(np.arange(W) + r + 1, 0, W)
    S = c[y1][:, x1] - c[y0][:, x1] - c[y1][:, x0] + c[y0][:, x0]
    return S / ((y1 - y0)[:, None] * (x1 - x0)[None, :])
skinr = boxmean(skin, 5)
def inb(c): return BOX[0] <= c.x <= BOX[1] and BOX[2] <= c.y <= BOX[3] and BOX[4] <= c.z <= BOX[5]
def fcol(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0); return px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
# 髪の色：箱のまわりの暗い面の中央値
dk = [fcol(p) for p in m.polygons if colorsys.rgb_to_hsv(*fcol(p))[2] < 0.4 and inb(MW @ p.center)]
hair = np.median(np.array(dk), 0); print("GP 髪の色", tuple(round(float(x), 3) for x in hair))
# --skin：髪の色でなく、額の肌の色（箱の中の肌の面の、肌色の画素の中央値）で塗る。髪の面（真ん中が暗い面）は塗らない。
#   額の帯を髪の色で塗ったら「額を消した」だけになり、正面で目のすぐ上がぎざぎざに黒くなった。前髪のすき間から見えるのは額なので、肌の色が正しい
SKIN = '--skin' in a
if SKIN:
    a.remove('--skin')
    sk = []
    for p in m.polygons:
        c = MW @ p.center
        if not inb(c) or colorsys.rgb_to_hsv(*fcol(p))[2] < 0.4: continue
        uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0); iy, ix = int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_)
        if skin[iy, ix] and mx[iy, ix] >= 0.8: sk.append(px[iy, ix, :3])
    hair = np.median(np.array(sk), 0); print("GP 肌の色（%d 面の中央値）" % len(sk), tuple(round(float(x), 3) for x in hair))
res = px.copy(); msk = np.zeros((H_, W_, 4), np.float32); msk[..., 3] = 1; npx = 0; nf = 0
paint = np.zeros((H_, W_), bool); cand = np.zeros((H_, W_), bool)
CLOSE = int(opt('--close', 0))   # 塗った所のすき間を埋める半径（画素）
EYE2 = float(opt('--eye2', 0))   # 目の楕円の縦の半径を小さくする時の値
if OCCL > 0:
    import bmesh, math
    from mathutils.bvhtree import BVHTree
    bw = bmesh.new(); bw.from_mesh(m); bw.transform(MW); bw.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bw)
    DKF = np.array([colorsys.rgb_to_hsv(*fcol(p))[2] < 0.4 for p in m.polygons])
    DIRS = []
    for azd in range(-60, 61, 15):
        for eld in (-10, 10, 25):
            ar, er = math.radians(azd), math.radians(eld)
            DIRS.append(Vector((math.sin(ar) * math.cos(er), -math.cos(ar) * math.cos(er), math.sin(er))))
    def occluded(q, n):
        hid = tot = 0
        for d in DIRS:
            if d.dot(n) < 0.05: continue
            tot += 1; h = tree.ray_cast(q + d * 0.0008, d, 0.12)
            if h[0] is not None and DKF[h[2]]: hid += 1
        return tot > 0 and hid / tot >= OCCL
for p in m.polygons:
    c = MW @ p.center
    if not inb(c): continue
    if SKIN and colorsys.rgb_to_hsv(*fcol(p))[2] < 0.4: continue   # 髪の面は肌色にしない
    uv = [uvl[li].uv[:] for li in p.loop_indices]; P = [MW @ m.vertices[v].co for v in p.vertices]; hit = False
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]; T = (P[0], P[k], P[k+1])
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d; l3 = 1 - l1 - l2
        M = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        # 画素の 3D の位置
        X = l1 * T[0].x + l2 * T[1].x + l3 * T[2].x; Z = l1 * T[0].z + l2 * T[1].z + l3 * T[2].z
        eye = np.minimum(((np.abs(X) - EX) / AX) ** 2 + ((Z - EZ) / AZ) ** 2, 9) < 1
        if EYE2 > 0:
            # 目の楕円を縦に小さく（EYE2）し、元の楕円の中では真っ白（白目）だけ外す。楕円が大きいと、まつげと塗った帯の間に肌色の線が残った
            big = eye; eye = np.minimum(((np.abs(X) - EX) / AX) ** 2 + ((Z - EZ) / EYE2) ** 2, 9) < 1
            sub0 = (slice(y0, y1 + 1), slice(x0, x1 + 1))
            eye = eye | (big & (mx[sub0] > 0.95) & (sat[sub0] < 0.04))
        sub = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        MM = M & grey[sub] & ~eye & (skinr[sub] < SKINR) & (Z >= BOX[4])
        cand[sub] |= M & (mx[sub] >= VMIN) & (sat[sub] < SMAX2) & ~eye & (Z >= BOX[4])   # すき間埋めで塗ってよい画素
        if OCCL > 0:
            M2 = M & (mx[sub] >= VMIN) & (sat[sub] < SMAX2) & ~eye & (Z >= BOX[4]) & ~MM   # 隠れ具合を見る画素
        if not MM.any() and not (OCCL > 0 and M2.any()): continue
        if OCCL > 0:
            base = MM.copy(); MM = M2
            # 4×4 画素のかたまりごとに、真ん中の 3D の位置で隠れ具合を調べる
            Y3 = l1 * T[0].y + l2 * T[1].y + l3 * T[2].y
            n = (T[1] - T[0]).cross(T[2] - T[0]).normalized()
            if n.y > 0: n = -n   # 顔の面は前（−y）向き
            keep = np.zeros_like(MM)
            for by0 in range(0, MM.shape[0], 4):
                for bx0 in range(0, MM.shape[1], 4):
                    blk = MM[by0:by0+4, bx0:bx0+4]
                    if not blk.any(): continue
                    ii = np.argwhere(blk)[len(np.argwhere(blk)) // 2]; yy, xx = by0 + ii[0], bx0 + ii[1]
                    q = Vector((float(X[yy, xx]), float(Y3[yy, xx]), float(Z[yy, xx])))
                    if occluded(q, n): keep[by0:by0+4, bx0:bx0+4] = blk
            MM = keep | base
            if not MM.any(): continue
        paint[sub] |= MM; hit = True
    nf += hit
if CLOSE > 0:
    # 塗った所のすき間（肌色寄りで残った画素）を埋める。塗った画素を CLOSE 画素ふくらませてから縮め（クロージング）、塗ってよい画素に限る。
    # 灰色だけ塗ると、目の上の帯が塗った所と残った所のまだらになり、ふちがぎざぎざの欠片に見えた
    def grow(A, r):
        B = A.copy()
        for _ in range(r):
            C = B.copy(); C[1:] |= B[:-1]; C[:-1] |= B[1:]; C[:, 1:] |= B[:, :-1]; C[:, :-1] |= B[:, 1:]; B = C
        return B
    def shrink(A, r): return ~grow(~A, r)
    add = shrink(grow(paint, CLOSE), CLOSE) & cand & ~paint
    print("GP すき間埋めで足した画素 %d" % int(add.sum())); paint |= add
res[paint, :3] = (0, 1, 0) if CHECK else hair; msk[paint, :3] = (0, 1, 0); npx = int(paint.sum())
print("GP 灰色〜白の画素を%s：%d 画素・%d 面" % ('緑で印を付けた' if CHECK else '髪の色で塗った', npx, nf))
if MASK:
    im = bpy.data.images.new("m", W_, H_, alpha=True); im.pixels = msk.ravel(); im.filepath_raw = MASK; im.file_format = 'PNG'; im.save(); print("GP マスク", MASK)
if CHECK:
    img.scale(W_, H_); img.pixels = res.ravel(); img.pack()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=CHECK, export_format='GLB', export_animations=False, export_skins=True, export_yup=True); print("GP 確かめ用", CHECK)
else:
    im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save(); print("GP 書き出し", OUT)
