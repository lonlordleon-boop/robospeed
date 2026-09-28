# -*- coding: utf-8 -*-
"""乳児期の赤ちゃん（くまの着ぐるみ）の色替え。茶色の着ぐるみだけを別の色にする（2026年9月23日）。

   着ぐるみ（色相 0.035〜0.06・鮮やかさ 0.37〜0.5・明るさ 0.45〜0.6）と髪（同じ色相・明るさ 0.25 前後）は色相が同じ。
   髪のつやの画素は明るさ 0.7 まであり、画素ごとには分けられない。そこで三角形ごとに決める:
     三角形の中の画素の中央値が「着ぐるみの茶色」なら、その三角形は着ぐるみ
     （髪の三角形は中央値が暗いので外れる。肌・目・口・クリーム色の所は中央値の色が違うので外れる）
   着ぐるみの三角形の中の、茶色の画素（色相 0〜0.12・鮮やかさ 0.2 以上）だけを塗り替える。
   クリーム色（お腹・しっぽ・耳の内側・足の裏）は鮮やかさが低いので残る。
   明るさと鮮やかさは元の値に倍率を掛けるだけなので、毛並みの模様と陰影はそのまま残る。
   顔（目・口のあたり）は位置で外す。瞳も同じ茶色で、はじめ目まで緑になった（座標は Blender、休みの姿勢の頂点）。
   画素は1回だけ塗る（三角形のふちの画素を二重に塗ると網目が出る。recolor.py で一度起きた）。

   絵の置き換えは swaptex.py で行うこと（Blender の書き出しでは元の絵が出る）。
   実行: blender -b --factory-startup -P babycolor.py -- 入力.glb 出力.png 色相,鮮やかさ倍率,明るさ倍率"""
import bpy, sys, colorsys
import numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], a[1]
TH, KS, KV = [float(v) for v in a[2].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH'); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
MX = A[..., :3].max(-1); MN = A[..., :3].min(-1)
SS = np.where(MX > 0, (MX - MN) / np.maximum(MX, 1e-6), 0); VV = MX
R_, G_, B_ = A[..., 0], A[..., 1], A[..., 2]
d = np.maximum(MX - MN, 1e-6)
HH = np.where(MX == R_, ((G_ - B_) / d) % 6, np.where(MX == G_, (B_ - R_) / d + 2, (R_ - G_) / d + 4)) / 6.0
HH = np.where(MX - MN < 1e-6, 0, HH)
brown = (HH >= 0.0) & (HH <= 0.12) & (SS >= 0.20)

m.calc_loop_triangles(); uvl = m.uv_layers.active.data
MW = me.matrix_world
def in_face(c):   # 目（左右 0.05〜0.35・高さ 0.88〜1.14）と口（左右 0.14 以内・高さ 0.80〜0.95）の前だけ。
    # 顔全体の箱（左右 0.36・高さ 0.78〜1.16）で外すと、顔のまわりのフードの内側に茶色が残った
    if c.y > -0.62: return False
    return (0.05 < abs(c.x) < 0.35 and 0.88 < c.z < 1.14) or (abs(c.x) < 0.14 and 0.80 < c.z < 0.95)
paint = np.zeros((H, W), bool); nf = nall = 0
for t in m.loop_triangles:
    if in_face(MW @ t.center): continue
    uv = np.array([tuple(uvl[l].uv) for l in t.loops]) * [W, H]
    x0, x1 = int(max(0, uv[:, 0].min() - 1)), int(min(W - 1, uv[:, 0].max() + 1))
    y0, y1 = int(max(0, uv[:, 1].min() - 1)), int(min(H - 1, uv[:, 1].max() + 1))
    if x1 < x0 or y1 < y0: continue
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = uv; dd = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(dd) < 1e-9: continue
    l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / dd; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / dd
    ins = (l1 >= -0.05) & (l2 >= -0.05) & (1 - l1 - l2 >= -0.05)
    if not ins.any(): continue
    nall += 1
    h = HH[y0:y1 + 1, x0:x1 + 1][ins]; s = SS[y0:y1 + 1, x0:x1 + 1][ins]; v = VV[y0:y1 + 1, x0:x1 + 1][ins]
    mh, ms, mv = np.median(h), np.median(s), np.median(v)
    # 着ぐるみの茶色の三角形か（髪は明るさの中央値が 0.36 未満、肌・クリームは鮮やかさが低い、口と頬は明るい）
    if not (0.015 <= mh <= 0.085 and ms >= 0.30 and 0.36 <= mv <= 0.72): continue
    nf += 1
    sub = paint[y0:y1 + 1, x0:x1 + 1]; sub |= ins & brown[y0:y1 + 1, x0:x1 + 1]
ns = np.clip(SS[paint] * KS, 0, 1); nv = np.clip(VV[paint] * KV, 0, 1)
# HSV → RGB（色相だけ置き換える）
hh6 = TH * 6.0; i = int(hh6) % 6; f = hh6 - int(hh6)
p = nv * (1 - ns); q = nv * (1 - ns * f); tt = nv * (1 - ns * (1 - f))
rgb = [(nv, tt, p), (q, nv, p), (p, nv, tt), (p, q, nv), (tt, p, nv), (nv, p, q)][i]
A[paint, 0], A[paint, 1], A[paint, 2] = rgb
print("[color] 三角形 %d のうち着ぐるみ %d・塗り替えた画素 %d・色相 %.2f" % (nall, nf, int(paint.sum()), TH))
o = bpy.data.images.new('o', W, H, alpha=True); o.pixels.foreach_set(A.ravel()); o.filepath_raw = OUT; o.file_format = 'PNG'; o.save()
