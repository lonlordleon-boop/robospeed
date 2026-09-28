# -*- coding: utf-8 -*-
"""頭の「顔ではない面」に塗られている肌色を、髪の色に塗り替える。
   このモデルの頭はひと繋がりの塊で、髪と顔の境目はテクスチャの塗り分けだけで決まっている。
   その塗り分けが形からずれており、耳の上や後ろの髪の部分にまで肌色が乗って、
   髪に肌の色が混じって見えていた。
   顔（前を向いた面）と耳は残し、それ以外の頭の肌色を、近くの髪の色で塗り直す。
   実行: blender -b --factory-startup -P hairpaint.py -- 入力.glb 元テクスチャ 出力テクスチャ [mark]"""
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
aw=arm.matrix_world; mw=mesh.matrix_world
head=aw@arm.pose.bones['Head'].head
front=((aw@arm.pose.bones['headfront'].head)-head); front.z=0; front.normalize()
neckz=(aw@arm.pose.bones['neck'].head).z
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); col=np.zeros((NF,3)); ctr=np.zeros((NF,3)); nd=np.zeros(NF)
for f in me.polygons:
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    col[f.index]=np.mean([px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv],0)
    c=mw@f.center; ctr[f.index]=(c.x,c.y,c.z)
    n=(mw.to_3x3()@f.normal).normalized(); nd[f.index]=n.dot(front)
def cls(c):
    r,g,b=c
    if r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08: return 1
    if r>0.28 and g<r*0.75 and b<r*0.55: return 2
    return 0
K=np.array([cls(c) for c in col])
onhead=ctr[:,2]>neckz
# 耳＝横に張り出した肌色の面のかたまり。その外枠を求めて残す
ear=(K==1)&onhead&(np.abs(ctr[:,0])>0.15)&(ctr[:,2]>0.63)&(ctr[:,2]<0.80)
boxes=[]
for s in (1,-1):
    m=ear&(np.sign(ctr[:,0])==s)
    if m.sum()<10: continue
    p=ctr[m]; boxes.append((s,p[:,1].min()-0.02,p[:,1].max()+0.02,p[:,2].min()-0.02,p[:,2].max()+0.02))
    print("HP 耳（x%s側）: y %.3f..%.3f  z %.3f..%.3f  %d面"%('+' if s>0 else '-',p[:,1].min(),p[:,1].max(),p[:,2].min(),p[:,2].max(),m.sum()))
def in_ear(i):
    for s,y0,y1,z0,z1 in boxes:
        if np.sign(ctr[i,0])==s and y0<=ctr[i,1]<=y1 and z0<=ctr[i,2]<=z1 and abs(ctr[i,0])>0.13: return True
    return False
# 顔として残す範囲：前を向いている面か、耳の高さ以下（頬・あご・首）。
# それより上で前を向いていない面は、形の上では髪なので塗り替える。
# 耳の上端は形から決める：横に一番張り出している肌色の面の高さ。
EARTOP=0.0
for s2 in (1,-1):
    m=(K==1)&onhead&(np.sign(ctr[:,0])==s2)&(np.abs(ctr[:,0])>0.16)&(ctr[:,2]<0.80)
    if m.sum(): EARTOP=max(EARTOP, float(ctr[m,2].max()))
print("HP 耳の上端 %.3f"%EARTOP)
target=[i for i in range(NF) if K[i]==1 and onhead[i] and ctr[i,2]>EARTOP+0.005 and nd[i]<0.35]
print("HP 頭の肌色の面 %d のうち、顔でも耳でもない %d 枚を塗り替える"%(int(((K==1)&onhead).sum()),len(target)))
# 塗る色＝近くの髪の面の色（同じ側・近い位置の中央値）
hair=np.where((K==2)&onhead)[0]
hc=ctr[hair]
fill={}
for i in target:
    d=np.linalg.norm(hc-ctr[i],axis=1); idx=hair[np.argsort(d)[:12]]
    fill[i]=np.median(col[idx],0)
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
ts=set(target)
keep=raster([t for i in range(NF) if i not in ts for t in tri_of[i]])
out=px.copy(); n=0
for i in target:
    m=raster(tri_of[i]) & (~keep)
    c=[0,1,0] if MARK else fill[i]
    out[m,0]=c[0]; out[m,1]=c[1]; out[m,2]=c[2]; n+=int(m.sum())
print("HP 塗り替えた画素 %d"%n)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("HP 書き出し",OUT)
