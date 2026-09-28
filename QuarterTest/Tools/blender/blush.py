# -*- coding: utf-8 -*-
"""頬の赤みを、位置のぼかし（楕円のガウス）で肌の画素だけに乗せる。
   三面図の頬は 緑×0.895・青×0.88 くらいの淡い赤み。貼り直しで消えたので描き足す。
   画素ごとに「モデルのどこに当たるか」を三角形の中の比率で求める（素の姿勢の Blender 座標）。
   実行: blender -b --factory-startup -P blush.py -- 入力.glb 出力.png 中心x(左右対称),z 幅σx,σz 緑倍率,青倍率"""
import bpy, sys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
CX, CZ = [float(v) for v in a[2].split(',')]
SX, SZ = [float(v) for v in a[3].split(',')]
KG, KB = [float(v) for v in a[4].split(',')]
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
done = 0; best = 0.0
# 画素は1回だけ塗る。三角形の縁の画素は隣の三角形の枠にも入るので、重ねて塗ると網目の線が出た。
# 1回目は三角形の内側だけ、2回目にまだ塗っていない縁（すき間）を塗る
touched = np.zeros((H, W), bool)
for TOL in (0.0, -0.05):
  for t in em.loop_triangles:
    V = P[list(t.vertices)]
    c = V.mean(0)
    if c[1] > -0.05 or abs(abs(c[0]) - CX) > 3.5*SX or abs(c[2] - CZ) > 3.5*SZ: continue
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
    m = (l1 >= TOL) & (l2 >= TOL) & (l3 >= TOL) & ~touched[y0:y1+1, x0:x1+1]
    touched[y0:y1+1, x0:x1+1] |= m
    X = l1*V[0, 0]+l2*V[1, 0]+l3*V[2, 0]; Z = l1*V[0, 2]+l2*V[1, 2]+l3*V[2, 2]
    w = np.exp(-0.5*(((np.abs(X)-CX)/SX)**2 + ((Z-CZ)/SZ)**2))
    blk = px[y0:y1+1, x0:x1+1]
    r, g, b = blk[..., 0], blk[..., 1], blk[..., 2]
    skin = m & (r > 0.5) & (r >= g) & (g >= b) & ((r-b) > 0.08) & ((r-b) < 0.45)
    if not skin.any(): continue
    blk[..., 1] = np.where(skin, g*(1-w*(1-KG)), g)
    blk[..., 2] = np.where(skin, b*(1-w*(1-KB)), b)
    px[y0:y1+1, x0:x1+1] = blk
    done += int((skin & (w > 0.05)).sum()); best = max(best, float(w[skin].max()))
print("BL 赤みを乗せた画素 %d（中心の重み最大 %.2f）" % (done, best))
out = bpy.data.images.new("o", W, H); out.pixels = px.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save(); print("BL 書き出し", OUT)
