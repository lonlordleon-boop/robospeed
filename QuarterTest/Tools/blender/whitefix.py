# -*- coding: utf-8 -*-
"""箱（複数可）に頂点が1つでも入る面の中で、白い布より暗い画素を白い布の色で塗る。
   recolor.py で紺を白へ塗り替えたあと、縁やボタンのまわりに残る暗い点を消すため。
   白の色は、箱の中の明るい画素（明るさ上位）の中央値。位置は素の姿勢の Blender 座標。
   実行: blender -b --factory-startup -P whitefix.py -- 入力.glb 出力.png "x0,x1,z0,z1;..." y上限 暗さの差"""
import bpy, sys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
BOXES = [[float(v) for v in b.split(',')] for b in a[2].split(';')]
YMAX = float(a[3]); DK = float(a[4])
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
def inbox(p):
    return p[1] <= YMAX and any(b[0] <= p[0] <= b[1] and b[2] <= p[2] <= b[3] for b in BOXES)
tris = []
for t in em.loop_triangles:
    if not any(inbox(P[v]) for v in t.vertices): continue
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
    tris.append((x0, x1, y0, y1, m))
allpx = np.concatenate([px[y0:y1+1, x0:x1+1, :3][m] for x0, x1, y0, y1, m in tris])
lum = allpx.mean(1); ref = np.median(allpx[lum >= np.percentile(lum, 60)], 0)
print("WF 面 %d  白の色 %s" % (len(tris), np.round(ref, 3)))
done = 0
for x0, x1, y0, y1, m in tris:
    blk = px[y0:y1+1, x0:x1+1]
    bad = m & (blk[..., :3].mean(2) < ref.mean() - DK)
    if bad.any():
        blk[..., :3][bad] = ref; done += int(bad.sum())
print("WF 塗った画素 %d" % done)
out = bpy.data.images.new("o", W, H); out.pixels = px.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save(); print("WF 書き出し", OUT)
