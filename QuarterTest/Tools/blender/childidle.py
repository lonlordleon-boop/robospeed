# -*- coding: utf-8 -*-
"""左右対称の待機（息に合わせた胸の上下と、肩・腕・頭のわずかな揺れ）を作り、Idle として入れ替える。
   幼稚園児の待機は体重を片足に乗せて体を傾けるので、左右の腕の開きが違って見えた。
   実行: blender -b --factory-startup -P childidle.py -- 入力.glb 出力.glb [コマ数 72]"""
import bpy, sys, math
from mathutils import Quaternion, Matrix, Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]; NF = int(a[2]) if len(a) > 2 else 72
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
# 古い Idle を外し、ほかのクリップは NLA に残す
keep = []
for ac in list(bpy.data.actions):
    if ac.name.startswith('Idle'): bpy.data.actions.remove(ac)
for tr in list(arm.animation_data.nla_tracks):
    if tr.name.startswith('Idle'): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
B = arm.data.bones; Rt = {b.name: b.matrix_local.to_quaternion() for b in B}
order = []
def _walk(b):
    order.append(b.name)
    for c in b.children: _walk(c)
for b in B:
    if b.parent is None: _walk(b)
for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
act = bpy.data.actions.new("Idle"); arm.animation_data.action = act
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))
for f in range(NF + 1):
    t = 2 * math.pi * (f % NF) / NF
    br = math.sin(t)                          # 息
    D = {}
    D['Spine01'] = Quaternion(X, math.radians(-1.2) * br)
    D['Spine02'] = Quaternion(X, math.radians(-2.0) * br)
    D['Spine'] = D['Spine02']
    D['neck'] = Quaternion(X, math.radians(-2.0) * br)
    D['Head'] = Quaternion(X, math.radians(1.5) * math.sin(t + 0.6))
    for s, sg in (('Left', 1), ('Right', -1)):
        D[s+'Shoulder'] = D['Spine02'] @ Quaternion(Y, sg * math.radians(1.5) * br)
        D[s+'Arm'] = D[s+'Shoulder'] @ Quaternion(X, math.radians(-2.0) * math.sin(t + 0.4)) @ Quaternion(Y, sg * math.radians(2))   # 腕を体へ2度寄せる（12度では閉じすぎで「+10度くらい必要」と言われた）
    W = {}
    for n in order:
        pb = arm.pose.bones[n]; par = B[n].parent
        if n in D: Wn = D[n] @ Rt[n]
        else: Wn = (W[par.name] @ Rt[par.name].inverted() @ Rt[n]) if par else Rt[n]
        W[n] = Wn
        Bq = (Rt[n].inverted() @ Rt[par.name] @ W[par.name].inverted() @ Wn) if par else (Rt[n].inverted() @ Wn)
        pb.rotation_quaternion = Bq; pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
        if n == 'Hips':
            pb.location = Rt[n].inverted() @ Vector((0, 0, 0.25 * br)); pb.keyframe_insert('location', frame=f, group=n)
arm.animation_data.action = None
# 待機を先頭にする（preview は最初のクリップを流す）。ほかのトラックを外して、待機のあとに入れ直す
others = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
tr = arm.animation_data.nla_tracks.new(); tr.name = "Idle"
st = tr.strips.new("Idle", 0, act); st.name = "Idle"
for nm, ac, fs in others:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm
    s2 = t2.strips.new(nm, fs, ac); s2.name = nm
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("CI 書き出し", OUT, [t.name for t in arm.animation_data.nla_tracks])
