# -*- coding: utf-8 -*-
"""zoom3d.py と同じカメラで、画面上の位置(0..1)に当たる面の3次元の位置とテクスチャの色を返す。
   実行: blender -b --factory-startup -P pick3d.py -- 入力.glb テクスチャ x,y,z 幅 方位角,仰角 sx,sy;sx,sy..."""
import bpy, sys, math
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX=a[0],a[1]; C=Vector(tuple(map(float,a[2].split(',')))); WID=float(a[3])
AZ,EL=map(float,a[4].split(',')); PTS=[tuple(map(float,s.split(','))) for s in a[5].split(';')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
er,ar=math.radians(EL),math.radians(AZ); R=20
loc=Vector((C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er)))
fwd=(C-loc).normalized(); right=fwd.cross(Vector((0,0,1))).normalized(); up=right.cross(fwd).normalized()
mwi=mesh.matrix_world.inverted(); d=(mwi.to_3x3()@fwd).normalized()
for sx,sy in PTS:
    o=mwi@(loc + right*((sx-0.5)*WID) + up*((0.5-sy)*WID))
    hit,p,n,fi = mesh.ray_cast(o,d)
    if not hit: print("PK (%.2f,%.2f) 当たらず"%(sx,sy)); continue
    f=me.polygons[fi]
    uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    c=px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]
    wp=mesh.matrix_world@p
    print("PK (%.2f,%.2f) 面%d 位置(%.4f,%.4f,%.4f) UV(%.4f,%.4f) 色 %.2f/%.2f/%.2f"%(sx,sy,fi,wp.x,wp.y,wp.z,uv[0],uv[1],*c))
