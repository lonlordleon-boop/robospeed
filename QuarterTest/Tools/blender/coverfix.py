# -*- coding: utf-8 -*-
"""素体が服から飛び出している所だけ、服を外へ押し出して隠す。

   sinkbody.py は素体のほうを引っ込める道具。ほとんどの場所はそれで足りるが、
   股や裾の縫い目の際だけは、面が斜めを向いていて光線の判定が当てにならず、
   素体の下着が白いトゲとして残った。すき間を広げると今度は太ももがへこんだ。

   こちらは逆に、服を必要なぶんだけ膨らませる。
   服は着せたときにしか出ないので、少しふくらんでも困らない。
   押し出す量は、素体が飛び出しているぶん＋すき間。飛び出していない所は動かさない。
   そのままだと押した所と押さない所の境目が角張るので、量を隣どうしでならしてから動かす。

   実行: blender -b --factory-startup -P coverfix.py -- 入力.glb 出力.glb 部品の種類
         [すき間 m 既定0.004] [届く範囲 m 既定0.025] [ならし回数 既定8] [押し出しの上限 m 既定0.02]
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, KIND = a[0], a[1], a[2]
GAP = float(a[3]) if len(a) > 3 else 0.004     # 素体と服のあいだに残すすき間
REACH = float(a[4]) if len(a) > 4 else 0.025   # 飛び出した1点が、服のどこまでを押し上げるか
SMOOTH = int(a[5]) if len(a) > 5 else 8        # 押し出し量をならす回数
MAXP = float(a[6]) if len(a) > 6 else 0.02     # 押し出しの上限

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
body = next((o for o in meshes if o.name == 'body'), None) or meshes[0]

def kind_of(o):
    for m in o.data.materials:
        if m and ':' in m.name: return m.name.split(':')[0]
    return ''

part = next((o for o in meshes if o is not body and kind_of(o) == KIND), None)
if part is None:
    print("CF 種類 %s の部品が見つからない" % KIND); sys.exit(1)
pm = part.data
print("CF 素体 頂点 %d  部品 %s 頂点 %d" % (len(body.data.vertices), part.name, len(pm.vertices)))

PW = [part.matrix_world @ v.co for v in pm.vertices]
bvh = BVHTree.FromPolygons(PW, [list(p.vertices) for p in pm.polygons], all_triangles=False, epsilon=0.0)
kd = kdtree.KDTree(len(PW))
for i, p in enumerate(PW): kd.insert(p, i)
kd.balance()

# 形状キー（sinkbody.py の引っ込め）が入っていれば、それを効かせた形で測る
sk = body.data.shape_keys
if sk:
    for k in sk.key_blocks:
        if k.name != 'Basis': k.value = 1.0
    print("CF 素体の形状キーを効かせて測る: %s" % [k.name for k in sk.key_blocks if k.name != 'Basis'])
dg = bpy.context.evaluated_depsgraph_get()
bev = body.evaluated_get(dg); bmesh_ = bev.to_mesh()
MW = body.matrix_world

push = np.zeros(len(PW), dtype=np.float64)
out = 0
for v in bmesh_.vertices:
    p = MW @ v.co
    near = bvh.find_nearest(p, REACH + MAXP)
    if near[0] is None: continue
    loc, nor = near[0], near[1]
    s = (p - loc).dot(nor)          # 正なら服の外へ出ている
    if s < -GAP: continue
    need = min(s + GAP, MAXP)
    if need <= 0: continue
    out += 1
    for co, i, d in kd.find_range(p, REACH):
        w = 1.0 - d / REACH         # 近いほど強く
        if need * w > push[i]: push[i] = need * w
bev.to_mesh_clear()
print("CF 服から飛び出していた素体の頂点 %d、押し上げる服の頂点 %d（最大 %.1f mm）"
      % (out, int((push > 1e-6).sum()), push.max()*1000))
if not (push > 1e-6).any():
    print("CF 直すところが無い"); sys.exit(0)

# 押し出し量を隣どうしでならす。境目が角張らないように
nbr = [[] for _ in range(len(PW))]
for e in pm.edges:
    nbr[e.vertices[0]].append(e.vertices[1]); nbr[e.vertices[1]].append(e.vertices[0])
for _ in range(SMOOTH):
    nxt = push.copy()
    for i, ns in enumerate(nbr):
        if ns: nxt[i] = max(push[i], 0.5*push[i] + 0.5*sum(push[j] for j in ns)/len(ns))
    push = nxt

pm.calc_normals_split() if hasattr(pm, 'calc_normals_split') else None
PMI = part.matrix_world.inverted()
moved = 0
for i, v in enumerate(pm.vertices):
    if push[i] <= 1e-6: continue
    n = (part.matrix_world.to_3x3() @ v.normal).normalized()
    v.co = PMI @ ((part.matrix_world @ v.co) + n * push[i])
    moved += 1
print("CF 服を押し出した頂点 %d（ならし %d 回、最大 %.1f mm）" % (moved, SMOOTH, push.max()*1000))

bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True)
print("CF 書き出し", DST, os.path.getsize(DST))
