# -*- coding: utf-8 -*-
"""コマごとの上体の左右の傾き（頭−腰の横ずれ）と足の高さを出す（診断用）。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
act = bpy.data.actions.get(CLIP)
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action = act
f0, f1 = act.frame_range
aw = arm.matrix_world
def P(n): return aw @ arm.pose.bones[n].head
N=16
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    h=P("Hips"); hd=P("head_end"); nk=P("Spine2") if "Spine2" in arm.pose.bones else P("Spine"); l=P("LeftFoot"); r=P("RightFoot")
    mid=(l+r)/2
    print("LN %2d 腰x-足中x %+.3f  首x-腰x %+.3f  頭x-腰x %+.3f  頭y-腰y %+.3f" % (k, h.x-mid.x, nk.x-h.x, hd.x-h.x, hd.y-h.y))
