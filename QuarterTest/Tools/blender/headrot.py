# -*- coding: utf-8 -*-
"""頭・首・背骨のワールド回転が素の姿勢からどれだけ回っているか（角度）をコマごとに出す。"""
import bpy, sys, math
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
aw = arm.matrix_world
CH=["Hips","Spine","Spine01","Spine02","neck","Head"]
def WQ(n): return (aw @ arm.pose.bones[n].matrix).to_quaternion()
arm.animation_data.action=None; bpy.context.view_layer.update()
rest={n:WQ(n).copy() for n in CH}
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
for k in range(8):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/8))); bpy.context.view_layer.update()
    out=[]
    for n in CH:
        d=rest[n].inverted() @ WQ(n); ax,ang=d.to_axis_angle()
        ax=aw.to_3x3().inverted() @ ax if False else ax
        out.append("%s %4.0f°(%+.1f,%+.1f,%+.1f)" % (n[:5], math.degrees(ang), ax.x, ax.y, ax.z))
    print("HR %d  " % k + "  ".join(out))
