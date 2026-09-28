# -*- coding: utf-8 -*-
"""各骨のワールド回転を「横倒し(roll)・前後(pitch)・向き(yaw)」に分けてコマごとに出す。
   素の姿勢の上向き・前向きベクトルを回して、その傾きを角度にする。"""
import bpy, sys, math
from mathutils import Vector
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
UP=Vector((0,0,1)); FWD=Vector((0,-1,0))
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
print("TL 横倒し=上向きが左右へ倒れた角(+は左)  前後=上向きが前後へ倒れた角(+は前)  向き=前向きが左右へ回った角(+は左)")
for k in range(8):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/8))); bpy.context.view_layer.update()
    out=[]
    for n in CH:
        d=WQ(n) @ rest[n].inverted()   # ワールドでの素の姿勢からの差
        u=d @ UP; f=d @ FWD
        roll=math.degrees(math.atan2(u.x, u.z)); pitch=math.degrees(math.atan2(-u.y, u.z)); yaw=math.degrees(math.atan2(f.x, -f.y))
        out.append("%s r%+3.0f p%+3.0f y%+3.0f" % (n[:5], roll, pitch, yaw))
    print("TL %d  " % k + " | ".join(out))
