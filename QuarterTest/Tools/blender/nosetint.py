# -*- coding: utf-8 -*-
"""鼻に色を足す（2026年9月23日、乳児期の赤ちゃん）。
   生成の絵の鼻は薄い点で、でこぼこの陰と合わさって初めて鼻に見えていた。facenormal.py で面の向きをそろえたら
   陰が消えて「鼻の色が消えた」と言われた。絵の鼻の点を、まわりに向かってなめらかに薄くなる桃色で濃くする。
   ・画素ごとに3次元の位置を三角形の中で補間し、鼻の中心からの距離（正面から見た 左右・高さ）で重みを付ける
   ・前を向いた面（前後 y が YMAX より前）だけ。色は元の色と目標の色を重みで混ぜる（陰影の明るさの差は残す）
   座標は Blender（x 左右・y 前が −・z 上）。絵の置き換えは swaptex.py で行うこと。
   中心に x,y,z（3つ）を書くと、その点（鼻の頭）からの3次元の距離で塗る（鼻の頭にチョンと）。
   tip と書くと顔の真ん中で一番前に出た点を探すが、赤ちゃんは上くちびるのふくらみ（0.925）が鼻（0.97）より前に出ていて、
   くちびるを選んで鼻血のように見えた。顔の真ん中の縦の断面（前後の位置を高さごとに）を測って、鼻の高さを確かめてから x,y,z で渡すこと。
   さらに消す半径を付けると、鼻の頭のまわり（上に寄せた範囲）の、肌より赤い画素を肌の色に戻す（生成の絵の薄い鼻の点・前に塗った色を消す）。
   実行: blender -b --factory-startup -P nosetint.py -- 入力.glb 出力.png 中心x,z|tip 半径 r,g,b 強さ [y上限 -0.7] [消す半径]"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
TIP = a[2] == 'tip' or a[2].count(',') == 2
CX, CZ = (0.0, 0.0) if TIP else [float(v) for v in a[2].split(',')]
TP3 = np.array([float(v) for v in a[2].split(',')]) if a[2].count(',') == 2 else None
RAD = float(a[3]); COL = np.array([float(v) for v in a[4].split(',')]); K = float(a[5])
YMAX = float(a[6]) if len(a) > 6 else -0.7
CLR = float(a[7]) if len(a) > 7 else 0.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
if arm:
    from mathutils import Matrix
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH'); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
V = np.array([tuple(me.matrix_world @ v.co) for v in m.vertices])
if TP3 is not None:
    TP = TP3; CX, CZ = TP[0], TP[2]
elif TIP:
    cm = (np.abs(V[:, 0]) < 0.05) & (V[:, 2] > 0.84) & (V[:, 2] < 1.02) & (V[:, 1] < YMAX)
    TP = V[np.nonzero(cm)[0][np.argmin(V[cm, 1])]]
    CX, CZ = TP[0], TP[2]
    print("[nose] 鼻の頭 %s" % np.round(TP, 3))
m.calc_loop_triangles(); uvl = m.uv_layers.active.data; MW = me.matrix_world
Wt = np.zeros((H, W), np.float32); Cl = np.zeros((H, W), bool); nf = 0
for t in m.loop_triangles:
    P = np.array([tuple(MW @ m.vertices[v].co) for v in t.vertices])
    if P[:, 1].min() > YMAX: continue
    if np.hypot(P[:, 0].mean() - CX, P[:, 2].mean() - CZ) > max(RAD * 2, CLR * 1.5 + 0.04): continue
    uv = np.array([tuple(uvl[l].uv) for l in t.loops]) * [W, H]
    x0, x1 = int(max(0, uv[:, 0].min() - 1)), int(min(W - 1, uv[:, 0].max() + 1))
    y0, y1 = int(max(0, uv[:, 1].min() - 1)), int(min(H - 1, uv[:, 1].max() + 1))
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = uv; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9: continue
    l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d; l3 = 1 - l1 - l2
    ins = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
    X = l1 * P[0, 0] + l2 * P[1, 0] + l3 * P[2, 0]; Z = l1 * P[0, 2] + l2 * P[1, 2] + l3 * P[2, 2]
    if TIP:
        Y = l1 * P[0, 1] + l2 * P[1, 1] + l3 * P[2, 1]
        r = np.sqrt((X - TP[0]) ** 2 + (Y - TP[1]) ** 2 + (Z - TP[2]) ** 2) / RAD
    else:
        r = np.hypot(X - CX, Z - CZ) / RAD
    if CLR > 0:                                          # 消す範囲は鼻の頭から上へ寄せる（絵の点は形の鼻より上にあった）
        Cl[y0:y1 + 1, x0:x1 + 1] |= ins & (np.hypot(X - CX, (Z - CZ - CLR * 0.5) / 1.6) < CLR)
    w = np.where(ins, np.clip(1 - r, 0, 1), 0); w = w * w * (3 - 2 * w)
    sub = Wt[y0:y1 + 1, x0:x1 + 1]; np.maximum(sub, w, out=sub); nf += 1
if CLR > 0:
    MX = A[..., :3].max(-1); MN = A[..., :3].min(-1)
    ring = Cl & (MX > 0.8)
    skin = np.median(A[ring, :3], axis=0)
    red = Cl & ((A[..., 0] - A[..., 2]) > (skin[0] - skin[2]) + 0.02)
    A[red, :3] = skin
    print("[nose] 消した赤い画素 %d・肌の色 %s" % (int(red.sum()), np.round(skin, 3)))
w = (Wt * K)[..., None]
A[..., :3] = A[..., :3] * (1 - w) + COL * w
print("[nose] 面 %d・色を足した画素 %d" % (nf, int((Wt > 0.01).sum())))
o = bpy.data.images.new('o', W, H, alpha=True); o.pixels.foreach_set(A.ravel()); o.filepath_raw = OUT; o.file_format = 'PNG'; o.save()
