# -*- coding: utf-8 -*-
"""髪の上に乗ってしまった肌色の染みを、近くの髪の色で塗り直す。
   このモデルの髪の房は形ではなく絵で描かれているため、房の途中に肌色が乗ると
   「髪に肌の色が混じっている」ように見える。
   肌色の面を「つながり」でかたまりに分けると、顔と耳は一つの大きなかたまりになり、
   髪の上の染みは小さな孤立したかたまりになる。小さいものだけを塗り替える。
   実行: blender -b --factory-startup -P patchheal.py -- 入力.glb 元テクスチャ 出力テクスチャ 面数の上限 [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; LIM=int(a[3]) if len(a)>3 else 60; MARK=len(a)>4 and a[4]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); K=np.zeros(NF,int); ctr=np.zeros((NF,3)); col=np.zeros((NF,3))
for f in me.polygons:
    uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    c=px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]; r,g,b=c; col[f.index]=c
    K[f.index]= 1 if (r>0.66 and g>0.40 and b>0.30 and g<r*0.99 and b<g*1.10) else (2 if (r>0.28 and g<r*0.75 and b<r*0.55) else 0)
    ctr[f.index]=tuple(mw@f.center)
P=np.array([tuple(mw@v.co) for v in me.vertices])
key={}; rep=np.arange(len(P))
for v in range(len(P)):
    k=tuple(np.round(P[v],5))
    if k in key: rep[v]=key[k]
    else: key[k]=v
e2f={}
for f in me.polygons:
    vs=[rep[me.loops[li].vertex_index] for li in f.loop_indices]
    for i in range(len(vs)):
        e=tuple(sorted((vs[i],vs[(i+1)%len(vs)]))); e2f.setdefault(e,[]).append(f.index)
skins=[i for i in range(NF) if K[i]==1 and ctr[i][2]>neckz]
S=set(skins); par={i:i for i in skins}
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for e,fs in e2f.items():
    ss=[i for i in fs if i in S]
    for j in ss[1:]: par[find(ss[0])]=find(j)
grp={}
for i in skins: grp.setdefault(find(i),[]).append(i)
target=[i for v in grp.values() if len(v)<=LIM for i in v]
print("PH 頭の肌色 %d面／かたまり %d個。%d面以下の孤立した染み %d面を塗り替える"%(len(skins),len(grp),LIM,len(target)))
hair=np.where((K==2)&(ctr[:,2]>neckz))[0]
fill={}
for i in target:
    d=np.linalg.norm(ctr[hair]-ctr[i],axis=1); fill[i]=np.median(col[hair[np.argsort(d)[:16]]],0)
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
        m[y0:y1+1,x0:x1+1] |= (l1>=-0.25)&(l2>=-0.25)&(l3>=-0.25)
    return m
ts=set(target)
keep=raster([t for i in range(NF) if i not in ts for t in tri_of[i]])
out=px.copy(); n=0
for i in target:
    m=raster(tri_of[i]) & (~keep)
    c=[0,1,0] if MARK else fill[i]
    out[m,0]=c[0]; out[m,1]=c[1]; out[m,2]=c[2]; n+=int(m.sum())
print("PH 塗り替えた画素 %d"%n)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("PH 書き出し",OUT)
