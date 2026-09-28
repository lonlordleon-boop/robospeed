# -*- coding: utf-8 -*-
"""受け側（T字で骨が入ったモデル）の腕の「素の姿勢」を、手本（A字の幼稚園児）の腕の向きにそろえて焼き直す。
   手本の素の姿勢で、肩・上腕・前腕・手の骨の向き（体の空間）を測り、受け側の同じ骨をその向きへ回して、
   メッシュに焼き込み、その姿勢を新しい素の姿勢にする。付いていた動き（Casual_Walk）は外す。
   実行: blender -b --factory-startup -P apose.py -- 受け側.glb 手本.glb 出力.glb [骨,骨,...]"""
import bpy, sys
from mathutils import Matrix, Vector
a = sys.argv[sys.argv.index("--")+1:]
DST, SRC, OUT = a[0], a[1], a[2]
BONES = a[3].split(',') if len(a) > 3 else ['LeftShoulder','LeftArm','LeftForeArm','LeftHand','RightShoulder','RightArm','RightForeArm','RightHand']
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm_s = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
dirs = {}
REF = a[4] if len(a) > 4 else ''
if REF:
    # 手本のクリップ REF の最初のコマの姿勢で向きを測る（素の姿勢がかがんでいる手本のため）
    act = next(x for x in bpy.data.actions if x.name == REF or x.name.startswith(REF))
    if arm_s.animation_data is None: arm_s.animation_data_create()
    for tr in list(arm_s.animation_data.nla_tracks): arm_s.animation_data.nla_tracks.remove(tr)
    arm_s.animation_data.action = act
    bpy.context.scene.frame_set(int(act.frame_range[0])); bpy.context.view_layer.update()
    for n in BONES:
        pb = arm_s.pose.bones[n]; dirs[n] = (pb.tail - pb.head).normalized()
else:
    for n in BONES:
        b = arm_s.data.bones[n]; dirs[n] = (b.tail_local - b.head_local).normalized()
print("AP 手本の向き", {n: tuple(round(x,3) for x in d) for n, d in dirs.items()})
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=DST)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
if arm.animation_data: arm.animation_data.action = None
for ac in list(bpy.data.actions): bpy.data.actions.remove(ac)
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
# 左右対称にする：上腕は手本の左と右（鏡）の平均。前腕・手首は左の今の向き。右はすべて左の鏡写し
from mathutils import Vector
def mir(v): return Vector((-v.x, v.y, v.z))
if 'LeftArm' in dirs and 'RightArm' in dirs:
    avg = (dirs['LeftArm'] + mir(dirs['RightArm'])).normalized()
    # 手本の平均は後ろへ16度傾いていて「待機、腕を後ろにしてるのが変」と言われた → 前後の傾きを 0 にする
    avg = Vector((avg.x, 0.0, avg.z)).normalized()
    dirs['LeftArm'] = avg; dirs['RightArm'] = mir(avg)
    print("AP 上腕の向き（左右そろえた）", tuple(round(x, 3) for x in avg))
SYMCHAIN = ['LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm', 'LeftHand', 'RightHand']
for n in SYMCHAIN:
    pb = arm.pose.bones[n]
    if n.startswith('Left'):
        if n == 'LeftForeArm':
            # 前腕は上腕とまっすぐにそろえる（生成のままだと約10度曲がっていて「両腕が曲がってるのが気になる」と言われた）
            dirs[n] = dirs['LeftArm'].copy()
        elif n not in dirs: dirs[n] = (pb.tail - pb.head).normalized()
    else:
        L = arm.pose.bones['Left' + n[5:]]
        dirs[n] = mir((L.tail - L.head).normalized())
    cur = (pb.tail - pb.head).normalized()
    q = cur.rotation_difference(dirs[n])
    h = pb.head.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()
    print("AP %s 回した角度 %.1f 度" % (n, q.angle * 57.2958))
for n in []:
    pb = arm.pose.bones[n]
    cur = (pb.tail - pb.head).normalized()
    q = cur.rotation_difference(dirs[n])
    h = pb.head.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()
    print("AP %s 回した角度 %.1f 度" % (n, q.angle * 57.2958))
# メッシュに焼き込んで、その姿勢を素の姿勢にする
bpy.context.view_layer.objects.active = me
for o in bpy.context.selected_objects: o.select_set(False)
me.select_set(True)
mod = next(m for m in me.modifiers if m.type == 'ARMATURE')
name = mod.name
with bpy.context.temp_override(object=me, active_object=me):
    bpy.ops.object.modifier_apply(modifier=name)
nm = me.modifiers.new("Armature", 'ARMATURE'); nm.object = arm
bpy.context.view_layer.objects.active = arm; arm.select_set(True)
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
print("AP 書き出し", OUT)
