# -*- coding: utf-8 -*-
"""黒くて長い髪（お嬢様の小学生編）の重みを直す。
   T字で骨を入れると、背中に垂れた長い髪の重みがほとんど左腕に付いていた（首〜腰の髪 8700頂点のほぼ全部）。
   hairweight.py は元気少女のオレンジの髪を色で見分けるので、黒い髪には使えない。
   1) 髪の判定：絵の色が暗い（明るさ < DARK）か紺（リボン）の頂点。つやの明るい所を取りこぼさないよう、
      「彩度が低く明るさ 0.65 未満」の候補の中で、まわり4つ分へ広げる。高さ ZLOW より上だけ
   2) 首の関節より上の髪：頭の骨（Head）だけ
   3) 首より下の長い髪：いちばん近い胴の頂点（髪でない・腕や肩の重みが少ない）の重みを写し、
      腰・背骨・首・頭の骨だけ残す（腕・肩・脚は外す）。首から BLEND m 下までは頭の骨となだらかにつなぐ
   4) 頭の重みが 0.4 以上の頂点（顔など）から、腕・肩の重みを外す（hairweight.py と同じ）
   実行: blender -b --factory-startup -P longhair.py -- 入力.glb 出力.glb [DARK 0.28] [BLEND 0.08] [ZLOW 0.55]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix, kdtree
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
DARK = float(a[2]) if len(a) > 2 else 0.28
BLEND = float(a[3]) if len(a) > 3 else 0.08
ZLOW = float(a[4]) if len(a) > 4 else 0.55
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
for ac in list(bpy.data.actions): bpy.data.actions.remove(ac)
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
zN = (arm.matrix_world @ arm.pose.bones['neck'].head).z
uvl = m.uv_layers.active.data
NV = len(m.vertices)
vuv = np.zeros((NV, 2)); cnt = np.zeros(NV)
for p in m.polygons:
    for li in p.loop_indices:
        vi = m.loops[li].vertex_index; vuv[vi] += uvl[li].uv; cnt[vi] += 1
vuv /= np.maximum(cnt, 1)[:, None]
MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in m.vertices])
gname = {g.index: g.name for g in me.vertex_groups}
def gid(n): return me.vertex_groups[n].index if n in me.vertex_groups else None
ARMB = {g.index for g in me.vertex_groups if g.name.endswith(('Shoulder', 'Arm', 'ForeArm', 'Hand')) or 'Hand' in g.name}
KEEP = {gid(n) for n in ('Hips', 'Spine02', 'Spine01', 'Spine', 'neck', 'Head') if gid(n) is not None}
HB = {gid(n) for n in ('Head', 'head_end', 'headfront') if gid(n) is not None}
HEAD = gid('Head')
# 腕（袖・手）の頂点は髪にしない：T字の絵では袖の下側が暗く塗られ、髪と判定されて腕と一緒に動かず、トゲになった。
# 肩の関節より 3cm 外側で、腕の骨（上腕・前腕・手）から ARMR 以内の頂点は腕とみなす（肩の上に乗った髪は残る）
from mathutils import Vector
from mathutils.geometry import intersect_point_line
ARMR = 0.065
SEG = []
for s in ('Left', 'Right'):
    for bn in ('Arm', 'ForeArm', 'Hand'):
        b = arm.data.bones[s + bn]; SEG.append((arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local))
SX = abs((arm.matrix_world @ arm.data.bones['LeftArm'].head_local).x) + 0.03
def is_arm(p):
    if abs(p[0]) < SX: return False
    pv = Vector(p)
    for h, t in SEG:
        q, f = intersect_point_line(pv, h, t); f = min(1.0, max(0.0, f))
        if (pv - (h + (t - h) * f)).length < ARMR: return True
    return False
def shoulder_top(p):
    """肩の付け根の近く（肩の関節から 7cm 以内）で、腕の骨より上：肩に垂れた髪が乗る所。袖の下側（暗く塗られた所）は含まない"""
    if abs(p[0]) >= SX + 0.07: return False
    pv = Vector(p)
    for h, t in SEG[0:1] + SEG[3:4]:           # 左右の上腕
        q, f = intersect_point_line(pv, h, t); f = min(1.0, max(0.0, f)); c = h + (t - h) * f
        if (pv - c).length < ARMR and pv.z > c.z: return True
    return False
hair = np.zeros(NV, bool); cand = np.zeros(NV, bool); VAL = np.ones(NV)
for v in m.vertices:
    if P[v.index][2] < ZLOW: continue
    # 左右両方の腕の重み（どちらも 0.05 超）を持つ頂点は体には無い。自動の骨入れが長い髪に付けたもの → 色・場所によらず髪。
    # 0.15 超だけにしたら、左肩の後ろの「左腕0.85・右腕0.1」の髪が残った。腕のまわりの判定より先に見る
    # ただし明るい色（明るさ 0.6 以上：白いボレロ）は外す。色を見なかったら、肩の後ろの白い布まで髪になり、腕と一緒に動かず髪に引っ付いた
    lw0 = sum(e.weight for e in v.groups if gname[e.group] == 'LeftArm'); rw0 = sum(e.weight for e in v.groups if gname[e.group] == 'RightArm')
    u0, t0 = vuv[v.index]; val0 = max(px[int(np.clip(t0, 0, .9999) * H_), int(np.clip(u0, 0, .9999) * W_), :3])
    VAL[v.index] = val0
    if lw0 > 0.05 and rw0 > 0.05 and P[v.index][2] < zN + 0.1 and val0 < 0.6:
        hair[v.index] = True; cand[v.index] = True; continue
    if is_arm(P[v.index]):
        # 腕のまわりでも、肩の付け根の上に乗った黒い髪だけは髪にする（広げる候補には入れない＝白い袖へは広がらない）
        if shoulder_top(P[v.index]):
            u, t = vuv[v.index]
            c = px[int(np.clip(t, 0, .9999) * H_), int(np.clip(u, 0, .9999) * W_), :3]
            if max(c) < DARK: hair[v.index] = True
        continue
    u, t = vuv[v.index]
    c = px[int(np.clip(t, 0, .9999) * H_), int(np.clip(u, 0, .9999) * W_), :3]
    h, s, val = colorsys.rgb_to_hsv(*c)
    navy = 200/360 <= h <= 250/360 and s > 0.30 and val < 0.60
    # つやの明るい所（彩度の低い灰色）も候補に入れる（明るさ 0.65 まででは、背中の髪のつやが腕の重みのまま残った）
    cand[v.index] = (s < 0.25 and val < 0.6) or navy     # 0.85 までにしたら白いボレロの影まで髪に広がった。髪は明るさ 0.1〜0.3、ボレロは 0.9〜1.0
    # 左右両方の腕の重みを持つ頂点は体には無い。自動の骨入れが長い髪に付けたもの → 色によらず髪
    lw = sum(e.weight for e in v.groups if gname[e.group] == 'LeftArm'); rw = sum(e.weight for e in v.groups if gname[e.group] == 'RightArm')
    both = lw > 0.15 and rw > 0.15
    hair[v.index] = val < DARK or navy or both
    if both: cand[v.index] = True
# 同じ位置の頂点（絵の切れ目で分かれた頂点）もつながりとして扱う
canon = {}; key = {}
for v in m.vertices:
    k = tuple(np.round(np.array(v.co), 5)); canon[v.index] = key.setdefault(k, v.index)
nb = [[] for _ in range(NV)]
for e in m.edges:
    i, j = e.vertices; nb[i].append(j); nb[j].append(i)
same = {}
for vi, c0 in canon.items(): same.setdefault(c0, []).append(vi)
for _ in range(6):                     # まわり6つ分へ広げる（4つでは背中の髪のつやを取りこぼした）
    add = set()
    for i in np.nonzero(hair)[0]:
        for j in nb[i] + same[canon[i]]:
            if cand[j] and not hair[j]: add.add(j)
    hair[list(add)] = True
print("LH 首の関節 %.3f  髪と判定した頂点 %d / %d（首より上 %d・首より下 %d）" % (zN, hair.sum(), NV, (hair & (P[:, 2] >= zN)).sum(), (hair & (P[:, 2] < zN)).sum()))
# 胴の頂点（髪でない・腕や肩の重みが 0.3 未満・首より下）で近い頂点を探す木
def wsum(v, S): return sum(e.weight for e in v.groups if e.group in S)
body = [v.index for v in m.vertices if not hair[v.index] and P[v.index][2] < zN and P[v.index][2] > ZLOW - 0.1 and wsum(v, ARMB) < 0.3]
kd = kdtree.KDTree(len(body))
for n, vi in enumerate(body): kd.insert(P[vi], n)
kd.balance()
def smooth(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
newW = {}
for vi in np.nonzero(hair)[0]:
    v = m.vertices[vi]; z = P[vi][2]
    if z >= zN:
        newW[vi] = {HEAD: 1.0}; continue
    _, n, _ = kd.find(P[vi]); bv = m.vertices[body[n]]
    bw = {e.group: e.weight for e in bv.groups if e.group in KEEP}
    tot = sum(bw.values())
    bw = {g: w / tot for g, w in bw.items()} if tot > 1e-6 else {gid('Spine'): 1.0}
    t = smooth((zN - z) / BLEND)
    w = {g: t * x for g, x in bw.items()}
    w[HEAD] = w.get(HEAD, 0.0) + (1 - t)
    newW[vi] = w
nclean = 0
for v in m.vertices:
    if hair[v.index]: continue
    # 頭の重みが少しでもある頂点（腕そのものでない所）から腕・肩の重みを外す。0.4 以上だけにしたら、
    # 肩の上の髪（頭 0.05〜0.8 と腕の重みを両方持つ頂点、左右約380ずつ）が腕に引っ張られてギザギザになった
    # 明るい色（白いボレロの襟・肩）は頭の重みが 0.4 以上のときだけ（頭の重みが少し付いた襟の腕の重みを外すと、肩の布が髪に引っ付いた）
    if wsum(v, HB) < (0.4 if VAL[v.index] >= 0.6 else 0.05) or (is_arm(P[v.index]) and not shoulder_top(P[v.index])): continue
    rm = [e.group for e in v.groups if e.group in ARMB]
    if not rm: continue
    for g in rm: me.vertex_groups[g].remove([v.index])
    tot = sum(e.weight for e in v.groups)
    for e in v.groups: e.weight = e.weight / tot
    nclean += 1
print("LH 腕の重みを外した顔などの頂点", nclean)
for vi, w in newW.items():
    for e in list(m.vertices[vi].groups): me.vertex_groups[e.group].remove([int(vi)])
    for g, x in w.items():
        if x > 1e-4: me.vertex_groups[g].add([int(vi)], float(x), 'REPLACE')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
print("LH 書き出し", OUT)
