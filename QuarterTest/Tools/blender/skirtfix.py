# -*- coding: utf-8 -*-
"""スカート（ワンピースの裾）が脚と一緒に跳ね上がるのを抑える。形と骨はそのまま、重みだけ。
   お嬢様（小学生編）は裾の下半分の重みの 82〜100% がももの骨に付いていて、走り・スキップでももを上げると
   裾もほぼ水平まで跳ね上がった（「動くとスカートが必要以上に跳ね上がってる」）。
   1) スカートの頂点：高さ ZLO〜ZHI、|x| < 0.30、絵の色が布（明るく彩度の低い白、または青い花柄）。肌・髪は外す
   2) スカートの頂点の重みを、となり（同じ位置の頂点もつながり）と NSMOOTH 回ならす（左右のももの境目の裂け目を減らす）
   3) 脚の骨（UpLeg・Leg）の重みの合計を CAP 以下にし、減らした分を腰（Hips）へ回す
   3) 上限は前後で変える（前側は上限なし、後ろ側は CAP）
   実行: blender -b --factory-startup -P skirtfix.py -- 入力.glb 出力.glb [CAP 0.30] [ZLO 0.30] [ZHI 0.62] [NSMOOTH 8] [YC -0.04] [RL0 0.075] [RL1 0.11] [FRONT 0.8] [SIDEW 0.06] [HGT 0.18]
   ZLO は裾のいちばん低い所のすぐ下（お嬢様は裾 0.37m → 0.35）。低くすると脚の肌まで直してしまう"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
CAP = float(a[2]) if len(a) > 2 else 0.30          # 後ろ側の上限
YC = float(a[6]) if len(a) > 6 else -0.04           # 胴の前後の真ん中（m）
# 上限は前後で変える：前側（YC-0.06 より前）は上限なし＝ひざに乗って持ち上がる、後ろ側（YC+0.03 より後ろ）は CAP。
# 全体を 0.45 にしたら、ももを上げた時に脚がスカートの前を突き抜けて太ももが外に出た
def capy(y):
    t = min(1.0, max(0.0, (y - (YC - 0.06)) / 0.09)); t = t * t * (3 - 2 * t)
    return 1.0 * (1 - t) + CAP * t
ZLO = float(a[3]) if len(a) > 3 else 0.30
ZHI = float(a[4]) if len(a) > 4 else 0.62
NSM = int(a[5]) if len(a) > 5 else 8
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
# スカートは形で選ぶ：ももとすねの骨から RLEG 以上離れた頂点（脚の肌は骨の近く、スカートは外へ広がる）。
# 色で選んだら、肌色に塗られたスカートの裏側が漏れてももの重みのまま残り、表と裏が離れて間が伸びた
from mathutils import Vector
from mathutils.geometry import intersect_point_line
RLEG = 0.07
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
LSEG = [(bh(s + 'UpLeg'), bh(s + 'Leg')) for s in ('Left', 'Right')] + [(bh(s + 'Leg'), bh(s + 'Foot')) for s in ('Left', 'Right')]   # もも・すね
def legdist(p):
    pv = Vector(p); best = 9.0
    for h, t in LSEG:
        q, f = intersect_point_line(pv, h, t); f = min(1.0, max(0.0, f)); best = min(best, (pv - (h + (t - h) * f)).length)
    return best
# 脚の肌は骨から 7cm ほどまである（ひざ下のふくらはぎで最大 7.2cm）。5cm から混ぜたら、裾より下の太もも・ひざの肌まで
# 腰の重みが混ざり、歩くと肌が引き伸ばされて筋になった → RL0〜RL1（既定 7.5〜11cm）でなめらかに。ZLO も裾のすぐ下にする
RL0 = float(a[7]) if len(a) > 7 else 0.075
RL1 = float(a[8]) if len(a) > 8 else 0.11
# 暗さ（髪の先）は同じ位置の頂点の中で一番明るい色で見る。縫い目の頂点は絵の切れ目の暗い色を拾うことがあり、
# 1つだけで決めたら裾の 53 頂点が「髪の先」として直しから漏れ、ももの重み 1.0 のまま裾を引っ張った
canon0 = {}; VAL = np.zeros(NV)
for v in m.vertices:
    uv = vuv.get(v.index)
    if uv is None: continue
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    VAL[v.index] = colorsys.rgb_to_hsv(*c)[2]
    k = tuple(np.round(np.array(v.co), 5)); canon0[k] = max(canon0.get(k, 0.0), VAL[v.index])
for v in m.vertices: VAL[v.index] = canon0.get(tuple(np.round(np.array(v.co), 5)), VAL[v.index])
sk = np.zeros(NV, bool); SF = np.zeros(NV)   # SF: スカートらしさ（脚の骨から RL0 で 0、RL1 で 1、間はなめらか）
for v in m.vertices:
    p = P[v.index]
    if not (ZLO < p[2] < ZHI and abs(p[0]) < 0.30): continue
    if v.index not in vuv: continue
    val = VAL[v.index]
    if val < 0.35: continue                                   # 髪の先
    if sum(e.weight for e in v.groups if gi[e.group].endswith(('Arm', 'Hand')) or 'Hand' in gi[e.group]) > 0.3: continue   # 手
    # きっぱり 7cm で分けたら、境目の両側で動きが食い違い、裾に針のようなトゲが出た → 5〜9cm でなめらかに
    d = legdist(p); t = min(1.0, max(0.0, (d - RL0) / (RL1 - RL0))); SF[v.index] = t * t * (3 - 2 * t)
    sk[v.index] = SF[v.index] > 0
print("SF スカートの頂点", int(sk.sum()))
canon = np.zeros(NV, int); key = {}
for v in m.vertices: canon[v.index] = key.setdefault(tuple(np.round(np.array(v.co), 5)), v.index)
nb = {}
for e in m.edges:
    x, y = canon[e.vertices[0]], canon[e.vertices[1]]
    if x != y: nb.setdefault(x, set()).add(y); nb.setdefault(y, set()).add(x)
idx = sorted(set(canon[np.nonzero(sk)[0]].tolist()))
LEG = [g.index for g in me.vertex_groups if g.name.endswith(('UpLeg', 'Leg')) and not g.name.endswith('ToeBase')]
HIPS = next(g.index for g in me.vertex_groups if g.name == 'Hips')
LUP = next(g.index for g in me.vertex_groups if g.name == 'LeftUpLeg'); RUP = next(g.index for g in me.vertex_groups if g.name == 'RightUpLeg')
# スカートの重みは場所だけで決める（頂点ごとに元の重みを削ったら、二重の布の表と裏が別々の重みになって離れ、裾に針のようなトゲが出た）。
#   高さ：ウエスト（股関節 +3cm）で 0、そこから 18cm 下で 1 … ももの骨の割合
#   前後：前側は裾で FRONT、後ろ側は CAP（前はひざに乗って持ち上がる、後ろは跳ね上がらない）
#   左右：x > +3cm は左もも、x < −3cm は右もも、間はなめらかに半分ずつ
#   脚の骨から 5〜9cm で、元の重み（脚の肌）となだらかにつなぐ（SF）
FRONT = float(a[9]) if len(a) > 9 else 0.8
# 前 0.8・左右の切り替え 6cm・高さ 18cm では、ももを上げると裾の前が板のように持ち上がり、真ん中で折れて
# 「角ばって金属っぽい」と言われた（お嬢様 3 回目）。ひざに当たってもよいので、前を下げ、切り替えを広く・なだらかにする
SIDEW = float(a[10]) if len(a) > 10 else 0.06        # 左右のももの切り替えの幅（m）
HGT = float(a[11]) if len(a) > 11 else 0.18          # ウエストから、ももの割合が最大になるまでの高さ（m）
WZ = (arm.matrix_world @ arm.data.bones['LeftUpLeg'].head_local).z + 0.03
def sstep(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
idxset = set(idx); before = []; after = []
for c in idx:
    p = P[c]; before.append(Wt[c, LEG].sum())
    hgt = sstep((WZ - p[2]) / HGT)
    fr = 1.0 - sstep((p[1] - (YC - 0.06)) / 0.09)          # 前 1 → 後ろ 0
    lw = hgt * (CAP + (FRONT - CAP) * fr)
    sl = sstep((p[0] + SIDEW / 2) / SIDEW)                   # 左の割合
    proc = np.zeros(G); proc[HIPS] = 1 - lw; proc[LUP] = lw * sl; proc[RUP] = lw * (1 - sl)
    Wt[c] = (1 - SF[c]) * Wt[c] + SF[c] * proc
    Wt[c] /= max(Wt[c].sum(), 1e-9)
    after.append(Wt[c, LEG].sum())
for v in range(NV):
    if canon[v] != v and canon[v] in idxset: Wt[v] = Wt[canon[v]]
print("SF 脚の重みの平均 %.2f → %.2f（裾で 前 %.2f・後ろ %.2f）" % (np.mean(before), np.mean(after), FRONT, CAP))
for v in m.vertices:
    if not sk[v.index] and canon[v.index] not in idxset: continue
    w = Wt[v.index].copy(); top = np.argsort(-w)[:4]; keep = np.zeros_like(w); keep[top] = w[top]
    keep[keep < 0.01] = 0; keep /= max(keep.sum(), 1e-9)
    for e in list(v.groups): me.vertex_groups[e.group].remove([v.index])
    for g in np.nonzero(keep)[0]: me.vertex_groups[int(g)].add([v.index], float(keep[g]), 'REPLACE')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("SF 書き出し", OUT)
