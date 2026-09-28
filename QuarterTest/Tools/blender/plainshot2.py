# -*- coding: utf-8 -*-
"""骨が無いモデルでも描けるように、メッシュの箱から枠を決めて複数の角度で描く。"""
import bpy, sys, math, os
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT=a[0],a[1]; AZS=[float(x) for x in a[2].split(',')]; EL=float(a[3]); ZOOM=float(a[4]) if len(a)>4 else 1.0
bpy.ops.wm.read_factory_settings(use_empty=True)
if SRC.lower().endswith('.fbx'): bpy.ops.import_scene.fbx(filepath=SRC)
else: bpy.ops.import_scene.gltf(filepath=SRC)
import sys as _s
_t=[x for x in _s.argv if x.endswith('.png') and ('tex' in x or 'baked' in x)]
if _t:
    ni=bpy.data.images.load(_t[-1])
    for m in bpy.data.materials:
        if not m.use_nodes: continue
        for n in m.node_tree.nodes:
            if n.type=='TEX_IMAGE': n.image=ni
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
ms=[o for o in bpy.data.objects if o.type=='MESH']
pts=[]
for m in ms:
    for v in m.data.vertices: pts.append(tuple(m.matrix_world@v.co))
P=np.array(pts); lo=P.min(0); hi=P.max(0); C=Vector(((lo+hi)/2)); Hh=float(hi[2]-lo[2])
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
CW=520; sc.render.resolution_x=CW; sc.render.resolution_y=int(CW*1.25); sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=Hh*1.15/ZOOM
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
tiles=[]; tmp=os.path.join(os.path.dirname(OUT),"_ps"); os.makedirs(tmp,exist_ok=True)
for i,az in enumerate(AZS):
    er,ar=math.radians(EL),math.radians(az); R=Hh*20
    cam.location=(C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er))
    cam.rotation_euler=(C-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
    p=os.path.join(tmp,"p_%d.png"%i); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append(p)
CH=int(CW*1.25); W=CW*len(tiles); sh=bpy.data.images.new("s",W,CH); buf=[1.0]*(W*CH*4)
for i,p in enumerate(tiles):
    im=bpy.data.images.load(p); px=im.pixels[:]
    for y in range(CH):
        d=(y*W+i*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
sh.pixels=buf; sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save(); print("PS",OUT)
