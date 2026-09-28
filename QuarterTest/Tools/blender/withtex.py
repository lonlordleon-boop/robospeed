# -*- coding: utf-8 -*-
"""指定のテクスチャに差し替えて頭を描く（ミップマップのにじみを再現する確認用）。
   実行: blender -b --factory-startup -P withtex.py -- 入力.glb テクスチャ 出力.png 方位角"""
import bpy, sys, math
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX,OUT,AZ=a[0],a[1],a[2],float(a[3])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh=next(o for o in bpy.data.objects if o.type=='MESH')
new=bpy.data.images.load(TEX)
for m in mesh.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE': n.image=new; n.interpolation='Linear'
bpy.context.view_layer.update()
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.render.resolution_x=600; sc.render.resolution_y=600; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
aw=arm.matrix_world
hp=aw@arm.pose.bones["Head"].head; top=aw@arm.pose.bones["head_end"].head
size=(top-hp).length; c=Vector((hp.x,hp.y,hp.z+size*0.45)); cd.ortho_scale=size*1.1
er,ar=math.radians(0),math.radians(AZ); R=20
cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
cam.rotation_euler=(c-cam.location).to_track_quat('-Z','Y').to_euler()
sc.render.filepath=OUT; bpy.ops.render.render(write_still=True); print("WT",OUT)
