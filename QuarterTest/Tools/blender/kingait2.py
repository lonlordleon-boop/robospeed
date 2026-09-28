# -*- coding: utf-8 -*-
"""幼稚園児（手本）の走り・スキップを、小学生のモデルへ骨の向きで写す。
   手作りの走りは「歩きを速めてるだけ」、スキップは「ロボットダンス」と言われた。測ると、手本より
   前傾・ももの上げ・蹴り上げ・腕の振りがどれもずっと小さかった → 手本の動きそのものを写す。
   ・手足：手本の骨の向き（真横から見た前後の角度）を写す。脚は左右の開きを自分の素の姿勢のままにする（内股にしない）
   ・腕：前後の角度と、横への開き（手本の値、ただし自分の素の開き以上）を写す
   ・胴・首・頭・腰：手本の Idle 最初のコマからの回り方（差分）を写す（手本の素の姿勢はかがんでいるため）
   ・左右：左と「右を半周期ずらして鏡写しにしたもの」の平均で左を作り、右はその鏡写し（手本の左右差は写さない）
   ・腰の高さ：低い方の足首の高さを、手本の（地面からの高さ÷脚の長さ）に合わせる（浮く時間もそのまま）
   実行: blender -b --factory-startup -P kingait.py -- 入力.glb 手本.glb 出力.glb クリップ名 手本の始めコマ 終わりコマ コマ数"""
import bpy, sys, math
from mathutils import Vector, Quaternion, Matrix
a = sys.argv[sys.argv.index("--")+1:]
DST, KIN, OUT, CLIP = a[0], a[1], a[2], a[3]
KF0, KF1, NF = float(a[4]), float(a[5]), int(a[6])
SUB = 4                                   # 平均のため手本を細かく測る
LIMBS = ['UpLeg', 'Leg', 'Foot', 'ToeBase', 'Arm', 'ForeArm', 'Hand']
TRUNK = ['Hips', 'Spine02', 'Spine01', 'Spine', 'neck', 'Head']
CHILD = {'UpLeg': 'Leg', 'Leg': 'Foot', 'Foot': 'ToeBase', 'Arm': 'ForeArm', 'ForeArm': 'Hand'}
def mirv(v): return Vector((-v.x, v.y, v.z))
def mirq(q): return Quaternion((q.w, q.x, -q.y, -q.z))

# ---- 手本を測る ----
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=KIN)
ka = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for tr in list(ka.animation_data.nla_tracks): ka.animation_data.nla_tracks.remove(tr)
sc = bpy.context.scene
def kpose(name, fr):
    ka.animation_data.action = next(x for x in bpy.data.actions if x.name == name)
    sc.frame_set(int(fr), subframe=fr - int(fr)); bpy.context.view_layer.update()
def bdir(pbs, s, n):
    pb = pbs[s + n]
    if n in CHILD: return (pbs[s + CHILD[n]].head - pb.head).normalized()
    return (pb.tail - pb.head).normalized()
kpose('Idle', 0)
KP = ka.pose.bones
K0 = {n: KP[n].matrix.to_quaternion() for n in TRUNK}
K0hip = KP['Hips'].head.copy()
KLEG = ((KP['LeftLeg'].head - KP['LeftUpLeg'].head).length + (KP['LeftFoot'].head - KP['LeftLeg'].head).length)
KGROUND = min(KP['LeftFoot'].head.z, KP['RightFoot'].head.z)
KMESH = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')]
KSC = ka.matrix_world.to_scale().z
def mesh_low(objs):
    dg = bpy.context.evaluated_depsgraph_get(); lo = 1e9
    for o in objs:
        em = o.evaluated_get(dg).to_mesh(); lo = min(lo, min((o.matrix_world @ v.co).z for v in em.vertices)); o.evaluated_get(dg).to_mesh_clear()
    return lo
M = NF * SUB
kd = []
for i in range(M):
    fr = KF0 + (KF1 - KF0) * i / M
    kpose(CLIP, fr)
    lv = KP['neck'].head - KP['Hips'].head
    r = {'dq': {n: KP[n].matrix.to_quaternion() @ K0[n].inverted() for n in TRUNK},
         'hip': KP['Hips'].head - K0hip, 'lean': math.atan2(-lv.y, lv.z),
         'g': mesh_low(KMESH) / (KLEG * KSC)}   # 一番低い頂点（靴底）の高さ ÷ 脚の長さ。足首の骨で合わせると 2.5cm 以上浮いた
    for s in ('Left', 'Right'):
        for n in LIMBS: r[s + n] = bdir(KP, s, n)
    kd.append(r)
