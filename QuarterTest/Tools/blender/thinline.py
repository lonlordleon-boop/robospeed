# -*- coding: utf-8 -*-
"""肌の上の細い暗い線（生成の絵の継ぎ目のひび）だけを消す（2026年9月23日、乳児期の赤ちゃん）。
   lineerase.py は「面の中央値より暗い画素」を全部塗るので、同じ箱に入った眉や前髪まで消える。
   ここでは暗い画素のうち、太いもの（眉・髪の束）を残し、細いもの（幅 1〜3 画素）だけを塗る:
     太い = 暗い画素を 2 画素ずつ削ってから 3 画素ふくらませて戻るもの（細い線は削ると消える）
   色は箱の中の肌（鮮やかさ 0.12〜0.40・明るさ 0.8 以上）の中央値。明るさはまわりに合わせない（細いので目立たない）。
   座標は Blender（x 左右・y 前が −・z 上）。絵の置き換えは swaptex.py で行うこと。
   箱は画素ごとに判定する（画素の3次元の位置を三角形の中で補間して求める）。面の中心で選ぶと、大きな三角形にかかった眉まで入った。
   箱は ; でいくつでも並べられる（線に沿って小さな箱を置く）。
   実行: blender -b --factory-startup -P thinline.py -- 入力.glb 出力.png "x0,x1,z0,z1,y上限;..." [元の絵.png] [暗さの比 0.85]"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
BOXES = [[float(v) for v in b.split(',')] for b in a[2].split(';')]
X0 = min(b[0] for b in BOXES); X1 = max(b[1] for b in BOXES); Z0 = min(b[2] for b in BOXES); Z1 = max(b[3] for b in BOXES); YMAX = max(b[4] for b in BOXES)
TEX = a[3] if len(a) > 3 and a[3] else None
DK = float(a[4]) if len(a) > 4 else 0.85
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH'); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
if TEX: img = bpy.data.images.load(TEX)
W, H = img.size
A = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
MX = A[..., :3].max(-1); MN = A[..., :3].min(-1); S = (MX - MN) / np.maximum(MX, 1e-6)
m.calc_loop_triangles(); uvl = m.uv_layers.active.data; MW = me.matrix_world
region = np.zeros((H, W), bool); nf = 0
for t in m.loop_triangles:
    P = np.array([tuple(MW @ m.vertices[v].co) for v in t.vertices]); c = P.mean(0)
    lo_, hi_ = P.min(0), P.max(0)                      # 三角形の囲みが箱に重なるか（中心で選ぶと、額に重なる前髪の長い三角形が漏れた）
    if hi_[0] < X0 or lo_[0] > X1 or hi_[2] < Z0 or lo_[2] > Z1 or lo_[1] > YMAX: continue
    uv = np.array([tuple(uvl[l].uv) for l in t.loops]) * [W, H]
    x0, x1 = int(max(0, uv[:, 0].min() - 1)), int(min(W - 1, uv[:, 0].max() + 1))
    y0, y1 = int(max(0, uv[:, 1].min() - 1)), int(min(H - 1, uv[:, 1].max() + 1))
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = uv; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9: continue
    l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
    l3 = 1 - l1 - l2
    ins = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
    X = l1 * P[0, 0] + l2 * P[1, 0] + l3 * P[2, 0]; Z = l1 * P[0, 2] + l2 * P[1, 2] + l3 * P[2, 2]; Y = l1 * P[0, 1] + l2 * P[1, 1] + l3 * P[2, 1]
    inb = np.zeros_like(ins)
    for bx0, bx1, bz0, bz1, by in BOXES:
        inb |= (X >= bx0) & (X <= bx1) & (Z >= bz0) & (Z <= bz1) & (Y <= by)
    region[y0:y1 + 1, x0:x1 + 1] |= ins & inb; nf += 1
skin = region & (S > 0.12) & (S < 0.40) & (MX > 0.8)
col = np.median(A[skin, :3], axis=0); vmed = col.max()
dark = region & (MX < vmed * DK)
def grow(m_, n, op):
    for _ in range(n):
        g = m_.copy()
        for s_, ax_ in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            r = np.roll(m_, s_, ax_); g = (g | r) if op == 'or' else (g & r)
        m_ = g
    return m_
thick = grow(grow(dark, 2, 'and'), 3, 'or')
thin = dark & ~thick
paint = grow(thin, 1, 'or') & region & ~thick
A[paint, :3] = col
print("[thin] 面 %d・暗い画素 %d・細い線 %d・塗った画素 %d・肌の色 %s" % (nf, dark.sum(), thin.sum(), paint.sum(), np.round(col, 3)))
o = bpy.data.images.new('o', W, H, alpha=True); o.pixels.foreach_set(A.ravel()); o.filepath_raw = OUT; o.file_format = 'PNG'; o.save()
