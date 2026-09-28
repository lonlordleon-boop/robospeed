# -*- coding: utf-8 -*-
"""骨の付け根（関節）の位置だけを直す。形（頂点）と重みはそのまま。動きは外して書き出す（あとで作り直す）。
   お嬢様（小学生編）はワンピースで腰が隠れ、自動の骨入れが腰・股関節・背骨の下を体の中心より約10cm前
   （ふくらんだスカートの前側）に置いた。脚や胴が体の前の何もない所を支点に回ってしまう。
   指定：骨の名前:x,y,z（骨の空間の値。_ はそのまま）。例 Hips:_,-4,_  → 前後だけ −4 に
   実行: blender -b --factory-startup -P jointfix.py -- 入力.glb 出力.glb 骨:x,y,z [骨:x,y,z ...]"""
import bpy, sys
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]; SPEC = a[2:]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
for ac in list(bpy.data.actions): bpy.data.actions.remove(ac)
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.objects.active = arm; arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for s in SPEC:
    name, xyz = s.split(':'); vals = xyz.split(',')
    eb = arm.data.edit_bones[name]; h = eb.head.copy(); old = h.copy()
    for i, v in enumerate(vals):
        if v != '_': h[i] = float(v)
    eb.use_connect = False
    t = eb.tail.copy(); eb.head = h; eb.tail = t + (h - old)     # 向きは変えずに平行に動かす
    print("JF %-12s (%.1f %.1f %.1f) → (%.1f %.1f %.1f)" % (name, old.x, old.y, old.z, h.x, h.y, h.z))
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
print("JF 書き出し", OUT)
