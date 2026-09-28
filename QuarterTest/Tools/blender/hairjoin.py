# -*- coding: utf-8 -*-
"""髪と服の境目の重みをなだらかにつなぐ。形・骨・動き・絵はそのまま、重みだけ。面は消さない。
   お嬢様（小学生編）は、肩の白い服の頂点（腕の重み 0.8〜0.9）と、その上に乗る髪の頂点（頭の重み 0.9）が
   1本の辺でじかにつながっていて、腕を振るとその辺だけが 10〜20 倍に伸び、肩から髪へ白い筋が出た（「肩と髪が引っ付いてる」）。
   背中の長い髪も、首より下で近くの胴の重みを写したため、となり同士で重みが食い違い、走ると髪の中が裂けた。
   1) 境目：暗い頂点（髪）と明るい頂点（服・肌）をつなぐ辺のうち、両端の重みが大きく違うもの（差の合計 ≥ 0.5）
   2) 境目から RING 輪以内の頂点の重みを、となりの平均と NIT 回ならす（境目の外の重みは動かさない）
   3) 首より下の髪（暗い頂点）どうしも NIT 回ならす（服の重みは混ぜない）
   明るさは同じ位置の頂点の中で一番明るい色で見る（縫い目の頂点は絵の切れ目の暗い色を拾うことがある）
   実行: blender -b --factory-startup -P hairjoin.py -- 入力.glb 出力.glb [RING 3] [NIT 12] [ZMIN 0.55]"""
import bpy, sys, colorsys, numpy as np
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
RING = int(a[2]) if len(a) > 2 else 3
NIT = int(a[3]) if len(a) > 3 else 12
ZMIN = float(a[4]) if len(a) > 4 else 0.55        # これより下（スカート・脚・靴）は触らない
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; vuv = {}
for l in m.loops: vuv.setdefault(l.vertex_index, uvl[l.index].uv[:])
NV = len(m.vertices); G = len(me.vertex_groups); gi = {g.index: g.name for g in me.vertex_groups}
P = np.array([tuple(me.matrix_world @ v.co) for v in m.vertices])
Wt = np.zeros((NV, G))
for v in m.vertices:
    for e in v.groups: Wt[v.index, e.group] = e.weight
# 同じ位置の頂点は 1 つにまとめる
canon = np.zeros(NV, int); key = {}
for v in m.vertices: canon[v.index] = key.setdefault(tuple(np.round(np.array(v.co), 5)), v.index)
# 暗い（髪）かどうかは、まわりの面の真ん中の色の多数決で決める。頂点の位置の色は絵の切れ目の暗い色を拾うことがあり、
# 袖の前の白い面の頂点が「髪」になって境目扱いされた
DK = np.zeros(NV); NF = np.zeros(NV)
for p in m.polygons:
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    d = 1.0 if colorsys.rgb_to_hsv(*c)[2] < 0.5 else 0.0
    for vi in p.vertices: DK[canon[vi]] += d; NF[canon[vi]] += 1
C = sorted(set(canon.tolist())); DARK = {c for c in C if NF[c] > 0 and DK[c] / NF[c] >= 0.5}
# ならす時は短い辺（EMAX 未満）だけを伝う。袖の大きな面（辺 7cm）を伝ったら、ひじの重みが肩の近くまで広がり、
# ひじを曲げると袖の前が折れて尖った（お嬢様 4 回目）
EMAX = 0.025
nb = {}
for e in m.edges:
    x, y = canon[e.vertices[0]], canon[e.vertices[1]]
    if x != y and np.linalg.norm(P[x] - P[y]) < EMAX: nb.setdefault(x, set()).add(y); nb.setdefault(y, set()).add(x)
zN = (arm.matrix_world @ arm.data.bones['neck'].head_local).z if 'neck' in arm.data.bones else (arm.matrix_world @ arm.data.bones['Head'].head_local).z
# 1) 境目
seed = set()
for x in C:
    if P[x][2] < ZMIN or x not in DARK: continue
    for y in nb.get(x, ()):
        if y in DARK or P[y][2] < ZMIN: continue
        if np.abs(Wt[x] - Wt[y]).sum() >= 0.5: seed.add(x); seed.add(y)
zone = set(seed); front = set(seed)
for _ in range(RING):
    front = {y for x in front for y in nb.get(x, ()) if y not in zone and P[y][2] >= ZMIN}; zone |= front
from mathutils import kdtree   # 境目から 4cm より遠い頂点はならさない
ks = kdtree.KDTree(len(seed))
for n, x in enumerate(seed): ks.insert(P[x], n)
ks.balance(); zone = {x for x in zone if ks.find(P[x])[2] <= 0.04}
print("HJ 境目の頂点 %d  ならす頂点 %d" % (len(seed), len(zone)))
def smooth(vs, only_dark):
    vs = sorted(vs)
    for _ in range(NIT):
        new = {}
        for x in vs:
            ns = [y for y in nb.get(x, ()) if (not only_dark or y in DARK)]
            if ns: new[x] = 0.5 * Wt[x] + 0.5 * np.mean([Wt[y] for y in ns], 0)
        for x, w in new.items(): Wt[x] = w
def jump(vs):   # となりとの重みの差の合計の最大（直す前後で比べる）
    return max((np.abs(Wt[x] - Wt[y]).sum() for x in vs for y in nb.get(x, ())), default=0)
j0 = jump(seed); smooth(zone, False); print("HJ 境目のとなりとの差の最大 %.2f → %.2f" % (j0, jump(seed)))
# 3) 首より下の髪どうし
hair = {x for x in DARK if ZMIN <= P[x][2] < zN}
j0 = jump(hair); smooth(hair, True); print("HJ 首より下の髪 %d 頂点：差の最大 %.2f → %.2f" % (len(hair), j0, jump(hair)))
done = zone | hair
for v in m.vertices:
    c = canon[v.index]
    if c not in done: continue
    w = Wt[c].copy(); top = np.argsort(-w)[:4]; keep = np.zeros_like(w); keep[top] = w[top]
    keep[keep < 0.01] = 0; keep /= max(keep.sum(), 1e-9)
    for e in list(v.groups): me.vertex_groups[e.group].remove([v.index])
    for g in np.nonzero(keep)[0]: me.vertex_groups[int(g)].add([v.index], float(keep[g]), 'REPLACE')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("HJ 書き出し", OUT)
