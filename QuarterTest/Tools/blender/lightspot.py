# -*- coding: utf-8 -*-
"""テクスチャの中で「まわりが髪色なのに、そこだけ白っぽい」画素を消す（髪の上に乗った眉の筋を取る）。
   実行: blender -b --factory-startup -P lightspot.py -- 入力.glb 元テクスチャ 出力 半径 髪の割合 明るさ [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; R=int(a[3]); FR=float(a[4]); LT=float(a[5]); MARK=len(a)>6 and a[6]=='mark'
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
uvl=me.uv_layers.active.data; me.calc_loop_triangles()
def raster(tris,mg=0.2):
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
head=raster([t for t in me.loop_triangles if (mw@me.polygons[t.polygon_index].center).z>neckz])
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=((r>0.28)&(r<0.95)&(g<r*0.80)&(b<r*0.62))&head
light=(np.minimum(np.minimum(r,g),b)>LT)&head&(~hair)
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
bad=light&(box(hair,R)>=FR)
print("LS 頭の画素 %d、白っぽく髪に囲まれた画素 %d"%(int(head.sum()),int(bad.sum())))
def dil(m,rr):
    o=m.copy()
    for _ in range(rr):
        n=o.copy(); n[1:,:]|=o[:-1,:]; n[:-1,:]|=o[1:,:]; n[:,1:]|=o[:,:-1]; n[:,:-1]|=o[:,1:]; o=n
    return o
fill=dil(bad,2)&head&(~hair)
out=px.copy()
if MARK:
    out[fill,0]=0; out[fill,1]=1; out[fill,2]=0
else:
    known=hair.copy(); cur=out.copy()
    for _ in range(40):
        s=np.zeros((H,W,4),np.float32); cnt=np.zeros((H,W),np.float32)
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            sh=np.roll(np.roll(cur,dy,axis=0),dx,axis=1)
            kn=np.roll(np.roll(known,dy,axis=0),dx,axis=1).astype(np.float32)
            s+=sh*kn[:,:,None]; cnt+=kn
        f=fill&(~known)&(cnt>0)
        if not f.any(): break
        cur[f]=(s[f]/cnt[f][:,None]); known|=f
    out=np.where(fill[:,:,None], cur, out)
print("LS 塗り替えた画素 %d"%int(fill.sum()))
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("LS 書き出し",OUT)
