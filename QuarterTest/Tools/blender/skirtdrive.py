# -*- coding: utf-8 -*-
"""スカートの骨（skirtbones.py が足した SkirtFL・SkirtFR・SkirtB）の回転を、すべての動きのコマごとに焼き込む。形・重み・絵はそのまま。
   前の骨 SkirtFL・SkirtFR：世界で「真下」と「自分の側のももの前へ上がった角度 × KF」のうち前の方を向く
   後ろの骨 SkirtB：世界で「真下」と「左右のももの後ろへ振っている方 × KB」のうち後ろの方を向く
   角度は、ももの骨の向きを、体の横の軸まわり（前後の面）で、素の姿勢と比べて世界で測る。骨は腰の子なので腰の傾きの分を引いて回す。
   回す軸も体の横の軸（左右の股関節を通る線）。片ひざを上げると、前全体がテントのようにひざに乗って上がる。
   動きの骨（腕や脚）は変えない。これより後に swaptex.py・animzero.py をかけてよい
   ももが裾の MARGIN（2cm）手前まで来てから回す（素の姿勢で裾とももの面の角度の差を測る）
   実行: blender -b --factory-startup -P skirtdrive.py -- 入力.glb 出力.glb [KF 1.0] [KB 0.5] [MARGIN 0.02]"""
import bpy, sys, math
from mathutils import Vector, Matrix, Quaternion
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
KF = float(a[2]) if len(a) > 2 else 1.0
KB = float(a[3]) if len(a) > 3 else 0.5
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
tracks = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
A3 = arm.matrix_world.to_3x3().normalized().inverted()
FWD = (A3 @ Vector((0, -1, 0))).normalized(); SIDE = (A3 @ Vector((1, 0, 0))).normalized(); DOWN = (A3 @ Vector((0, 0, -1))).normalized()
B = arm.data.bones; PB = arm.pose.bones
HR = B['Hips'].matrix_local
def legdir_rest(s): return (B[s + 'Leg'].head_local - B[s + 'UpLeg'].head_local)
def proj(v): return (v - SIDE * v.dot(SIDE)).normalized()
# 角度は世界の真下から測る。腰から測ったら、走りは体ごと前へ 56 度傾いているので、脚が真下でも 55 度・最大 152 度になり、
# スカートの前がお腹の上までめくれた。スカートは重さで垂れるので、前の骨は「真下」と「前へ上がっている方のもも」のうち前の方へ向ける
def fwd_angle(v, ref):
    """ref から v への、体の横の軸まわりの角度（v が前へ出る向きが正、ラジアン）"""
    p, p0 = proj(v), proj(ref)
    ang = math.atan2(p0.cross(p).dot(SIDE), p0.dot(p))
    fs = 1.0 if ((Quaternion(SIDE, 0.1) @ p0) - p0).dot(FWD) > 0 else -1.0
    return ang * fs
def lift(s):
    """もも（素の姿勢の向きを 0 とする）の、世界での前後の角度（前が正）"""
    return fwd_angle(PB[s + 'Leg'].head - PB[s + 'UpLeg'].head, legdir_rest(s))
def hips_pitch():
    """腰が素の姿勢から前後に回った分（腰につく下向きのものが前へ出る向きが正）"""
    rel = (PB['Hips'].matrix @ HR.inverted()).to_3x3()
    return fwd_angle(rel @ DOWN, DOWN)
# 体の横の軸まわりで、下向きの骨の先が前へ出る向きの符号を決める
sgn = 1.0 if (Quaternion(SIDE, 0.1) @ DOWN).dot(FWD) > 0 else -1.0
def drive(name, ang):
    pb = PB[name]; bone = B[name]; h = bone.head_local
    q = Quaternion(SIDE, sgn * ang).to_matrix().to_4x4()
    rot = Matrix.Translation(h) @ q @ Matrix.Translation(-h)
    pb.matrix = PB['Hips'].matrix @ HR.inverted() @ rot @ bone.matrix_local
