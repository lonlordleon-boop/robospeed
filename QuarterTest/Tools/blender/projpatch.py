# -*- coding: utf-8 -*-
"""面を画面に投影して、指定した画面の枠に入る手前側の面を選び、そのテクスチャを
   まわりの髪の色でにじませて埋める。光線を飛ばさないので座標の取り違えが起きない。
   実行: blender -b --factory-startup -P projpatch.py -- 入力.glb 元テクスチャ 出力 中心x,y,z 幅 枠sx0,sx1,sy0,sy1 [mark]"""
import bpy, sys
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]
C=Vector(tuple(map(float,a[3].split(',')))); WID=float(a[4])
sb=[float(x) for x in a[5].split(',')]; MARK=len(a)>6 and a[6]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
fwd=Vector((0,1,0)); right=Vector((1,0,0)); up=Vector((0,0,1))   # 正面から見る（方位角0）
NF=len(me.polygons)
ctr=np.zeros((NF,3)); nrm=np.zeros((NF,3))
for f in me.polygons:
    ctr[f.index]=tuple(mw@f.center); nrm[f.index]=tuple((mw.to_3x3()@f.normal).normalized())
d=ctr-np.array([C.x,C.y,C.z])
sx=(d@np.array([right.x,right.y,right.z]))/WID+0.5
sy=0.5-(d@np.array([up.x,up.y,up.z]))/WID
depth=d@np.array([fwd.x,fwd.y,fwd.z])
face_to=nrm@np.array([-fwd.x,-fwd.y,-fwd.z])
inbox=(sx>=sb[0])&(sx<=sb[1])&(sy>=sb[2])&(sy<=sb[3])&(face_to>-0.25)
if inbox.sum():
    dmin=depth[inbox].min()
    sel=[i for i in range(NF) if inbox[i] and depth[i]<dmin+0.055]
else: sel=[]
print("PP 枠に入る面 %d、手前3cm以内 %d"%(int(inbox.sum()),len(sel)))
me.calc_loop_triangles()
tri_of=[[] for _ in range(NF)]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
def raster(tris,mg=0.15):
    m=np.zeros((H,W),bool)
    for t in tris:
        uv=np.array([uvl[li].uv for li in t.loops],float)
        xs=uv[:,0]*W; ys=uv[:,1]*H
        x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
        y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
        if x1<x0 or y1<y0 or (x1-x0)>300 or (y1-y0)>300: continue
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        dd=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(dd)<1e-12: continue
        l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/dd
        l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/dd
        l3=1-l1-l2
        m[y0:y1+1,x0:x1+1] |= (l1>=-mg)&(l2>=-mg)&(l3>=-mg)
    return m
M=raster([t for i in sel for t in tri_of[i]])
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=(r>0.26)&(r<0.95)&(g<r*0.80)&(b<r*0.62)
fill=M&(~hair)
print("PP 埋める画素 %d"%int(fill.sum()))
out=px.copy()
if MARK:
    out[fill,0]=0; out[fill,1]=1; out[fill,2]=0
else:
    # まわりの髪の色の平均で塗る（すぐ隣が明るいと、にじませても明るいままになるため）
    def boxf(m,rr):
        c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
        return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
    RR=40
    hs=np.stack([boxf(np.where(hair,px[:,:,k],0),RR) for k in range(3)],2)
    hc=np.maximum(boxf(hair,RR),1e-6)
    hcol=hs/hc[:,:,None]
    for k in range(3): out[:,:,k]=np.where(fill,hcol[:,:,k],out[:,:,k])
    e=(boxf(fill,2)>0)&(boxf(fill,2)<1)
    sm=np.stack([boxf(out[:,:,k],2) for k in range(3)],2)
    for k in range(3): out[:,:,k]=np.where(e,sm[:,:,k],out[:,:,k])
    known=hair.copy(); cur=out.copy()
    for _ in range(0):
        s=np.zeros((H,W,4),np.float32); cnt=np.zeros((H,W),np.float32)
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            sh=np.roll(np.roll(cur,dy,axis=0),dx,axis=1)
            kn=np.roll(np.roll(known,dy,axis=0),dx,axis=1).astype(np.float32)
            s+=sh*kn[:,:,None]; cnt+=kn
        f=fill&(~known)&(cnt>0)
        if not f.any(): break
        cur[f]=(s[f]/cnt[f][:,None]); known|=f
    out=np.where(fill[:,:,None], cur, out)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("PP 書き出し",OUT)