# 左右をそろえる（左 = 左と、半周期先の右の鏡写しの平均）
H = M // 2
sym = []
for i in range(M):
    r, o = kd[i], kd[(i + H) % M]
    s = {'g': min(r['g'], o['g']),   # 低い方（平均すると、手本の左右の着地のずれで着地がぼやけて浮いた）
         'lean': 0.5 * (r['lean'] + o['lean']),
         'hip': Vector((0.0, 0.5 * (r['hip'].y + o['hip'].y), 0.5 * (r['hip'].z + o['hip'].z))),
         'dq': {n: r['dq'][n].slerp(mirq(o['dq'][n]), 0.5) for n in TRUNK}}
    for n in LIMBS: s['Left' + n] = (r['Left' + n] + mirv(o['Right' + n])).normalized()
    sym.append(s)
for i in range(M):
    sym[i]['R'] = {n: mirv(sym[(i + H) % M]['Left' + n]) for n in LIMBS}
    sym[i]['L'] = {n: sym[i]['Left' + n] for n in LIMBS}
# 着地（一番低い時）が書き出すコマの上に来るよう、始まりをずらす
i0 = min(range(M), key=lambda i: sym[i]['g']); sh = i0 % SUB
sym = sym[sh:] + sym[:sh]
print("KG 着地に合わせてずらした", sh, "/", SUB)
print("KG 手本を測った", CLIP, KF0, KF1, "脚の長さ", round(KLEG, 2))

# ---- 受け側に動きを作る ----
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=DST)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks):
    if tr.name.startswith(CLIP): arm.animation_data.nla_tracks.remove(tr)
for ac in list(bpy.data.actions):
    if ac.name.startswith(CLIP) and ac.users == 0: bpy.data.actions.remove(ac)
arm.animation_data.action = None
B = arm.data.bones; Rt = {b.name: b.matrix_local.to_quaternion() for b in B}
order = []
def _walk(b):
    order.append(b.name)
    for c in b.children: _walk(c)
for b in B:
    if b.parent is None: _walk(b)
def head(n): return B[n].head_local.copy()
def rdir(s, n):
    if n in CHILD: return (head(s + CHILD[n]) - head(s + n)).normalized()
    b = B[s + n]; return (b.tail_local - b.head_local).normalized()
MLEG = (head('LeftLeg') - head('LeftUpLeg')).length + (head('LeftFoot') - head('LeftLeg')).length
MGROUND = min(head('LeftFoot').z, head('RightFoot').z)
MMESH = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')]
MSC = arm.matrix_world.to_scale().z
RATIO = MLEG / KLEG
X = Vector((1, 0, 0))
def frame_rot(d0, p0, d1, p1):
    p0 = (p0 - d0 * p0.dot(d0)).normalized(); p1 = (p1 - d1 * p1.dot(d1)).normalized()
    M0 = Matrix((d0, p0, d0.cross(p0))).transposed(); M1 = Matrix((d1, p1, d1.cross(p1))).transposed()
    return (M1 @ M0.transposed()).to_quaternion()
def target(s, n, kdir):
    """手本の向き kdir から、受け側で使う向きを作る"""
    r0 = rdir(s, n)
    if n in ('UpLeg', 'Leg', 'Foot', 'ToeBase'):
        # 前後の角度だけ写す。左右の開きは自分の素の姿勢のまま
        yz = Vector((0, kdir.y, kdir.z))
        if yz.length < 1e-6: return r0
        c = (1 - r0.x * r0.x) ** 0.5
        yz = yz.normalized() * c
        return Vector((r0.x, yz.y, yz.z)).normalized()
    if n == 'Arm':
        # 横への開きは、手本と自分の素の開きの大きい方（体に腕がめり込まないように）
        sg = 1 if s == 'Left' else -1
        ax = max(kdir.x * sg, r0.x * sg) * sg
        yz = Vector((0, kdir.y, kdir.z))
        c = (max(0.0, 1 - ax * ax)) ** 0.5
        yz = yz.normalized() * c if yz.length > 1e-6 else Vector((0, 0, -c))
        return Vector((ax, yz.y, yz.z)).normalized()
    return kdir
