# -*- coding: utf-8 -*-
"""頭を複数の角度で大きく描いて並べる（髪の肌色を探すため）。
   実行: blender -b --factory-startup -P headsweep.py -- 入力.glb 出力.png 方位角1,方位角2,... 仰角 光"""
import bpy, sys, math, os
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT=a[0],a[1]; AZS=[float(x) for x in a[2].split(',')]; EL=float(a[3]); LIGHT=a[4] if len(a)>4 else 'STUDIO'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
bpy.context.view_layer.update()
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light=LIGHT; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
CW=560; sc.render.resolution_x=CW; sc.render.resolution_y=CW; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
aw=arm.matrix_world
hp=aw@arm.pose.bones["Head"].head; top=aw@arm.pose.bones["head_end"].head
size=(top-hp).length; c=Vector((hp.x,hp.y,hp.z+size*0.45)); cd.ortho_scale=size*1.5
tiles=[]; tmp=os.path.join(os.path.dirname(OUT),"_hs"); os.makedirs(tmp,exist_ok=True)
for i,az in enumerate(AZS):
    er,ar=math.radians(EL),math.radians(az); R=20
    cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
    cam.rotation_euler=(c-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
    p=os.path.join(tmp,"s_%d.png"%i); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append(p)
W=CW*len(tiles); sh=bpy.data.images.new("s",W,CW); buf=[1.0]*(W*CW*4)
for i,p in enumerate(tiles):
    im=bpy.data.images.load(p); px=im.pixels[:]
    for y in range(CW):
        d=(y*W+i*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
sh.pixels=buf; sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save(); print("HS",OUT)
