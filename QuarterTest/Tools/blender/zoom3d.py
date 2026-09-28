# -*- coding: utf-8 -*-
"""指定した3次元の点のまわりを大きく描く（素の姿勢）。
   実行: blender -b --factory-startup -P zoom3d.py -- 入力.glb 出力.png x,y,z 幅 方位角,仰角[;...]"""
import bpy, sys, math, os
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT=a[0],a[1]; C=Vector(tuple(map(float,a[2].split(',')))); WID=float(a[3])
VIEWS=[tuple(map(float,s.split(','))) for s in a[4].split(';')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
CW=460; sc.render.resolution_x=CW; sc.render.resolution_y=CW; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=WID
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
tiles=[]; tmp=os.path.join(os.path.dirname(OUT),"_z"); os.makedirs(tmp,exist_ok=True)
for i,(az,el) in enumerate(VIEWS):
    er,ar=math.radians(el),math.radians(az); R=20
    cam.location=(C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er))
    cam.rotation_euler=(C-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
    p=os.path.join(tmp,"z_%d.png"%i); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append(p)
W=CW*len(tiles); sh=bpy.data.images.new("s",W,CW); buf=[1.0]*(W*CW*4)
for i,p in enumerate(tiles):
    im=bpy.data.images.load(p); px=im.pixels[:]
    for y in range(CW):
        d=(y*W+i*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
sh.pixels=buf; sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save(); print("Z3",OUT)
