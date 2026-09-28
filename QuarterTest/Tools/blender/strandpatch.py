# -*- coding: utf-8 -*-
"""髪の房の絵が足りていない箇所を、隣の髪の色を「にじませて」埋める。
   面の三角形で塗り分けるとギザギザになるので、埋める範囲だけを決めて、
   その中を外側の髪の色から少しずつ広げて埋める（色の階調が保たれる）。
   実行: blender -b --factory-startup -P strandpatch.py -- 入力.glb 元テクスチャ 出力テクスチャ x,y,z 半径 広げ幅 [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]
SEEDS=[np.array([float(t) for t in q.split(',')]) for q in a[3].split(';')]; RAD=float(a[4]); PAD=int(a[5])
MARK=len(a)>6 and a[6]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
def facecol(f):
    uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    return px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]
NF=len(me.polygons)
K=np.zeros(NF,int)
for f in me.polygons:
    r,g,b=facecol(f)
    K[f.index]= 1 if ((r>0.62 and g>0.36 and b>0.26 and g<r*0.995 and b<g*1.20) or (r>0.72 and g>0.60 and b>0.55)) else (2 if (r>0.26 and g<r*0.76 and b<r*0.58) else 0)
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
nbf=[[] for _ in range(NF)]
for f in me.polygons:
    for e in f.edge_keys: nbf[f.index]+=[j for j in e2f.get(e,[]) if j!=f.index]
ctrs=np.array([tuple(mw@f.center) for f in me.polygons])
sel=[]
for i in range(NF):
    if K[i]!=1: continue
    if min(np.linalg.norm(ctrs[i]-sd) for sd in SEEDS)>RAD: continue
    if not any(K[j]==2 for j in nbf[i]): continue      # 髪の面と接している縁だけ
    sel.append(i)
print("SP 範囲内で肌色・白っぽい面 %d"%len(sel))
me.calc_loop_triangles()
tri_of=[[] for _ in range(len(me.polygons))]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
def raster(tris,mg=0.0):
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
M0=raster([t for i in sel for t in tri_of[i]],0.15)
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
M=box(M0,PAD)>0.0
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=(r>0.26)&(r<0.92)&(g<r*0.76)&(b<r*0.58)
fillzone=M&(~hair)
print("SP 埋める画素 %d（元の面の画素 %d）"%(int(fillzone.sum()),int(M0.sum())))
out=px.copy()
if MARK:
    out[fillzone,0]=0; out[fillzone,1]=1; out[fillzone,2]=0
else:
    known=hair.copy(); cur=out.copy()
    for _ in range(PAD*3+12):
        s=np.zeros((H,W,4),np.float32); cnt=np.zeros((H,W),np.float32)
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            sh=np.roll(np.roll(cur,dy,axis=0),dx,axis=1)
            kn=np.roll(np.roll(known,dy,axis=0),dx,axis=1).astype(np.float32)
            s+=sh*kn[:,:,None]; cnt+=kn
        f=fillzone&(~known)&(cnt>0)
        if not f.any(): break
        cur[f]=(s[f]/cnt[f][:,None]); known|=f
    out=np.where(fillzone[:,:,None], cur, out)
    # ふちを2画素だけならして、境目を目立たなくする
    edge=(box(fillzone,2)>0.0)&(box(fillzone,2)<1.0)
    sm=np.stack([box(out[:,:,k],1) for k in range(3)],2)
    for k in range(3): out[:,:,k]=np.where(edge,sm[:,:,k],out[:,:,k])
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("SP 書き出し",OUT)
