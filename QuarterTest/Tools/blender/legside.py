# -*- coding: utf-8 -*-
"""すねから下（Leg・Foot・ToeBase）が主な頂点から、反対側の脚の骨の重みを外す。形と骨はそのまま、動きも残す。
   お嬢様（小学生編）は T字で骨を入れた時につま先どうしが近く、右の靴に左足先・左足の重みが混じっていた
   （右足の頂点 1043 のうち 170、左足 970 のうち 126）。走って足が離れると靴がくちばしのように伸びた。
   実行: blender -b --factory-startup -P legside.py -- 入力.glb 出力.glb"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
gi = {g.index: g.name for g in me.vertex_groups}
LOW = ('Leg', 'Foot', 'ToeBase')
CHAIN = ('UpLeg', 'Leg', 'Foot', 'ToeBase', 'Toe_End')
n = 0
for v in me.data.vertices:
    if not v.groups: continue
    top = max(v.groups, key=lambda e: e.weight); tn = gi[top.group]
    side = 'Left' if tn.startswith('Left') else ('Right' if tn.startswith('Right') else None)
    if side is None or tn[len(side):] not in LOW: continue
    other = 'Right' if side == 'Left' else 'Left'
    rm = [e.group for e in v.groups if gi[e.group].startswith(other) and gi[e.group][len(other):] in CHAIN]
    if not rm: continue
    for g in rm: me.vertex_groups[g].remove([v.index])
    tot = sum(e.weight for e in v.groups)
    for e in v.groups: e.weight = e.weight / tot
    n += 1
print("LS2 反対側の脚の重みを外した頂点", n)
if arm.animation_data and arm.animation_data.nla_tracks:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
else:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
print("LS2 書き出し", OUT)
