# -*- coding: utf-8 -*-
"""子どもの歩き 2（「足がロボットダンスの歩きみたい」を直した版）。
   ・腰は高め（着いている脚はほぼ伸びる）。一番高いのは片足立ちの真ん中、低いのは両足が着いた時
   ・かかとから着いて（つま先が上）、足の裏を下ろし、終わりにかかとを上げてつま先で蹴る
   ・浮いている足は、前半でひざを大きく曲げて上げ、後半で前へ伸ばす
   ・腰は左右にひねり、浮いた側へ少し下がる。胸は逆へひねる。腕は体の横で前後に振る
   実行: blender -b --factory-startup -P childwalk2.py -- 入力.glb 出力.glb [コマ数 28] [歩幅 28] [足の上がり 6] [腕の振り 20] [腕を寄せる 10]"""
import bpy, sys, math
from mathutils import Vector, Quaternion, Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
NF = int(a[2]) if len(a) > 2 else 28
STRIDE = float(a[3]) if len(a) > 3 else 28.0
LIFT = float(a[4]) if len(a) > 4 else 6.0
ASW = math.radians(float(a[5]) if len(a) > 5 else 20.0)
ADD = math.radians(float(a[6]) if len(a) > 6 else 10.0)
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
for ac in list(bpy.data.actions):
    if ac.name.startswith('Walk_Child'): bpy.data.actions.remove(ac)
for tr in list(arm.animation_data.nla_tracks):
    if tr.name.startswith('Walk_Child'): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
B = arm.data.bones; Rt = {b.name: b.matrix_local.to_quaternion() for b in B}
order = []
def _walk(b):
    order.append(b.name)
    for c in b.children: _walk(c)
for b in B:
    if b.parent is None: _walk(b)
def head(n): return B[n].head_local.copy()
LEN = {}
for s in ('Left', 'Right'):
    LEN[s+'UpLeg'] = (head(s+'Leg') - head(s+'UpLeg')).length
    LEN[s+'Leg'] = (head(s+'Foot') - head(s+'Leg')).length
def frame_rot(d0, p0, d1, p1):
    p0 = (p0 - d0 * p0.dot(d0)).normalized(); p1 = (p1 - d1 * p1.dot(d1)).normalized()
    M0 = Matrix((d0, p0, d0.cross(p0))).transposed(); M1 = Matrix((d1, p1, d1.cross(p1))).transposed()
    return (M1 @ M0.transposed()).to_quaternion()
