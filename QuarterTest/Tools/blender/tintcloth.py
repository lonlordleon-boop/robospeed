# -*- coding: utf-8 -*-
"""白い布（カーディガン・スカートなど）に色を乗せる。陰影はそのまま残す。
   recolor.py は色相で選ぶので、色味の無い白は選べない。そこで「明るくて色味の無い画素」を選ぶ。

   選び方:
   - 位置: 画素ごとに「モデルのどこに当たるか」を求め、高さ z が範囲に入るものだけ（素の姿勢の Blender 座標）。
   - 面ごと: 面の画素の中央値が明るく（明るさ >= 面の明るさ下限）色味が無い（鮮やかさ <= 0.12、
     青みがかった灰色なら 0.30）面だけを布とみなす。
     長い髪は背中の布の前に垂れているが、髪の面は暗いので外れる。
   - 画素ごと: 布の面の中でも、紺の線・リボン（鮮やかさが高い）と肌（赤みがある）の画素は触らない。
   塗り方: 新しい色 = 目標の色 × (その画素の明るさ ÷ 白の基準)。しわの暗さがそのまま色の濃淡になる。
   画素は1回だけ塗る（三角形の縁の画素を重ねて塗ると網目の線が出る）。
   塗ったあとは texpad.py を掛け直す（島の外側の塗り広げが古い白のまま残るため）。

   実行: blender -b --factory-startup -P tintcloth.py -- 入力.glb 出力.png z下限,z上限 目標R,G,B [白の基準 0.92] [面の明るさ下限 0.45] [面の明るさ上限] [左右の幅の上限]
   灰色の布に色を乗せるときは、白の基準をその布の明るさ（例 0.53）にし、上限で白い布を外す。
   例（秀才少女のベスト 2P）: ... shusai.glb v2.png 0.41,0.64 0.50,0.66,0.48 0.53 0.35 0.68
   例（新お嬢様 2P）: ... -- ojou.glb tint2.png 0.14,0.64 0.70,0.90,0.68"""
import bpy, sys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
# mask=マスク.png（skinmask.py で作ったもの）を渡すと、布かどうかを色で推測せず、マスクの青だけを塗る。
# 白い升のあるチェックのスカートや、肌と同じ色の金髪でも間違えない。どこに書いてもよい。
MASKARG = next((v[5:] for v in a if v.startswith('mask=')), None)
a = [v for v in a if not v.startswith('mask=')]
SRC, OUT = a[0], a[1]
Z0, Z1 = [float(v) for v in a[2].split(',')]
TGT = np.array([float(v) for v in a[3].split(',')], dtype=np.float32)
REF = float(a[4]) if len(a) > 4 else 0.92
FACEV = float(a[5]) if len(a) > 5 else 0.45   # 髪の面の中央値は 0.3 以下。脇の影の布は 0.5 前後
# 面の明るさ上限（既定なし）。秀才少女の灰色のベスト（面の中央値 0.53）だけに色を乗せ、
# 白いブラウスの袖（0.71〜0.85）を残すため
FACEVMAX = float(a[6]) if len(a) > 6 else 9.0
# 左右の幅の上限（既定なし）。ベストだけに色を乗せ、肩の付け根の袖（白が影で灰色になった所）を外すため
XMAX = float(a[7]) if len(a) > 7 else 9.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm:
    if arm.animation_data: arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH')
dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in em.vertices])
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
uvl = em.uv_layers.active.data
em.calc_loop_triangles()

def satval(rgb):
    mx = rgb.max(-1); mn = rgb.min(-1)
    return np.where(mx > 1e-4, (mx-mn)/np.maximum(mx, 1e-4), 0.0), mx

MASK = None
if MASKARG:
    import os
    mi = bpy.data.images.load(os.path.abspath(MASKARG))
    if tuple(mi.size) != (W, H):
        print("TC ！ マスクの大きさが絵と違う（%dx%d と %dx%d）" % (mi.size[0], mi.size[1], W, H)); sys.exit(1)
    MM = np.array(mi.pixels[:], dtype=np.float32).reshape(H, W, 4)[..., :3]
    MASK = (MM[..., 2] > 0.5) & (MM[..., 0] < 0.5) & (MM[..., 1] < 0.5)        # 青 = 服
    print("TC マスクを使う: %s（服の画素 %d・%.1f%%）" % (MASKARG, MASK.sum(), 100*MASK.mean()))

touched = np.zeros((H, W), bool)
faces = 0; done = 0
for TOL in (0.0, -0.05):
  for t in em.loop_triangles:
    V = P[list(t.vertices)]
    c = V.mean(0)
    if not (Z0 <= c[2] <= Z1) or abs(c[0]) > XMAX: continue
    uv = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    xs = uv[:, 0]*W; ys = uv[:, 1]*H
    x0 = max(0, int(np.floor(xs.min()))-1); x1 = min(W-1, int(np.ceil(xs.max()))+1)
    y0 = max(0, int(np.floor(ys.min()))-1); y1 = min(H-1, int(np.ceil(ys.max()))+1)
    gx, gy = np.meshgrid(np.arange(x0, x1+1)+0.5, np.arange(y0, y1+1)+0.5)
    d = (ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(d) < 1e-12: continue
    l1 = ((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/d
    l2 = ((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/d
    l3 = 1-l1-l2
    inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
    m = (l1 >= TOL) & (l2 >= TOL) & (l3 >= TOL) & ~touched[y0:y1+1, x0:x1+1]
    if not m.any(): continue
    blk = px[y0:y1+1, x0:x1+1]
    # 面が布かどうかは、面の内側の画素（まだ塗っていない元の色）で決める
    ref = blk[..., :3][inside] if inside.sum() >= 3 else blk[..., :3][m]
    med = np.median(ref, 0)
    s_med, v_med = satval(med[None, :])
    # 髪の下や脇の影の布は、青みがかった灰色に塗られていて鮮やかさが 0.12 を超える。
    # 肌は赤みがある（赤 > 青）ので、「青 >= 赤」なら鮮やかさ 0.30 まで布とみなす
    bluish = med[2] >= med[0]
    if MASK is None and (v_med[0] < FACEV or v_med[0] > FACEVMAX or s_med[0] > (0.30 if bluish else 0.12)):
        touched[y0:y1+1, x0:x1+1] |= m
        continue
    faces += 1 if TOL == 0.0 else 0
    s, v = satval(blk[..., :3])
    # 紺の線・リボン（鮮やかさ 0.4 以上）と肌（赤 > 青 で色味あり）は残す
    rr, bb = blk[..., 0], blk[..., 2]
    if MASK is not None:
        cloth = m & MASK[y0:y1+1, x0:x1+1]          # マスクがあるなら、色で推測しない
    else:
        cloth = m & ((s <= 0.15) | ((s <= 0.30) & (bb >= rr)))
    k = np.clip(v / REF, 0.0, 1.15)[..., None]
    blk[..., :3] = np.where(cloth[..., None], np.clip(TGT[None, None, :]*k, 0, 1), blk[..., :3])
    px[y0:y1+1, x0:x1+1] = blk
    touched[y0:y1+1, x0:x1+1] |= m
    done += int(cloth.sum())
print("TC 布とみなした面 %d  塗った画素 %d  目標の色 %s" % (faces, done, np.round(TGT, 3)))
out = bpy.data.images.new("o", W, H); out.pixels = px.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save(); print("TC 書き出し", OUT)
