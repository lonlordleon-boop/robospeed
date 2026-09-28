# -*- coding: utf-8 -*-
"""素の姿勢と各クリップで、背骨〜頭の各骨が腰からどれだけ横（x）にずれているかを出す。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS = a[1].split(',')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
aw = arm.matrix_world
def P(n): return aw @ arm.pose.bones[n].head
CH=["Hips","Spine","Spine01","Spine02","neck","Head","head_end"]
def row(tag):
    h=P("Hips")
    print("L2 %-14s " % tag + "  ".join("%s%+.3f" % (n[:6], P(n).x-h.x) for n in CH[1:]) + "   頭高%.3f" % (P("head_end").z-h.z))
arm.animation_data.action=None; bpy.context.view_layer.update(); row("rest")
for c in CLIPS:
    act=bpy.data.actions.get(c); arm.animation_data.action=act; f0,f1=act.frame_range
    for k in range(8):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/8))); bpy.context.view_layer.update(); row("%s %d"%(c,k))
