# -*- coding: utf-8 -*-
"""指定の骨のあたりを、指定の角度・コマで大きく描く。
   実行: blender -b --factory-startup -P spot.py -- 入力.glb 出力.png クリップ コマ/総数 骨名 幅 方位角,仰角[;...]"""
import bpy, sys, math, os
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT,CLIP=a[0],a[1],a[2]; FR=a[3]; BONE=a[4]; WIDTH=float(a[5]); VIEWS=[tuple(map(float,s.split(','))) for s in a[6].split(';')]
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
CW=500; sc.render.resolution_x=CW; sc.render.resolution_y=CW; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
cd.ortho_scale=WIDTH
c=arm.matrix_world@arm.pose.bones[BONE].head
tiles=[]; tmp=os.path.join(os.path.dirname(OUT),"_t"); os.makedirs(tmp,exist_ok=True)
for i,(az,el) in enumerate(VIEWS):
    er,ar=math.radians(el),math.radians(az); R=20
    cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
    cam.rotation_euler=(Vector(c)-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
    p=os.path.join(tmp,"s_%d.png"%i); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append(p)
W=CW*len(tiles); sh=bpy.data.images.new("s",W,CW); buf=[1.0]*(W*CW*4)
for i,p in enumerate(tiles):
    im=bpy.data.images.load(p); px=im.pixels[:]
    for y in range(CW):
        d=(y*W+i*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
sh.pixels=buf; sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save(); print("SP",OUT)
