# -*- coding: utf-8 -*-
"""動くと引っ張られて伸びる髪の房を切り取る（「数本髪の毛が引っ張られて動いてるのがある。それは切り取って」）。
   全クリップの全コマで、素の姿勢より 1.5 倍を超えて伸びる辺を探し、
   高さ ZMIN より上で、絵の色が髪（色相 12〜70度・彩度 0.35 以上）の面のうち、伸びる辺の頂点に触れる面を消す。
   消したあと、ZMIN より上で頂点が MINV 個未満の離れたかけらも消す。骨・重み・動き・絵はそのまま。
   クリップの並びは Idle・Walk_Child・Run・Skip にそろえて書き出す。
   実行: blender -b --factory-startup -P hairtrim.py -- 入力.glb 出力.glb [ZMIN 0.85] [MINV 400]"""
import bpy, bmesh, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
ZMIN = float(a[2]) if len(a) > 2 else 0.85
MINV = int(a[3]) if len(a) > 3 else 400
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
tracks = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
def pos():
    dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
    P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear(); return P
E = np.array([e.vertices[:] for e in m.edges])
P0 = pos(); L0 = np.linalg.norm(P0[E[:, 0]] - P0[E[:, 1]], axis=1) + 1e-9
mx = np.ones(len(E))
for nm, act, fs in tracks:
    arm.animation_data.action = act
    f0, f1 = map(int, act.frame_range)
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); P = pos()
        mx = np.maximum(mx, np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1) / L0)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
sv = np.zeros(len(m.vertices), bool); sv[E[mx > 1.5].ravel()] = True
# 絵の色で髪の面を判定
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data
kill = []
for p in m.polygons:
    if P0[list(p.vertices)][:, 2].min() < ZMIN: continue
    if not any(sv[v] for v in p.vertices): continue
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    h, s, val = colorsys.rgb_to_hsv(*c)
    if 12/360 <= h <= 70/360 and s >= 0.35: kill.append(p.index)
print("HT 伸びる辺 %d 本、切り取る髪の面 %d 枚" % (int((mx > 1.5).sum()), len(kill)))
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in kill], context='FACES')
# 離れた小さなかけら（首より上）を消す
bm.verts.ensure_lookup_table()
# 絵の島ごとに頂点が分かれて保存されているので、同じ位置の頂点はつながっているとみなす
def key(v): return (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
same = {}
for v in bm.verts: same.setdefault(key(v), []).append(v)
seen = set(); small = []
for v in bm.verts:
    if v.index in seen: continue
    comp = []; st = [v]; seen.add(v.index)
    while st:
        x = st.pop(); comp.append(x)
        nbrs = [e.other_vert(x) for e in x.link_edges] + same.get(key(x), [])
        for o in nbrs:
            if o.index not in seen: seen.add(o.index); st.append(o)
    zs = [(me.matrix_world @ c.co).z for c in comp]
    if len(comp) < MINV and min(zs) >= ZMIN: small.extend(comp)
bmesh.ops.delete(bm, geom=small, context='VERTS')
print("HT 消した小さなかけらの頂点 %d" % len(small))
bm.to_mesh(m); bm.free(); m.update()
# クリップの並び：Idle・Walk_Child・Run・Skip
want = ['Idle', 'Walk_Child', 'Run', 'Skip']
tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
for nm, act, fs in tracks:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, act); s2.name = nm
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("HT 書き出し", OUT, [t.name for t in arm.animation_data.nla_tracks])
