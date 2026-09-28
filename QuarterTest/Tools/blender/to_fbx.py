# -*- coding: utf-8 -*-
"""GLB を読み込み、アニメを全部載せた FBX として書き出す。
   Unity 純正の FBX 読み込みを使うことで glTFast の変換を通さない。
   実行: blender -b --factory-startup -P to_fbx.py -- 入力.glb 出力.fbx"""
import bpy, sys, os
a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

# 読み込み側が作る内部オブジェクトを消す（FBXに混ぜない）
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
print("ACTIONS", [x.name for x in bpy.data.actions])
print("OBJECTS", [(o.name, o.type) for o in bpy.data.objects])

# 全アクションを書き出す。Unity 側では「ファイル名|アクション名」で入る
bpy.ops.export_scene.fbx(
    filepath=DST,
    use_selection=False,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_NONE',
    object_types={'ARMATURE', 'MESH'},
    use_mesh_modifiers=False,      # アーマチュアの変形を焼き込まない
    add_leaf_bones=False,          # 余計な末端ボーンを作らない
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    bake_anim=True,
    bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,
    bake_anim_use_all_actions=True,
    bake_anim_force_startend_keying=True,
    bake_anim_step=1.0,
    bake_anim_simplify_factor=0.0,
    path_mode='COPY',
    embed_textures=True,
)
print("EXPORTED", DST, os.path.getsize(DST))
