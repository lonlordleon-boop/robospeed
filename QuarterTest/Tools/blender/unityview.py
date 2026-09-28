# -*- coding: utf-8 -*-
"""Unity のゲーム画面と同じ角度（仰角30度・方位45度）で、頭を大きく描く。
   実行: blender -b --factory-startup -P unityview.py -- 入力.glb 出力.png クリップ 時刻 倍率"""
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP, FR = a[0], a[1], a[2], float(a[3]); ZOOM=float(a[4]) if len(a)>4 else 1.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
act=bpy.data.actions.get(CLIP)
if act: arm.animation_data.action=act; f0,f1=act.frame_range; bpy.context.scene.frame_set(int(round(f0+(f1-f0)*FR)))
bpy.context.view_layer.update()
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.render.resolution_x=700; sc.render.resolution_y=700; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
aw=arm.matrix_world
hp=aw@arm.pose.bones["Head"].head; top=aw@arm.pose.bones["head_end"].head
size=(top-hp).length
c=Vector((hp.x,hp.y,hp.z+size*0.5)); cd.ortho_scale=size*2.2/ZOOM
er,ar=math.radians(30),math.radians(45); R=20
cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
cam.rotation_euler=(c-cam.location).to_track_quat('-Z','Y').to_euler()
sc.render.filepath=OUT; bpy.ops.render.render(write_still=True); print("UVW",OUT)
