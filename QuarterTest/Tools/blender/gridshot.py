# -*- coding: utf-8 -*-
"""指定の場所を大きく描き、10%ごとの目盛り線を重ねる（画面上の位置を正確に読むため）。"""
import bpy, sys, math, os
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; C=Vector(tuple(map(float,a[3].split(',')))); WID=float(a[4]); AZ,EL=map(float,a[5].split(','))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
ni=bpy.data.images.load(TEX)
for m in bpy.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE': n.image=ni
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
N=700; sc.render.resolution_x=N; sc.render.resolution_y=N; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=WID
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
er,ar=math.radians(EL),math.radians(AZ); R=20
loc=Vector((C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er)))
cam.location=loc; cam.rotation_euler=(C-loc).to_track_quat('-Z','Y').to_euler()
tmp=OUT+".tmp.png"; sc.render.filepath=tmp; bpy.ops.render.render(write_still=True)
im=bpy.data.images.load(tmp); A=np.array(im.pixels[:],dtype=np.float32).reshape(N,N,4)
for k in range(1,10):
    p=int(N*k/10)
    A[p-1:p+1,:,:3]=[0,0,1] if k!=5 else [1,0,0]
    A[:,p-1:p+1,:3]=[0,0,1] if k!=5 else [1,0,0]
o=bpy.data.images.new("o",N,N); o.pixels=A.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("GS",OUT)
