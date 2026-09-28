# -*- coding: utf-8 -*-
"""別のモデルのアニメを、骨の向きの違いを直しながらこちらの骨へ移す。

   animgraft.py は「素の姿勢からの回転の差」をそのまま貼り替える。骨の向き（ねじれ）が同じモデル同士なら
   それで合うが、生成のたびに骨の向きの取り方が変わることがある。
   作り直したお嬢様は腰の骨の向きが v55 と大きく違い（glTF の腰の回転 約24度 と 約134度）、
   同じ差を貼ると違う向きに回って、待機でも体がねじれて傾き、片足が浮いた。

   ここでは、出し側の「素の姿勢からの差」を体全体（Armature）の空間の回転に直し、
   受け側の骨の素の向きで戻してから貼る。
       差(体の空間) = 出し側の素の向き × 出し側の差 × 出し側の素の向きの逆
       受け側の差   = 受け側の素の向きの逆 × 差(体の空間) × 受け側の素の向き
   骨の向きが同じなら animgraft.py と同じ結果になる。
   腰の移動も同じように体の空間へ直し、腰の高さの比で縮める。

   コマは出し側のキーのある範囲を1コマずつ焼く。床合わせ（liftdip.py）は、このあとで掛けること。

   実行: blender -b --factory-startup -P animretarget.py -- 受け側.glb 出し側.glb 出力.glb クリップ名1,クリップ名2,...
"""
import bpy, sys
from mathutils import Matrix, Quaternion, Vector

a = sys.argv[sys.argv.index("--")+1:]
DST, SRC, OUT = a[0], a[1], a[2]
NAMES = a[3].split(',')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=DST)
before = set(bpy.data.objects)
arm_t = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
acts_before = set(bpy.data.actions)
bpy.ops.import_scene.gltf(filepath=SRC)
added = [o for o in bpy.data.objects if o not in before]
arm_s = next(o for o in added if o.type == 'ARMATURE')
acts_src = [x for x in bpy.data.actions if x not in acts_before]
# 出し側のメッシュは要らない（骨だけ使う）
for o in added:
    if o.type == 'MESH': bpy.data.objects.remove(o, do_unlink=True)

# 受け側がもともと持っていたクリップは捨てる
if arm_t.animation_data is None: arm_t.animation_data_create()
for tr in list(arm_t.animation_data.nla_tracks): arm_t.animation_data.nla_tracks.remove(tr)
arm_t.animation_data.action = None
if arm_s.animation_data is None: arm_s.animation_data_create()
for tr in list(arm_s.animation_data.nla_tracks): arm_s.animation_data.nla_tracks.remove(tr)

common = [b.name for b in arm_t.data.bones if b.name in arm_s.data.bones]
print("RT 共通の骨 %d 本" % len(common))
Rs = {n: arm_s.data.bones[n].matrix_local.to_quaternion() for n in common}
Rt = {n: arm_t.data.bones[n].matrix_local.to_quaternion() for n in common}
for n in ('Hips', 'Spine', 'Head', 'LeftArm', 'LeftUpLeg'):
    if n in Rs:
        d = Rs[n].rotation_difference(Rt[n])
        print("RT %-10s 素の向きの違い %.1f度" % (n, d.angle * 57.2958))
# 腰の高さの比（移動を縮める）
hs = arm_s.data.bones['Hips'].head_local.length or 1.0
ht = arm_t.data.bones['Hips'].head_local.length or 1.0
SCALE = ht / hs
print("RT 腰の高さ 出し側 %.3f 受け側 %.3f 比 %.3f" % (hs, ht, SCALE))

for pb in arm_t.pose.bones: pb.rotation_mode = 'QUATERNION'
sc = bpy.context.scene
for name in NAMES:
    act_s = next((x for x in acts_src if x.name == name), None) or next((x for x in acts_src if x.name.startswith(name)), None)
    if act_s is None:
        print("RT 見つからない", name); continue
    arm_s.animation_data.action = act_s
    f0, f1 = int(round(act_s.frame_range[0])), int(round(act_s.frame_range[1]))
    act_t = bpy.data.actions.new(name)
    arm_t.animation_data.action = act_t
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for n in common:
            ps = arm_s.pose.bones[n]; pt = arm_t.pose.bones[n]
            B = ps.matrix_basis
            qd = Rs[n] @ B.to_quaternion() @ Rs[n].inverted()
            pt.rotation_quaternion = Rt[n].inverted() @ qd @ Rt[n]
            pt.keyframe_insert('rotation_quaternion', frame=f, group=n)
            if n == 'Hips':
                vd = Rs[n] @ B.to_translation()
                pt.location = (Rt[n].inverted() @ vd) * SCALE
                pt.keyframe_insert('location', frame=f, group=n)
    arm_t.animation_data.action = None
    tr = arm_t.animation_data.nla_tracks.new(); tr.name = name
    st = tr.strips.new(name, f0, act_t); st.name = name
    print("RT %s: %d〜%d コマを焼いた" % (name, f0, f1))

bpy.data.objects.remove(arm_s, do_unlink=True)
for pb in arm_t.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=True, export_yup=True, use_selection=False)
print("RT 書き出し", OUT)
