# -*- coding: utf-8 -*-
"""unityview.py と同じカメラで、画面上の指定位置(0..1)に当たる面を調べ、UV とテクスチャ色を出す。
   実行: blender -b --factory-startup -P pick.py -- 入力.glb テクスチャ 倍率 sx,sy sx,sy ..."""
import bpy, sys, math
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,ZOOM=a[0],a[1],float(a[2]); PTS=[tuple(map(float,s.split(','))) for s in a[3].split(';')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh=next(o for o in bpy.data.objects if o.type=='MESH')
bpy.context.view_layer.update()
aw=arm.matrix_world
hp=aw@arm.pose.bones["Head"].head; top=aw@arm.pose.bones["head_end"].head
size=(top-hp).length; c=Vector((hp.x,hp.y,hp.z+size*0.5)); osz=size*2.2/ZOOM
er,ar=math.radians(30),math.radians(45); R=20
loc=Vector((c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er)))
fwd=(c-loc).normalized(); right=fwd.cross(Vector((0,0,1))).normalized(); upv=right.cross(fwd).normalized()
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
me=mesh.data; uvl=me.uv_layers.active.data
mwi=mesh.matrix_world.inverted()
for sx,sy in PTS:
    o=loc + right*((sx-0.5)*osz) + upv*((0.5-sy)*osz)
    hit,p,n,fi = mesh.ray_cast(mwi@o, (mwi.to_3x3()@fwd).normalized())
    if not hit: print("PK (%.2f,%.2f) 当たらず"%(sx,sy)); continue
    f=me.polygons[fi]
    uvs=[tuple(uvl[li].uv) for li in f.loop_indices]
    u=sum(x[0] for x in uvs)/len(uvs); v=sum(x[1] for x in uvs)/len(uvs)
    col=px[int(v*H)%H,int(u*W)%W,:3]
    wp=mesh.matrix_world@p
    print("PK (%.2f,%.2f) 面%d 位置(%.3f,%.3f,%.3f) UV(%.4f,%.4f) 色 R%.2f G%.2f B%.2f"%(sx,sy,fi,wp.x,wp.y,wp.z,u,v,*col))
