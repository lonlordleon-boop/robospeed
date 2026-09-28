# -*- coding: utf-8 -*-
"""指定した場所から、つながった肌色の面を決めた距離まで辿って、髪の色に塗り替える。
   頬に垂れた髪の房の途中に肌色が乗っている箇所（房は形ではなく絵なので、
   色のかたまりだけでは顔と切り離せない）を、場所を指定して直すためのもの。
   実行: blender -b --factory-startup -P seedheal.py -- 入力.glb 元テクスチャ 出力テクスチャ 半径 x,y,z;x,y,z... [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; RAD=float(a[3])
SEEDS=[np.array([float(t) for t in s.split(',')]) for s in a[4].split(';')]
MARK=len(a)>5 and a[5]=='mark'
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
    c=px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]; r,g,b=c; col[f.index]=c
    K[f.index]= 1 if (r>0.64 and g>0.38 and b>0.28 and g<r*0.99 and b<g*1.12) else (2 if (r>0.28 and g<r*0.75 and b<r*0.55) else 0)
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
nb=[[] for _ in range(NF)]
for e,fs in e2f.items():
    for i in fs:
        for j in fs:
            if i!=j: nb[i].append(j)
target=set()
for sd in SEEDS:
    d=np.linalg.norm(ctr-sd,axis=1)
    start=[i for i in np.argsort(d)[:200] if K[i]==1 and d[i]<0.014]
    if not start:
        near=np.argsort(d)[:6]
        print('SH   種の近くの面:', [(int(i),int(K[i]),round(float(d[i]),4)) for i in near])
    stack=list(start); seen=set(start)
    while stack:
        i=stack.pop()
        for j in nb[i]:
            if j in seen or K[j]!=1: continue
            if np.linalg.norm(ctr[j]-sd)>RAD: continue
            seen.add(j); stack.append(j)
    target|=seen
    print("SH 種(%.3f,%.3f,%.3f) から %d面"%(*sd,len(seen)))
target=sorted(target)
print("SH 合計 %d面を塗り替える"%len(target))
hair=np.where(K==2)[0]
fill={}
for i in target:
    d=np.linalg.norm(ctr[hair]-ctr[i],axis=1); fill[i]=np.median(col[hair[np.argsort(d)[:16]]],0)
me.calc_loop_triangles()
tri_of=[[] for _ in range(NF)]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
def raster(tris,mg=0.0):
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
        m[y0:y1+1,x0:x1+1] |= (l1>=-mg)&(l2>=-mg)&(l3>=-mg)
    return m
ts=set(target)
# このモデルは面どうしがテクスチャの同じ画素を共有している（左右で使い回している）ため、
# 他の面が使う画素を避けると何も塗れない。共有先も同じ症状なので、そのまま塗る。
keep=np.zeros((H,W),bool)
out=px.copy(); n=0
for i in target:
    m=raster(tri_of[i],0.05) & (~keep)
    c=[0,1,0] if MARK else fill[i]
    out[m,0]=c[0]; out[m,1]=c[1]; out[m,2]=c[2]; n+=int(m.sum())
print("SH 塗り替えた画素 %d"%n)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("SH 書き出し",OUT)