# スカートは広がっているので、ももと同じ角度だけ回すと裾がももから大きく離れて「必要以上に上がり過ぎ」た。
# 素の姿勢で「裾（ももの前）」と「ももの前の面」の角度の差を測り、ももが裾の MARGIN 手前まで来てから回す（すき間 2cm を保つ）
MARGIN = float(a[4]) if len(a) > 4 else 0.02
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); mm = me.data
mgi = {g.index: g.name for g in me.vertex_groups}
VP = [me.matrix_world @ v.co for v in mm.vertices]
def wsum(v, names): return sum(e.weight for e in v.groups if mgi[e.group] in names)
def gap(s, front):
    piv = arm.matrix_world @ B[s + 'UpLeg'].head_local
    bone = ('SkirtFL' if s == 'Left' else 'SkirtFR') if front else 'SkirtB'
    sg = 1 if front else -1
    hem = []
    for v in mm.vertices:
        p = VP[v.index]
        if wsum(v, (bone,)) < 0.6 or abs(p.x - piv.x) > 0.04: continue
        if (front and p.y > piv.y - 0.02) or (not front and p.y < piv.y + 0.02): continue
        hem.append(p)
    if not hem: return 0.0, 0.0
    zmin = min(p.z for p in hem); hem = [p for p in hem if p.z < zmin + 0.02]
    ang = sorted(sg * fwd_angle(A3 @ (p - piv), DOWN) for p in hem); rr = sorted((p - piv).length for p in hem)
    th_s, r_h = ang[len(ang) // 2], rr[len(rr) // 2]
    th_t = -9.0
    for v in mm.vertices:
        p = VP[v.index]
        if wsum(v, (s + 'UpLeg', s + 'Leg')) < 0.9 or abs(p.x - piv.x) > 0.045 or abs((p - piv).length - r_h) > 0.03: continue
        th_t = max(th_t, sg * fwd_angle(A3 @ (p - piv), DOWN))
    g = th_s - th_t - math.atan(MARGIN / r_h)
    print("SD %s %s：裾 %.0f 度・ももの面 %.0f 度・半径 %.0fcm → ももが %.0f 度 来てから回す" % (s, '前' if front else '後ろ', math.degrees(sg * th_s), math.degrees(sg * th_t), r_h * 100, math.degrees(g)))
    return max(g, 0.0), r_h
GF = {s: gap(s, True)[0] for s in ('Left', 'Right')}
GB = {s: gap(s, False)[0] for s in ('Left', 'Right')}
SK = ('SkirtFL', 'SkirtFR', 'SkirtB')
for nm, act, fs in tracks:
    arm.animation_data.action = act
    if hasattr(arm.animation_data, 'action_slot') and arm.animation_data.action_slot is None and len(act.slots):
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = map(int, act.frame_range); mx = 0; mn = 0
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        for s in SK: PB[s].matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        la, lb = lift('Left'), lift('Right'); hpt = hips_pitch()
        # 世界での向き（0 = 真下に垂れる）。前の左右はそれぞれ自分の側のもも、後ろは後ろへ振っている方
        fl = max(la - GF['Left'], 0.0) * KF; fr_ = max(lb - GF['Right'], 0.0) * KF
        ba = min(la + GB['Left'], lb + GB['Right'], 0.0) * KB
        mx = max(mx, fl, fr_); mn = min(mn, ba)
        # 骨は腰の子なので腰の分を引く。後ろは腰から見て後ろへだけ回す（走りは体ごと前へ 56 度傾くので、真下へ垂らすと
        # 腰から見て前へ 56 度回り、スカートの後ろがお尻の中へ入った）
        drive('SkirtFL', fl - hpt); drive('SkirtFR', fr_ - hpt); drive('SkirtB', min(ba - hpt, 0.0))
        bpy.context.view_layer.update()
        for s in SK:
            PB[s].rotation_mode = 'QUATERNION'
            PB[s].keyframe_insert('rotation_quaternion', frame=f); PB[s].keyframe_insert('location', frame=f)
    print("SD %-10s %d〜%d コマ  前の骨 最大 %.0f 度・後ろの骨 最大 %.0f 度" % (nm, f0, f1, math.degrees(mx), math.degrees(mn)))
arm.animation_data.action = None
for pb in PB: pb.matrix_basis = Matrix.Identity(4)
want = ['Idle', 'Walk_Child', 'Run', 'Skip']
tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
for nm, act, fs in tracks:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, act); s2.name = nm
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("SD 書き出し", OUT)
