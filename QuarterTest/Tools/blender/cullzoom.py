# -*- coding: utf-8 -*-
"""同じコマ・同じ角度で「裏面を描く／描かない」を並べて比べる（Unity は描かない側）。
   実行: blender -b --factory-startup -P cullzoom.py -- 入力.glb 出力.png クリップ コマ/総数 骨名 幅 方位角,仰角"""
import bpy, sys, math, os
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT,CLIP,FR,BONE=a[0],a[1],a[2],a[3],a[4]; WID=float(a[5]); AZ,EL=map(float,a[6].split(','))
k,n=map(int,FR.split('/'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
act=bpy.data.actions.get(CLIP)
if act:
    arm.animation_data.action=act; f0,f1=act.frame_range
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/n)))
bpy.context.view_layer.update()
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
CW=480; sc.render.resolution_x=CW; sc.render.resolution_y=CW; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=WID
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
c=arm.matrix_world@arm.pose.bones[BONE].head
er,ar=math.radians(EL),math.radians(AZ); R=20
cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
cam.rotation_euler=(Vector(c)-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
tmp=os.path.join(os.path.dirname(OUT),"_c"); os.makedirs(tmp,exist_ok=True); tiles=[]
for i,cull in enumerate((True,False)):
    sc.display.shading.show_backface_culling=cull
    p=os.path.join(tmp,"c_%d.png"%i); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append(p)
W=CW*2; sh=bpy.data.images.new("s",W,CW); buf=[1.0]*(W*CW*4)
for i,p in enumerate(tiles):
    im=bpy.data.images.load(p); px=im.pixels[:]
    for y in range(CW):
        d=(y*W+i*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
sh.pixels=buf; sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save(); print("CZ",OUT)
