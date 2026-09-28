# -*- coding: utf-8 -*-
"""髪に覆われている地肌を、髪の色で塗り直す。
   このモデルは髪の房と房のあいだに隙間があり、そこから地肌（肌色）が筋になって覗く。
   隙間そのものを塞ぐには形を作り直す必要があるが、覗く先の地肌を髪色にしておけば目立たない。
   面ごとに法線の向きへ光線を飛ばし、すぐ外側に髪の面があるものだけを塗る（外から見える肌には触らない）。
   実行: blender -b --factory-startup -P scalpfix.py -- 入力.glb 元テクスチャ 出力テクスチャ [mark]"""
import bpy, sys
import numpy as np
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; MARK=len(a)>3 and a[3]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); col=np.zeros((NF,3))
for f in me.polygons:
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    col[f.index]=np.mean([px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv],0)
def cls(c):
    r,g,b=c
    if r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08: return 1   # 肌
    if r>0.28 and g<r*0.75 and b<r*0.55: return 2                          # 髪
    return 0
K=np.array([cls(c) for c in col])
mw=mesh.matrix_world; mwi=mw.inverted()
covered=[]; fillcol={}
for f in me.polygons:
    if K[f.index]!=1: continue
    c=mw@f.center
    if c.z < neckz: continue
    n=(mw.to_3x3()@f.normal).normalized()
    o=mwi@(c+n*0.0015); d=(mwi.to_3x3()@n).normalized()
    hit,p,nn,fi = mesh.ray_cast(o,d,distance=0.06)
    if not hit or fi==f.index: continue
    if K[fi]!=2: continue
    covered.append(f.index); fillcol[f.index]=col[fi]
print("SC 首より上の肌の面のうち、すぐ外側が髪の面 %d 枚"%len(covered))
me.calc_loop_triangles()
tri_of=[[] for _ in range(NF)]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
def raster(tris):
    m=np.zeros((H,W),bool)
    for t in tris:
        uv=np.array([uvl[li].uv for li in t.loops],float)
        xs=uv[:,0]*W; ys=uv[:,1]*H
        x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
        y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
        if x1<x0 or y1<y0 or (x1-x0)>400 or (y1-y0)>400: continue
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        dd=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(dd)<1e-12: continue
        l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/dd
        l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/dd
        l3=1-l1-l2
        m[y0:y1+1,x0:x1+1] |= (l1>=-0.2)&(l2>=-0.2)&(l3>=-0.2)
    return m
cs=set(covered)
others=raster([t for i in range(NF) if i not in cs for t in tri_of[i]])
out=px.copy(); n=0
for i in covered:
    m=raster(tri_of[i]) & (~others)
    c=[0,1,0] if MARK else fillcol[i]
    out[m,0]=c[0]; out[m,1]=c[1]; out[m,2]=c[2]; n+=int(m.sum())
print("SC 塗り直した画素 %d"%n)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("SC 書き出し",OUT)
