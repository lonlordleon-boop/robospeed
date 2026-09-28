# -*- coding: utf-8 -*-
"""テクスチャの絵そのものを整える。頭に使われている画素だけを対象に、
   ・髪の色の中にできた「切れ込み・穴」を埋める（房の途中に肌色が入るのを消す）
   ・肌の上に散った小さな髪色の点を消す
   面ごとに塗り分けると境目がギザギザになるので、絵の形（塗りの領域）に対して処理する。
   実行: blender -b --factory-startup -P texclose.py -- 入力.glb 元テクスチャ 出力テクスチャ 埋める半径 消す半径 [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; RC=int(a[3]) if len(a)>3 else 10; RO=int(a[4]) if len(a)>4 else 6
MARK=len(a)>5 and a[5]=='mark'
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
me.calc_loop_triangles()
def raster(tris,mg=0.0):
    m=np.zeros((H,W),bool)
    for t in tris:
        uv=np.array([uvl[li].uv for li in t.loops],float)
        xs=uv[:,0]*W; ys=uv[:,1]*H
        x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
        y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
        if x1<x0 or y1<y0 or (x1-x0)>500 or (y1-y0)>500: continue
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        dd=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(dd)<1e-12: continue
        l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/dd
        l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/dd
        l3=1-l1-l2
        m[y0:y1+1,x0:x1+1] |= (l1>=-mg)&(l2>=-mg)&(l3>=-mg)
    return m
headtris=[t for t in me.loop_triangles if (mw@me.polygons[t.polygon_index].center).z>neckz]
headmask=raster(headtris,0.2)
print("TC 頭に使われている画素 %d（%.1f%%）"%(headmask.sum(),100*headmask.mean()))
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=((r>0.26)&(r<0.92)&(g<r*0.76)&(b<r*0.58))&headmask
skin=((r>0.62)&(g>0.36)&(b>0.26)&(g<r*0.995)&(b<g*1.18))&headmask
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
dil=box(hair,RC)>0.0
clo=box(dil,RC)>0.999           # 膨張→収縮＝切れ込みを埋める
fill_hair=clo&(~hair)&headmask&(~( (r>0.9)&(g>0.9)&(b>0.9) ))
ero=box(hair,RO)>0.999
opn=box(ero,RO)>0.0             # 収縮→膨張＝小さな点を消す
kill_hair=hair&(~opn)&headmask
print("TC 髪の切れ込みを埋める %d 画素、肌の上の髪色の点を消す %d 画素"%(int(fill_hair.sum()),int(kill_hair.sum())))
hs=np.stack([box(np.where(hair,px[:,:,k],0),RC*2) for k in range(3)],2); hc=np.maximum(box(hair,RC*2),1e-6)
hcol=hs/hc[:,:,None]
ss=np.stack([box(np.where(skin,px[:,:,k],0),RO*3) for k in range(3)],2); sc=np.maximum(box(skin,RO*3),1e-6)
scol=ss/sc[:,:,None]
out=px.copy()
if MARK:
    out[fill_hair,0]=0; out[fill_hair,1]=1; out[fill_hair,2]=0
    out[kill_hair,0]=1; out[kill_hair,1]=0; out[kill_hair,2]=1
else:
    for k in range(3):
        out[:,:,k]=np.where(fill_hair,hcol[:,:,k],out[:,:,k])
        out[:,:,k]=np.where(kill_hair,scol[:,:,k],out[:,:,k])
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("TC 書き出し",OUT)
