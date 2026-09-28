# -*- coding: utf-8 -*-
"""スカート専用の骨（SkirtFL・SkirtFR＝前の左右・SkirtB＝後ろ）を足し、スカートの重みをその骨と腰で決める。形・絵はそのまま。
   お嬢様（小学生編）は、スカートを「腰」と「左右のもも」の重みの混ぜ合わせで動かしていた（skirtfix.py）。
   片ひざを上げると、前の割合 0.5〜0.7 ではスカートの前がひざより遅れて突き抜け（「スキップでスカートを突き破るのは違う」）、
   0.8 では左右のももの間で布が折れて角ばった（「角ばって金属っぽい」）。混ぜ合わせではどちらかが出る。
   → 前の骨は、左右のももの「前へ上がっている方」の角度で回す（skirtdrive.py が動きごとに焼き込む）。
     片ひざを上げると前全体がテントのようにひざに乗って上がるので、突き抜けも真ん中の折れも出ない。
   1) 骨：根元は左右の股関節の真ん中、10cm 下向き。親は Hips
   2) スカートの頂点は skirtfix.py と同じ選び方（高さ ZLO〜ZHI・脚の骨から RL0〜RL1 でなめらかに元の重みとつなぐ・髪の先と手を外す）
   3) 重み：高さ（ウエスト＝股関節 +3cm で 0、HGT 下で 1）× 前後（前 1 → 後ろ 0、YC から）で SkirtF と SkirtB、残りは Hips
   前は左右 2 本に分け、真ん中は SIDEW の幅でなめらかに混ぜる
   実行: blender -b --factory-startup -P skirtbones.py -- 入力.glb 出力.glb [ZLO 0.35] [ZHI 0.53] [YC -0.04] [RL0 0.075] [RL1 0.11] [HGT 0.20] [SIDEW 0.15] [FBW 0.18]
   お嬢様: 0.35 0.53 -0.04 0.075 0.11 0.06 0.15 0.18（HGT 0.06：股関節より下は全部骨に付ける。20cm かけて増やしたら、
   スカートの上の方がももに遅れて付け根が突き抜けた）"""
import bpy, sys, colorsys, numpy as np
from mathutils import Vector
from mathutils.geometry import intersect_point_line
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
ZLO = float(a[2]) if len(a) > 2 else 0.35
ZHI = float(a[3]) if len(a) > 3 else 0.53
YC = float(a[4]) if len(a) > 4 else -0.04
RL0 = float(a[5]) if len(a) > 5 else 0.075
RL1 = float(a[6]) if len(a) > 6 else 0.11
HGT = float(a[7]) if len(a) > 7 else 0.20
SIDEW = float(a[8]) if len(a) > 8 else 0.15   # 前の左右の骨の切り替えの幅（m）
FBW = float(a[9]) if len(a) > 9 else 0.18     # 前と後ろの骨の切り替えの幅（m）
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
MWa = arm.matrix_world; MIa = MWa.inverted()
def bh(n): return MWa @ arm.data.bones[n].head_local
# 1) 骨を足す
piv = (bh('LeftUpLeg') + bh('RightUpLeg')) / 2
bpy.context.view_layer.objects.active = arm; arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
# 前は左右 2 本（SkirtFL・SkirtFR）。1 本で前全体を「上がっている方のもも」に合わせたら、片ひざを上げた時に
# 軸足の側まで上がって、スカートの前が大きくめくれた。左右それぞれ自分の側のももに合わせ、真ん中は SIDEW でなめらかに混ぜる
BONES = {'SkirtFL': bh('LeftUpLeg'), 'SkirtFR': bh('RightUpLeg'), 'SkirtB': piv}
for nm, hp in BONES.items():
    if nm in eb: continue
    b = eb.new(nm); b.head = MIa @ hp; b.tail = MIa @ (hp + Vector((0, 0, -0.10))); b.parent = eb['Hips']; b.use_deform = True
