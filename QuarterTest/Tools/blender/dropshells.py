# -*- coding: utf-8 -*-
"""指定した名前のメッシュから、小さな「つながった塊」を消す（部品に散った破片のゴミ取り）。

   生成した部品から灰色の面を消すと、掌や肘のそばに数頂点だけの破片が残ることがある。
   同じ位置の頂点をつないだ上で塊に分け、頂点数がしきい値より少ない塊を丸ごと消す。
   骨・重み・アニメ・材質はそのまま。Blender で読み直して書き出すだけ。

   実行: blender -b --factory-startup -P dropshells.py -- 入力.glb 出力.glb メッシュ名の先頭 [頂点数の下限 既定100]
"""
import bpy, sys, os, bmesh
a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, NAME = a[0], a[1], a[2]
MINV = int(a[3]) if len(a) > 3 else 100

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
obj = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(NAME))
mesh = obj.data
# 同じ位置の頂点をつないでから塊を数える（glTF は UV の継ぎ目で頂点が分かれている）
bm = bmesh.new(); bm.from_mesh(mesh)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
n = len(bm.verts); par = list(range(n))
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for e in bm.edges:
    a_, b_ = find(e.verts[0].index), find(e.verts[1].index)
    if a_ != b_: par[a_] = b_
size = {}
for i in range(n): r = find(i); size[r] = size.get(r, 0) + 1
small = [f for f in bm.faces if size[find(f.verts[0].index)] < MINV]
nshell = sum(1 for r, s in size.items() if s < MINV)
print("DS %s: 塊 %d 個のうち頂点 %d 未満の塊 %d 個（面 %d 枚）を消す" % (obj.name, len(size), MINV, nshell, len(small)))
bmesh.ops.delete(bm, geom=small, context='FACES')
bm.to_mesh(mesh); bm.free(); mesh.update()
print("DS 残った面 %d、頂点 %d" % (len(mesh.polygons), len(mesh.vertices)))
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB', export_animations=True, export_skins=True, export_yup=True)
print("DS 書き出し", DST, os.path.getsize(DST))