for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
act = bpy.data.actions.new(CLIP); arm.animation_data.action = act
LEANED = ['Hips', 'Spine02', 'Spine01', 'Spine', 'neck', 'Head']   # 骨盤ごと傾ける（胴から上だけだと、おなかで折れて上着が裂けた）
def set_pose(f, s, corr):
    D = {n: s['dq'][n] for n in TRUNK}
    # 上体の傾き：差分だけだと手本の Idle が前かがみな分だけ足りない（走り 41度・スキップは後ろへ反った）
    # → 腰から首への角度が手本と同じになるよう、胴から上をまとめて前後に回す
    for n in LEANED: D[n] = Quaternion(X, corr) @ D[n]
    for sd in ('Left', 'Right'):
        D[sd + 'Shoulder'] = D['Spine']
    W = {}
    for n in order:
        pb = arm.pose.bones[n]; par = B[n].parent
        side = 'Left' if n.startswith('Left') else ('Right' if n.startswith('Right') else None)
        base = n[len(side):] if side else None
        # 手は写さず前腕にまっすぐ付けたまま（このモデルの手の骨は前腕から55度ずれて付いていて、手本の向きに合わせると手首が約40度折れた）
        # 足先（ToeBase）も写さず足に付けたまま（お嬢様のメリージェーンは、足先だけ下へ折れてつま先がくちばしのように伸びた）
        if side and base in LIMBS and base not in ('Hand', 'ToeBase'):
            kdir = s['L' if side == 'Left' else 'R'][base]
            d1 = target(side, base, kdir)
            pole_q = D['Hips'] if base in ('UpLeg', 'Leg', 'Foot', 'ToeBase') else D['Spine']
            q = frame_rot(rdir(side, base), X, d1, pole_q @ X)
            Wn = q @ Rt[n]
        elif n in D: Wn = D[n] @ Rt[n]
        else: Wn = (W[par.name] @ Rt[par.name].inverted() @ Rt[n]) if par else Rt[n]
        W[n] = Wn
        pb.rotation_quaternion = (Rt[n].inverted() @ Rt[par.name] @ W[par.name].inverted() @ Wn) if par else (Rt[n].inverted() @ Wn)
        if f is not None: pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
def my_lean():
    bpy.context.view_layer.update(); P = arm.pose.bones
    lv = P['neck'].head - P['Hips'].head
    return math.atan2(-lv.y, lv.z)
LE = []
for f in range(NF + 1):
    s = sym[(f % NF) * SUB]
    arm.animation_data.action = None          # 測る間は動きを外す（付けたままだと更新で上書きされる）
    arm.pose.bones['Hips'].location = Vector((0, 0, 0))
    corr = 0.0
    for it in range(4):
        set_pose(None, s, corr); corr += s['lean'] - my_lean()
    set_pose(None, s, corr)
    LE.append((round(math.degrees(s['lean']), 1), round(math.degrees(my_lean()), 1)))
    arm.animation_data.action = act; set_pose(f, s, corr); arm.animation_data.action = None
    # 腰の高さ：低い方の足首を、手本の地面からの高さ（脚の長さ比）へ
    hp = arm.pose.bones['Hips']; hp.location = Vector((0, 0, 0)); bpy.context.view_layer.update()
    low = mesh_low(MMESH) / MSC          # 骨の空間の単位へ
    want = s['g'] * MLEG
    dloc = Vector((0, s['hip'].y * RATIO, want - low))
    hp.location = Rt['Hips'].inverted() @ dloc; arm.animation_data.action = act; hp.keyframe_insert('location', frame=f, group='Hips')
arm.animation_data.action = None
others = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
want_order = ['Idle', 'Walk_Child', 'Run', 'Skip']
others.append((CLIP, act, 0))
others.sort(key=lambda t: want_order.index(t[0]) if t[0] in want_order else 99)
for nm, ac, fs in others:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, ac); s2.name = nm
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("KG 傾き（手本, 自分）", LE)
print("KG 書き出し", OUT, [t.name for t in arm.animation_data.nla_tracks], "比", round(RATIO, 3))
