# -*- coding: utf-8 -*-
"""口の中の白い点（生成が描いた小さな歯・八重歯）を、口の中の赤で塗る（2026年9月23日、乳児期の赤ちゃん）。
   三面図に「歯なし」と書いても、口の上の角に小さな白い歯が描かれて、立体の絵にもそのまま出た。
   箱の中の面の画素のうち、ほぼ無彩色で明るい画素（鮮やかさ 0.12 未満・明るさ 0.8 以上）だけを塗る。
   肌は鮮やかさ 0.2 前後なので入らない。色は同じ箱の中の鮮やかな赤（鮮やかさ 0.45 以上）の中央値。まわり 1 画素も塗る。
   座標は Blender（x 左右・y 前が −・z 上）。絵の置き換えは swaptex.py で行うこと（書き出しでは元の絵が出る）。
   実行: blender -b --factory-startup -P mouthteeth.py -- 入力.glb 出力.png x0,x1,z0,z1,y上限 [元の絵.png]"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
X0, X1, Z0, Z1, YMAX = [float(v) for v in a[2].split(',')]
TEX = a[3] if len(a) > 3 else None
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
    if not (X0 <= c[0] <= X1 and Z0 <= c[2] <= Z1 and c[1] <= YMAX): continue
    uv = np.array([tuple(uvl[l].uv) for l in t.loops]) * [W, H]
    x0, x1 = int(max(0, uv[:, 0].min() - 1)), int(min(W - 1, uv[:, 0].max() + 1))
    y0, y1 = int(max(0, uv[:, 1].min() - 1)), int(min(H - 1, uv[:, 1].max() + 1))
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = uv; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9: continue
    l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
    region[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.05) & (l2 >= -0.05) & (1 - l1 - l2 >= -0.05); nf += 1
white = region & (S < 0.12) & (MX > 0.8)
g = white.copy(); g[1:] |= white[:-1]; g[:-1] |= white[1:]; g[:, 1:] |= white[:, :-1]; g[:, :-1] |= white[:, 1:]
paint = g & region & ((S < 0.30) | white)
red = region & (S > 0.45)
col = np.median(A[red, :3], axis=0)
A[paint, :3] = col
print("[teeth] 面 %d・白い画素 %d・塗った画素 %d・色 %s" % (nf, white.sum(), paint.sum(), np.round(col, 3)))
o = bpy.data.images.new('o', W, H, alpha=True); o.pixels.foreach_set(A.ravel()); o.filepath_raw = OUT; o.file_format = 'PNG'; o.save()
