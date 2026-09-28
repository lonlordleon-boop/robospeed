# -*- coding: utf-8 -*-
"""動き（クリップ）のコマを 0 コマ目から始まるようにずらして書き出す。形・骨・重み・絵はそのまま。
   glb を Blender に読み込み直すと動きは 1 コマ目から始まり、そのまま書き出すと 0 コマ目（1 コマ目と同じ姿勢）が
   1 つ余分に入って、ループのたびに 1 コマ止まった（走り 12 コマが 0.54 秒になっていた。本当は 0.50 秒）。
   クリップの並びは Idle・Walk_Child・Run・Skip にそろえる。
   実行: blender -b --factory-startup -P animzero.py -- 入力.glb 出力.glb"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
tracks = [(t.name, t.strips[0].action) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
def fcurves(act):
    if hasattr(act, 'fcurves') and len(act.fcurves): return list(act.fcurves)
    out = []
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in strip.channelbags: out += list(cb.fcurves)
    return out
for nm, act in tracks:
    f0 = act.frame_range[0]
    if abs(f0) > 1e-6:
        for fc in fcurves(act):
            for k in fc.keyframe_points:
                k.co.x -= f0; k.handle_left.x -= f0; k.handle_right.x -= f0
            fc.update()
    print("AZ %-10s %.0f〜%.0f → %.0f〜%.0f" % (nm, f0, f0 + (act.frame_range[1] - act.frame_range[0]), act.frame_range[0], act.frame_range[1]))
want = ['Idle', 'Walk_Child', 'Run', 'Skip']
tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
for nm, act in tracks:
    t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, 0, act); s2.name = nm
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print("AZ 書き出し", OUT)
