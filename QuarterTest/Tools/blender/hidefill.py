# -*- coding: utf-8 -*-
"""服や髪に隠れて見えない所のテクスチャを、のっぺりした一色で塗り潰す。

   狙いはファイルを小さくすること。JPEG は「模様のない平らな面」をほとんど容量ゼロで詰める。
   隠れている所の模様は誰にも見えないので、捨てても損はない。

   透明にする手は使えない。JPEG に透明の情報は入らず、PNG に替えると倍以上に膨らむ。
   絵の大きさも中身に関係なく変わらない。効くのは「平らにすること」だけ。

   のりしろを残す。隠れている頂点をそのまま塗ると、服がわずかにずれた瞬間に塗った面が出る。
   だから隠れている頂点の集まりを、縁から数えて何重か内側へ削ってから塗る。
   削る量は「輪の数」で指定する。1輪でおよそ数ミリぶん内側へ下がる。

   隠れているかどうかは sinkbody.py と同じやり方で決める。
   頂点から面の向きへ光線を出し、部品に当たれば「部品の内側にいる＝隠れている」。

   実行: blender -b --factory-startup -P hidefill.py --
         入力.glb 出力.glb [のりしろの輪の数 既定2] [メッシュ名 既定body]
"""
import bpy, sys, os
import numpy as np
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
RINGS = int(a[2]) if len(a) > 2 else 2
NAME = a[3] if len(a) > 3 else "body"
# 塗る色。書かなければ「その場所の平均の色」。色そのものは容量に効かないが、
# すき間から見えたときに目立たない色にしておく意味はある
COL  = [float(v) for v in a[4].split(",")] if len(a) > 4 and a[4] else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
body = next((o for o in meshes if o.name == NAME), None) or meshes[0]
parts = [o for o in meshes if o is not body]
print("HF 素体 %s（頂点 %d）  隠す側 %s" % (body.name, len(body.data.vertices), [o.name for o in parts]))

trees = []
for p in parts:
    vs = [p.matrix_world @ v.co for v in p.data.vertices]
    ps = [list(f.vertices) for f in p.data.polygons]
    trees.append(BVHTree.FromPolygons(vs, ps, all_triangles=False, epsilon=0.0))

me = body.data
MW = body.matrix_world
NRM = MW.to_3x3().inverted().transposed()
hidden = np.zeros(len(me.vertices), dtype=bool)
for v in me.vertices:
    p = MW @ v.co
    n = (NRM @ v.normal).normalized()
    for t in trees:
        hit = t.ray_cast(p + n*0.0005, n, 0.30)     # 外向きに出して部品に当たれば内側
        if hit[0] is not None:
            hidden[v.index] = True; break
print("HF 隠れている頂点 %d / %d（%.0f%%）"
      % (hidden.sum(), len(hidden), 100.0*hidden.sum()/len(hidden)))

# のりしろ。縁から RINGS 輪ぶん内側へ下げる
nbr = [[] for _ in range(len(me.vertices))]
for e in me.edges:
    x, y = e.vertices
    nbr[x].append(y); nbr[y].append(x)
keep = hidden.copy()
for r in range(RINGS):
    nxt = keep.copy()
    for i in np.where(keep)[0]:
        for j in nbr[i]:
            if not keep[j]: nxt[i] = False; break
    keep = nxt
print("HF のりしろ %d 輪を残して、塗る頂点 %d（隠れているうちの %.0f%%）"
      % (RINGS, keep.sum(), 100.0*keep.sum()/max(1, hidden.sum())))

mat = next((m for m in me.materials if m and m.use_nodes), None)
img = None
if mat:
    for n_ in mat.node_tree.nodes:
        if n_.type == 'TEX_IMAGE' and n_.image: img = n_.image; break
if img is None:
    print("HF 絵が見つからない"); sys.exit(1)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
uv = me.uv_layers.active.data

# 塗る面＝3頂点とも塗る対象の面
tri = [f for f in me.polygons if all(keep[vi] for vi in f.vertices)]
print("HF 塗る面 %d / %d" % (len(tri), len(me.polygons)))

# その面が占めている画素の平均色を、塗る色にする（境目がいちばん目立たない）
mask = np.zeros((H, W), dtype=bool)
for f in tri:
    P = np.array([[uv[li].uv[0]*W, uv[li].uv[1]*H] for li in f.loop_indices], dtype=np.float32)
    x0 = max(0, int(np.floor(P[:,0].min())) - 1); x1 = min(W, int(np.ceil(P[:,0].max())) + 1)
    y0 = max(0, int(np.floor(P[:,1].min())) - 1); y1 = min(H, int(np.ceil(P[:,1].max())) + 1)
    if x1 <= x0 or y1 <= y0: continue
    xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    inside = np.zeros(xs.shape, dtype=bool)
    for i in range(1, len(P) - 1):
        a_, b_, c_ = P[0], P[i], P[i+1]
        d = (b_[1]-c_[1])*(a_[0]-c_[0]) + (c_[0]-b_[0])*(a_[1]-c_[1])
        if abs(d) < 1e-9: continue
        w0 = ((b_[1]-c_[1])*(xs-c_[0]) + (c_[0]-b_[0])*(ys-c_[1])) / d
        w1 = ((c_[1]-a_[1])*(xs-c_[0]) + (a_[0]-c_[0])*(ys-c_[1])) / d
        w2 = 1.0 - w0 - w1
        inside |= (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
    mask[y0:y1, x0:x1] |= inside

n_px = int(mask.sum())
if n_px == 0:
    print("HF 塗る画素が無かった"); sys.exit(1)
col = np.array(COL, dtype=np.float32) if COL else A[mask][:, :3].mean(axis=0)
A[mask, 0] = col[0]; A[mask, 1] = col[1]; A[mask, 2] = col[2]
print("HF 塗った画素 %d / %d（%.1f%%）  色 (%.3f, %.3f, %.3f)"
      % (n_px, W*H, 100.0*n_px/(W*H), col[0], col[1], col[2]))
img.pixels = A.ravel().tolist()
img.pack()

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("HF 書き出し %s %.2f MB（元 %.2f MB）"
      % (DST, os.path.getsize(DST)/1048576, os.path.getsize(SRC)/1048576))