def ease(x): return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, x)))
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0)); Z = Vector((0, 0, 1)); FWD = Vector((0, -1, 0))
for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
act = bpy.data.actions.new("Walk_Child"); arm.animation_data.action = act
ST = 0.62                                            # 着いている割合
FOOTLEN = (head('LeftToeBase') - head('LeftFoot')).length
for f in range(NF + 1):
    ph = (f % NF) / NF
    # 腰の上下：左の片足立ちの真ん中（ph≈0.31）と右（≈0.81）で高く、両足の時（≈0.06, 0.56）で低い
    bob = 0.9 * math.cos(4 * math.pi * (ph - 0.31)) - 0.9     # 0 〜 -1.8
    yaw = math.radians(6) * math.sin(2 * math.pi * (ph - 0.06))
    roll = math.radians(3) * math.sin(2 * math.pi * (ph - 0.31))  # 浮いた側へ下がる
    Dh = Quaternion(Z, yaw) @ Quaternion(Y, roll)
    dloc = Vector((0, 0, bob - 0.4))
    D = {'Hips': Dh}
    D['Spine02'] = Quaternion(Z, -yaw * 0.5); D['Spine01'] = Quaternion(Z, -yaw * 0.8) @ Quaternion(X, math.radians(-3))
    D['Spine'] = Quaternion(Z, -yaw) @ Quaternion(X, math.radians(-3))
    D['neck'] = Quaternion(X, math.radians(-3)); D['Head'] = Quaternion(X, math.radians(-2))
    Ph = head('Hips') + dloc; fwd = Dh @ FWD
    IK = {}
    for s, off in (('Left', 0.0), ('Right', 0.5)):
        p = (ph + off) % 1.0
        H = Ph + Dh @ (head(s+'UpLeg') - head('Hips'))
        rest_rel = head(s+'Foot') - head(s+'UpLeg')
        if p < ST:
            t = p / ST
            y = -STRIDE / 2 + STRIDE * t; z = 0.0
            # かかとから着く（つま先が上 15度 → 0）、終わりにかかとを上げる（0 → 28度）
            pitch = -math.radians(15) * (1 - ease(t / 0.18)) + math.radians(28) * ease((t - 0.72) / 0.28)
        else:
            t = (p - ST) / (1 - ST)
            y = STRIDE / 2 - STRIDE * ease(t)
            z = LIFT * math.sin(math.pi * min(1.0, t / 0.85)) ** 1.2 if t < 0.85 else 0.0
            pitch = math.radians(28) * (1 - ease(t / 0.45)) - math.radians(15) * ease((t - 0.6) / 0.4)
        # かかとを上げると足首が上がる（つま先を軸に回る）
        ank_up = FOOTLEN * math.sin(max(0.0, pitch)) * 0.9
        F = Vector((H.x + rest_rel.x, head('Hips').y + y + (head(s+'Foot').y - head('Hips').y), head(s+'Foot').z + z + ank_up))
        A, Bl = LEN[s+'UpLeg'], LEN[s+'Leg']
        d = F - H; L = min(d.length, (A + Bl) * 0.998); u = d.normalized()
        ca = max(-1.0, min(1.0, (A*A + L*L - Bl*Bl) / (2*A*L))); sa = (1 - ca*ca) ** 0.5
        pn = (fwd - u * fwd.dot(u)).normalized()
        K = H + u * (A*ca) + pn * (A*sa); F = H + u * L
        for bn, cn, d1 in ((s+'UpLeg', s+'Leg', (K - H).normalized()), (s+'Leg', s+'Foot', (F - K).normalized())):
            d0 = (head(cn) - head(bn)).normalized()
            IK[bn] = frame_rot(d0, FWD, d1, fwd)
        D[s+'Foot'] = Quaternion(Z, yaw) @ Quaternion(X, pitch)          # ＋でかかとが上（つま先が下）
        D[s+'ToeBase'] = Quaternion(Z, yaw) @ Quaternion(X, min(0.0, pitch))
        # 腕：同じ側の脚と逆に振る（脚が前＝かかとが着く p≈0 の時に腕は一番後ろ）。腕は脚より少し遅れる。前へ振る時にひじを少し曲げる
        # 前の版は同じ側の脚と腕が同時に前へ出ていた（「左右の手と足が同じタイミングで出てる」）
        sw = -ASW * math.cos(2 * math.pi * (p - 0.05))
        sg = 1 if s == 'Left' else -1
        D[s+'Shoulder'] = D['Spine']
        D[s+'Arm'] = D['Spine'] @ Quaternion(X, -sw) @ Quaternion(Y, sg * ADD)
        D[s+'ForeArm'] = D[s+'Arm'] @ Quaternion(X, -(math.radians(3) + max(0.0, sw) * 0.35))   # ひじはほぼ伸ばす（12度では「両腕が曲がってる」と言われた）
        D[s+'Hand'] = D[s+'ForeArm']
    W = {}
    for n in order:
        pb = arm.pose.bones[n]; par = B[n].parent
        if n in IK: Wn = IK[n] @ Rt[n]
        elif n in D: Wn = D[n] @ Rt[n]
        else: Wn = (W[par.name] @ Rt[par.name].inverted() @ Rt[n]) if par else Rt[n]
        W[n] = Wn
        Bq = (Rt[n].inverted() @ Rt[par.name] @ W[par.name].inverted() @ Wn) if par else (Rt[n].inverted() @ Wn)
        pb.rotation_quaternion = Bq; pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
        if n == 'Hips':
            pb.location = Rt[n].inverted() @ dloc; pb.keyframe_insert('location', frame=f, group=n)
arm.animation_data.action = None
others = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
for nm, ac, fs in others:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, ac); s2.name = nm
tr = arm.animation_data.nla_tracks.new(); tr.name = "Walk_Child"
st = tr.strips.new("Walk_Child", 0, act); st.name = "Walk_Child"
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("CW2 書き出し", OUT, [t.name for t in arm.animation_data.nla_tracks])
