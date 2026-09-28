# -*- coding: utf-8 -*-
"""画面で見て「髪の中に浮いている明るい色」を見つけ、その画素のUVを別の描画から読み取って、
   テクスチャ側を髪の色で塗り直す。座標の取り違えが起きない方法。
   実行: blender -b --factory-startup -P screenheal.py -- 入力.glb 元テクスチャ 出力 x,y,z 幅 方位角 画面の範囲sx0,sx1,sy0,sy1 [mark]"""
import bpy, sys, math, os
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]
C=Vector(tuple(map(float,a[3].split(',')))); WID=float(a[4]); AZ=float(a[5])
sb=[float(x) for x in a[6].split(',')]; MARK=len(a)>7 and a[7]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
tex=bpy.data.images.load(TEX); W,H=tex.size
px=np.array(tex.pixels[:],dtype=np.float32).reshape(H,W,4)
gx=(np.arange(W)+0.5)/W; gy=(np.arange(H)+0.5)/H
grad=np.zeros((H,W,4),np.float32); grad[:,:,0]=gx[None,:]; grad[:,:,1]=gy[:,None]; grad[:,:,3]=1.0
gimg=bpy.data.images.new("uvgrad",W,H); gimg.pixels=grad.ravel().tolist()
gimg.colorspace_settings.name="Non-Color"   # 色変換を通さず、UVの値をそのまま読む
nodes=[n for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE']
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(0,0,0)
sc.view_settings.view_transform='Standard'; sc.display.render_aa='OFF'   # 縁のぼかしを切る
N=800; sc.render.resolution_x=N; sc.render.resolution_y=N; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=WID
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
er,ar=0.0,math.radians(AZ); R=20
loc=Vector((C.x+R*math.sin(ar), C.y-R*math.cos(ar), C.z))
cam.location=loc; cam.rotation_euler=(C-loc).to_track_quat('-Z','Y').to_euler()
tmp=os.path.dirname(OUT)
def shoot(im,tag):
    for n in nodes: n.image=im
    p=os.path.join(tmp,"_sc_%s.png"%tag); sc.render.filepath=p; bpy.ops.render.render(write_still=True)
    x=bpy.data.images.load(p); A=np.array(x.pixels[:],dtype=np.float32).reshape(N,N,4); bpy.data.images.remove(x); return A
A=shoot(tex,'a'); B=shoot(gimg,'b')
r,g,b=A[:,:,0],A[:,:,1],A[:,:,2]
hair=(r>0.24)&(g<r*0.78)&(b<r*0.60)
light=(r>0.55)&(g>0.40)&(b>0.30)&(b>r*0.45)&(~hair)   # 髪より明るく青みがある＝眉や肌
# 画面の指定範囲だけ
ys,xs=np.mgrid[0:N,0:N]
sx=(xs+0.5)/N; sy=1.0-(ys+0.5)/N
inbox=(sx>=sb[0])&(sx<=sb[1])&(sy>=sb[2])&(sy<=sb[3])
K=12
U=np.zeros_like(hair); D=np.zeros_like(hair); L=np.zeros_like(hair); Rr=np.zeros_like(hair)
for d in range(1,K+1):
    U[d:,:] |= hair[:-d,:]; D[:-d,:] |= hair[d:,:]
    L[:,d:] |= hair[:,:-d]; Rr[:,:-d] |= hair[:,d:]
votes=U.astype(int)+D.astype(int)+L.astype(int)+Rr.astype(int)
onmodel=(B[:,:,0]>0)|(B[:,:,1]>0)
bad=(inbox&onmodel) if 'all' in sys.argv else (light&(votes>=4)&inbox)
print("SH 範囲内で髪に囲まれた明るい画素 %d"%int(bad.sum()))
mask=np.zeros((H,W),bool)
yy,xx=np.where(bad)
for y,x in zip(yy,xx):
    u=B[y,x,0]; v=B[y,x,1]
    if u<=0 and v<=0: continue
    tx=int(np.clip(u,0,0.9999)*W); ty=int(np.clip(v,0,0.9999)*H)
    mask[max(0,ty-1):ty+2, max(0,tx-1):tx+2]=True
print("SH テクスチャ上 %d 画素"%int(mask.sum()))
def boxf(m,rr):
    c=np.cumsum(np.cumsum(m.astype(np.float32),0),1)
    c=np.pad(c,((1,0),(1,0)))
    return None
def dil(m,rr):
    o=m.copy()
    for _ in range(rr):
        n=o.copy()
        n[1:,:]|=o[:-1,:]; n[:-1,:]|=o[1:,:]; n[:,1:]|=o[:,:-1]; n[:,:-1]|=o[:,1:]
        o=n
    return o
mask=dil(mask,2)
tr,tg,tb=px[:,:,0],px[:,:,1],px[:,:,2]
thair=(tr>0.26)&(tr<0.95)&(tg<tr*0.78)&(tb<tr*0.60)
fill=mask&(~thair)
out=px.copy()
if MARK:
    out[fill,0]=0; out[fill,1]=1; out[fill,2]=0
else:
    known=thair.copy(); cur=out.copy()
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
print("SH 塗り替えた画素 %d"%int(fill.sum()))
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("SH 書き出し",OUT)
