# クリップごとに、各コマの一番低い頂点の高さ（cm）を出す（地面は 0）
import bpy, sys, numpy as np
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
for act in bpy.data.actions:
    arm.animation_data.action = act; f0, f1 = map(int, act.frame_range); zs = []
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
        zs.append(min((me.matrix_world @ v.co).z for v in em.vertices) * 100); me.evaluated_get(dg).to_mesh_clear()
    print("FL %-10s 一番低い %.1f〜%.1f cm  コマごと %s" % (act.name, min(zs), max(zs), " ".join("%.1f" % z for z in zs)))
