# -*- coding: utf-8 -*-
"""箱の中で、動きのどこかで素の姿勢より TH 倍を超えて伸びる辺を持つ面を消す（骨・重み・動き・絵はそのまま）。
   お嬢様（小学生編）はスカートの内側が太ももの肌とつながっていて、スカートを脚と別に動かすと、
   つなぎの面が引き伸ばされて裾から針のように伸びた。スカートの内側に隠れた面なので消す。
   消したあと、箱の中で頂点が MINV 個未満の離れたかけら（同じ位置の頂点はつながりとみなす）も消す。
   実行: blender -b --factory-startup -P stretchcut.py -- 入力.glb 出力.glb x0,x1,y0,y1,z0,z1 [TH 2.5] [MINV 30]"""
import bpy, bmesh, sys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
BOX = tuple(map(float, a[2].split(',')))
TH = float(a[3]) if len(a) > 3 else 2.5
MINV = int(a[4]) if len(a) > 4 else 30
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
tracks = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
def pos():
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
    P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear(); return P
P0 = pos()
E = np.array([e.vertices[:] for e in m.edges]); L0 = np.linalg.norm(P0[E[:, 0]] - P0[E[:, 1]], axis=1) + 1e-9
mx = np.ones(len(E))
for nm, act, fs in tracks:
    arm.animation_data.action = act; f0, f1 = map(int, act.frame_range)
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); P = pos()
        mx = np.maximum(mx, np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1) / L0)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
ekey = {tuple(sorted(e)): i for i, e in enumerate(E.tolist())}
def inbox(c): return BOX[0] <= c[0] <= BOX[1] and BOX[2] <= c[1] <= BOX[3] and BOX[4] <= c[2] <= BOX[5]
cut = []
for p in m.polygons:
    vs = list(p.vertices)
    if not inbox(P0[vs].mean(0)): continue
    r = max(mx[ekey[tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))]] for i in range(len(vs)))
    if r > TH: cut.append(p.index)
print("SC2 %.1f倍を超えて伸びる面 %d 枚を消す" % (TH, len(cut)))
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in cut], context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
# 箱の中の小さな離れたかけら
bm.verts.ensure_lookup_table()
key = {}; canon = {}
for v in bm.verts: canon[v.index] = key.setdefault(tuple(round(c, 5) for c in v.co), v.index)
par = {}
def find(x):
    while par.get(x, x) != x: x = par[x]
    return x
for e in bm.edges:
    ra, rb = find(canon[e.verts[0].index]), find(canon[e.verts[1].index])
    if ra != rb: par[ra] = rb
groups = {}
for v in bm.verts: groups.setdefault(find(canon[v.index]), []).append(v)
small = [v for g in groups.values() if len(g) < MINV and inbox(np.mean([tuple(me.matrix_world @ v.co) for v in g], 0)) for v in g]
bmesh.ops.delete(bm, geom=small, context='VERTS')
print("SC2 箱の中の小さなかけらの頂点 %d を消す" % len(small))
bm.to_mesh(m); bm.free(); m.update()
want = ['Idle', 'Walk_Child', 'Run', 'Skip']
tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
for nm, act, fs in tracks:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, act); s2.name = nm
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("SC2 書き出し", OUT)
