# -*- coding: utf-8 -*-
"""耳のまわりを大きく描く（髪と肌の境目の確認用）。
   実行: blender -b --factory-startup -P earzoom.py -- 入力.glb 出力.png 方位角 仰角 [光]"""
import bpy, sys, math
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT=a[0],a[1]; AZ=float(a[2]); EL=float(a[3]); LIGHT=a[4] if len(a)>4 else 'STUDIO'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh=next(o for o in bpy.data.objects if o.type=='MESH')
bpy.context.view_layer.update()
aw=arm.matrix_world
hp=aw@arm.pose.bones["Head"].head; top=aw@arm.pose.bones["head_end"].head
size=(top-hp).length
# 耳のあたり＝頭の骨から横へ、少し上
side = 1 if math.sin(math.radians(AZ))>0 else -1
C=Vector((hp.x+side*size*0.55, hp.y, hp.z+size*0.45))
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light=LIGHT; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.render.resolution_x=760; sc.render.resolution_y=760; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=size*0.9
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
er,ar=math.radians(EL),math.radians(AZ); R=20
cam.location=(C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er))
cam.rotation_euler=(C-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
sc.render.filepath=OUT; bpy.ops.render.render(write_still=True); print("EZ",OUT)