bpy.ops.object.mode_set(mode='OBJECT')
for nm in BONES:
    if nm not in me.vertex_groups: me.vertex_groups.new(name=nm)
# 2) スカートの頂点（skirtfix.py と同じ）
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; vuv = {}
for l in m.loops: vuv.setdefault(l.vertex_index, uvl[l.index].uv[:])
NV = len(m.vertices); G = len(me.vertex_groups); gi = {g.index: g.name for g in me.vertex_groups}; gn = {v: k for k, v in gi.items()}
P = np.array([tuple(me.matrix_world @ v.co) for v in m.vertices])
Wt = np.zeros((NV, G))
for v in m.vertices:
    for e in v.groups: Wt[v.index, e.group] = e.weight
key0 = {}; VAL = np.zeros(NV)
for v in m.vertices:
    uv = vuv.get(v.index)
    if uv is None: continue
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    VAL[v.index] = colorsys.rgb_to_hsv(*c)[2]
    k = tuple(np.round(np.array(v.co), 5)); key0[k] = max(key0.get(k, 0.0), VAL[v.index])
for v in m.vertices: VAL[v.index] = key0.get(tuple(np.round(np.array(v.co), 5)), VAL[v.index])
LSEG = [(bh(s + 'UpLeg'), bh(s + 'Leg')) for s in ('Left', 'Right')] + [(bh(s + 'Leg'), bh(s + 'Foot')) for s in ('Left', 'Right')]
def legdist(p):
    pv = Vector(p); best = 9.0
    for h, t in LSEG:
        q, f = intersect_point_line(pv, h, t); f = min(1.0, max(0.0, f)); best = min(best, (pv - (h + (t - h) * f)).length)
    return best
def sstep(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
SF = np.zeros(NV)
for v in m.vertices:
    p = P[v.index]
    if not (ZLO < p[2] < ZHI and abs(p[0]) < 0.30) or v.index not in vuv or VAL[v.index] < 0.35: continue
    if sum(e.weight for e in v.groups if 'Arm' in gi[e.group] or 'Hand' in gi[e.group]) > 0.3: continue
    SF[v.index] = sstep((legdist(p) - RL0) / (RL1 - RL0))
# 3) 重み
HIPS, SKFL, SKFR, SKB = gn['Hips'], gn['SkirtFL'], gn['SkirtFR'], gn['SkirtB']
WZ = bh('LeftUpLeg').z + 0.03
n = 0
for v in m.vertices:
    s = SF[v.index]
    if s <= 0: continue
    p = P[v.index]
    # 前後の切り替えは YC−1.5cm を真ん中に FBW の幅（9cm では、前が上がり後ろが垂れた時に、横で布が板のように折れて立った）
    hgt = sstep((WZ - p[2]) / HGT); fr = 1.0 - sstep((p[1] - (YC - 0.015 - FBW / 2)) / FBW)
    sl = sstep((p[0] + SIDEW / 2) / SIDEW)                       # 左の割合（x > 0 が左）
    proc = np.zeros(G); proc[HIPS] = 1 - hgt; proc[SKFL] = hgt * fr * sl; proc[SKFR] = hgt * fr * (1 - sl); proc[SKB] = hgt * (1 - fr)
    w = (1 - s) * Wt[v.index] + s * proc; w /= max(w.sum(), 1e-9)
    top = np.argsort(-w)[:4]; keep = np.zeros_like(w); keep[top] = w[top]; keep[keep < 0.01] = 0; keep /= keep.sum()
    for e in list(v.groups): me.vertex_groups[e.group].remove([v.index])
    for g in np.nonzero(keep)[0]: me.vertex_groups[int(g)].add([v.index], float(keep[g]), 'REPLACE')
    n += 1
print("SB スカートの頂点 %d を SkirtFL・SkirtFR・SkirtB・Hips へ（左右の切り替え %.0fcm）" % (n, SIDEW * 100))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("SB 書き出し", OUT)
