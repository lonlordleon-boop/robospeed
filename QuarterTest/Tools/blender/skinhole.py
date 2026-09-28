# -*- coding: utf-8 -*-
"""髪の中に肌色が見えている画素を機械的に探し、その光線上に何枚の面があるかを調べる。
   「髪が無くて地肌が見えている」のか「地肌が髪を突き抜けている」のかを見分ける。
   実行: blender -b --factory-startup -P skinhole.py -- 入力.glb テクスチャ 方位角 仰角"""
import bpy, sys, math
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX=a[0],a[1]; AZ=float(a[2]); EL=float(a[3])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh=next(o for o in bpy.data.objects if o.type=='MESH')
bpy.context.view_layer.update()
me=mesh.data; uvl=me.uv_layers.active.data
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
def texcol(fi,p):
    f=me.polygons[fi]
    uv=np.array([uvl[li].uv for li in f.loop_indices]).mean(0)
    return px[int(uv[1]*H)%H, int(uv[0]*W)%W, :3]
def cls(c):
    r,g,b=c
    if r>0.70 and g>0.45 and b>0.35 and g<r*0.99 and b<g*1.05: return '肌'
    if r>0.30 and g<r*0.72 and b<r*0.52: return '髪'
    return 'その他'
aw=arm.matrix_world
hp=aw@arm.pose.bones["Head"].head; top=aw@arm.pose.bones["head_end"].head
size=(top-hp).length; C=Vector((hp.x,hp.y,hp.z+size*0.45)); osz=size*1.5
er,ar=math.radians(EL),math.radians(AZ); R=20
loc=Vector((C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er)))
fwd=(C-loc).normalized(); right=fwd.cross(Vector((0,0,1))).normalized(); up=right.cross(fwd).normalized()
mwi=mesh.matrix_world.inverted(); dloc=(mwi.to_3x3()@fwd).normalized()
N=70; found=0
grid={}
for iy in range(N):
    for ix in range(N):
        sx=(ix+0.5)/N; sy=(iy+0.5)/N
        o=loc + right*((sx-0.5)*osz) + up*((0.5-sy)*osz)
        hit,p,nn,fi = mesh.ray_cast(mwi@o, dloc)
        grid[(ix,iy)]=(cls(texcol(fi,p)) if hit else None, p if hit else None, fi if hit else -1)
for iy in range(1,N-1):
    for ix in range(1,N-1):
        k,pp,fi=grid[(ix,iy)]
        if k!='肌': continue
        nb=[grid[(ix+dx,iy+dy)][0] for dx in(-1,0,1) for dy in(-1,0,1) if (dx,dy)!=(0,0)]
        if nb.count('髪')<6: continue
        found+=1
        if found>4: continue
        # この光線上の面をすべて拾う
        sx=(ix+0.5)/N; sy=(iy+0.5)/N
        o=mwi@(loc + right*((sx-0.5)*osz) + up*((0.5-sy)*osz))
        layers=[]; cur=o
        for _ in range(8):
            hit,p,nn,f2 = mesh.ray_cast(cur, dloc)
            if not hit: break
            layers.append((round((p-o).length,4), cls(texcol(f2,p)), f2))
            cur = p + dloc*0.0005
        wp=mesh.matrix_world@pp
        print("SH 画素(%d,%d) 位置(%.3f,%.3f,%.3f) 光線上の面: %s"%(ix,iy,wp.x,wp.y,wp.z,layers))
print("SH 髪に囲まれた肌色の画素 %d 個 / %d 画素中"%(found,N*N))
