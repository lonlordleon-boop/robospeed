# -*- coding: utf-8 -*-
"""走り・スキップの大きな動きで裂ける所の重みを直す。
   1) 袖：腕の重みが 0.7 以上で髪の色でない頂点から、頭の重みを外す（袖が頭に引かれていた）
   2) 首と襟の境目：首の付け根のまわり（髪の色の面に触れる頂点は除く）の重みを、となりとならしてなだらかにする
      （頭だけの頂点と肩の頂点が隣り合っていて、前傾して頭を起こすと 5cm 以上開いた）
   3) スコート：紺の面の頂点の重みをならす（腰ともものつなぎ目で、ひだが裂けた）
   同じ位置で分かれた頂点（絵の切れ目）は、つながっているものとして扱う。
   実行: blender -b --factory-startup -P wfix.py -- 入力.glb 出力.glb [首の回数 12] [スコートの回数 12]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
NNECK = int(a[2]) if len(a) > 2 else 12
NSKIRT = int(a[3]) if len(a) > 3 else 12
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
tracks = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; MW = me.matrix_world
NV = len(m.vertices); G = len(me.vertex_groups); gi = {g.index: g.name for g in me.vertex_groups}
Wt = np.zeros((NV, G), np.float64)
for v in m.vertices:
    for e in v.groups: Wt[v.index, e.group] = e.weight
P = np.array([tuple(MW @ v.co) for v in m.vertices])
def fcol(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    return colorsys.rgb_to_hsv(*c)
hair_v = np.zeros(NV, bool); navy_v = np.zeros(NV, bool)
for p in m.polygons:
    h, s, val = fcol(p)
    if 12/360 <= h <= 45/360 and s >= 0.45: hair_v[list(p.vertices)] = True
    if 190/360 <= h <= 250/360 and s >= 0.25: navy_v[list(p.vertices)] = True
# 同じ位置の頂点をまとめる
key = {}; canon = np.zeros(NV, int)
for v in m.vertices:
    k = tuple(np.round(np.array(v.co), 5)); canon[v.index] = key.setdefault(k, v.index)
nb = {}
for e in m.edges:
    x, y = canon[e.vertices[0]], canon[e.vertices[1]]
    if x != y: nb.setdefault(x, set()).add(y); nb.setdefault(y, set()).add(x)
def gid(name): return next(g.index for g in me.vertex_groups if g.name == name)
armg = [g.index for g in me.vertex_groups if any(k in g.name for k in ('Arm', 'Shoulder', 'Hand'))]
# 1) 袖から頭の重みを外す
hd = gid('Head')
aw = Wt[:, armg].sum(1)
sl = (aw >= 0.7) & (Wt[:, hd] > 0) & ~hair_v
Wt[sl, hd] = 0.0
print("WF 袖から頭の重みを外した頂点", int(sl.sum()))
def smooth(region, n, label):
    idx = sorted(set(canon[np.nonzero(region)[0]].tolist()))
    for it in range(n):
        new = {}
        for c in idx:
            ns = nb.get(c)
            if not ns: continue
            new[c] = 0.5 * Wt[c] + 0.5 * np.mean([Wt[x] for x in ns], 0)
        for c, w in new.items(): Wt[c] = w / max(w.sum(), 1e-9)
    # 同じ位置の頂点へ写す
    for v in range(NV):
        if canon[v] != v and canon[v] in set(idx): Wt[v] = Wt[canon[v]]
    print("WF %s ならした頂点 %d（%d 回）" % (label, len(idx), n))
# 2) 首と襟の境目
zN = (arm.matrix_world @ arm.data.bones['neck'].head_local).z
neck_r = (P[:, 2] > zN - 0.07) & (P[:, 2] < zN + 0.03) & (np.abs(P[:, 0]) < 0.13) & ~hair_v
smooth(neck_r, NNECK, "首まわり")
# 3) スコート
smooth(navy_v, NSKIRT, "スコート")
# 小さい重みを捨てて4本までにし、足して1にする
for v in m.vertices:
    w = Wt[v.index].copy(); top = np.argsort(-w)[:4]; keep = np.zeros_like(w); keep[top] = w[top]
    keep[keep < 0.01] = 0; keep /= max(keep.sum(), 1e-9); Wt[v.index] = keep
for g in me.vertex_groups:
    g.remove(list(range(NV)))
for v in range(NV):
    for gidx in np.nonzero(Wt[v])[0]: me.vertex_groups[int(gidx)].add([v], float(Wt[v, gidx]), 'REPLACE')
want = ['Idle', 'Walk_Child', 'Run', 'Skip']
tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
for nm, act, fs in tracks:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, act); s2.name = nm
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("WF 書き出し", OUT)
