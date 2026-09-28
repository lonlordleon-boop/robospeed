# -*- coding: utf-8 -*-
"""箱の中の顔の肌で、まわりより暗い細い線（貼り直しが描いた口の線など）だけを消す。
   面ごとに色の中央値を取り、その面の中で中央値より暗い画素を中央値の色（明るさだけ合わせる）に置き換える。
   位置は素の姿勢（骨の姿勢を外したあと）の Blender 座標。
   実行: blender -b --factory-startup -P lineerase.py -- 入力.glb 出力.png x0,x1,z0,z1,y上限 暗さの差"""
import bpy, sys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
X0, X1, Z0, Z1, YMAX = [float(v) for v in a[2].split(',')]
DK = float(a[3])
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
mat = me.active_material
img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
uvl = em.uv_layers.active.data
em.calc_loop_triangles()
done = 0; faces = 0
for t in em.loop_triangles:
    c = P[list(t.vertices)].mean(0)
    if not (X0 <= c[0] <= X1 and Z0 <= c[2] <= Z1 and c[1] <= YMAX): continue
    uv = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    xs = uv[:, 0]*W; ys = uv[:, 1]*H
    x0 = max(0, int(np.floor(xs.min()))-1); x1 = min(W-1, int(np.ceil(xs.max()))+1)
    y0 = max(0, int(np.floor(ys.min()))-1); y1 = min(H-1, int(np.ceil(ys.max()))+1)
    gx, gy = np.meshgrid(np.arange(x0, x1+1)+0.5, np.arange(y0, y1+1)+0.5)
    d = (ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(d) < 1e-12: continue
    l1 = ((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/d
    l2 = ((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/d
    m = (l1 >= -0.05) & (l2 >= -0.05) & (1-l1-l2 >= -0.05)
    blk = px[y0:y1+1, x0:x1+1]
    rgb = blk[..., :3][m]
    if len(rgb) < 4: continue
    lum = rgb.mean(1); med = np.median(rgb, 0); ml = med.mean()
    faces += 1
    bad = m & (blk[..., :3].mean(2) < ml - DK)
    if bad.any():
        blk[..., :3][bad] = med; done += int(bad.sum())
    px[y0:y1+1, x0:x1+1] = blk
print("LE 対象の面 %d  塗り直した画素 %d" % (faces, done))
out = bpy.data.images.new("o", W, H); out.pixels = px.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save(); print("LE 書き出し", OUT)
