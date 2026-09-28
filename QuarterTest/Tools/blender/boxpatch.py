# -*- coding: utf-8 -*-
"""指定した箱の中で、髪に囲まれた肌色の面を、まわりの髪の色でにじませて埋める。
   眉が髪の上に描かれている箇所を消すために使う。
   実行: blender -b --factory-startup -P boxpatch.py -- 入力.glb 元テクスチャ 出力 x0,x1,y0,y1,z0,z1 広げ幅 [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]
b=[float(x) for x in a[3].split(',')]; PAD=int(a[4]); MARK=len(a)>5 and a[5]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); K=np.zeros(NF,int); ctr=np.zeros((NF,3)); col=np.zeros((NF,3))
for f in me.polygons:
    uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    c=px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]; col[f.index]=c; ctr[f.index]=tuple(mw@f.center)
    r,g,bb=c
    K[f.index]= 1 if ((r>0.62 and g>0.36 and bb>0.26 and g<r*0.995 and bb<g*1.25) or (r>0.70 and g>0.58 and bb>0.52)) else (2 if (r>0.26 and g<r*0.78 and bb<r*0.60) else 0)
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
nbf=[[] for _ in range(NF)]
for f in me.polygons:
    for e in f.edge_keys: nbf[f.index]+=[j for j in e2f.get(e,[]) if j!=f.index]
inbox=(ctr[:,0]>=b[0])&(ctr[:,0]<=b[1])&(ctr[:,1]>=b[2])&(ctr[:,1]<=b[3])&(ctr[:,2]>=b[4])&(ctr[:,2]<=b[5])
sel=[i for i in range(NF) if inbox[i] and K[i]==1 and any(K[j]==2 for j in nbf[i])]
print("BP 箱の中の面 %d、そのうち髪に接した肌色 %d"%(int(inbox.sum()),len(sel)))
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
M0=raster([t for i in sel for t in tri_of[i]])
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
M=box(M0,PAD)>0.0
r,g,bb=px[:,:,0],px[:,:,1],px[:,:,2]
hair=(r>0.26)&(r<0.95)&(g<r*0.78)&(bb<r*0.60)
fill=M&(~hair)
print("BP 埋める画素 %d"%int(fill.sum()))
out=px.copy()
if MARK:
    out[fill,0]=0; out[fill,1]=1; out[fill,2]=0
else:
    known=hair.copy(); cur=out.copy()
    for _ in range(PAD*3+20):
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
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("BP 書き出し",OUT)
