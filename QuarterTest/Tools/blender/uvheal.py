# -*- coding: utf-8 -*-
"""見た目で見つけた色の間違いを、テクスチャの正確な位置へ変換して直す。
   同じカメラで「普通の絵」と「UV座標を色にした絵」の2枚を描き、
   間違っている画素の UV を読み取って、その画素だけをまわりの正しい色で塗る。
   面ごとに塗らないので、境目がギザギザにならない。
   実行: blender -b --factory-startup -P uvheal.py -- 入力.glb 元テクスチャ 出力テクスチャ x,y,z 幅 方位角,仰角;... 種類 [mark]
        種類 hair=髪の中の肌色を髪色に  skin=肌の上の髪色を肌色に"""
import bpy, sys, math, os
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]
C=Vector(tuple(map(float,a[3].split(',')))); WID=float(a[4])
VIEWS=[tuple(map(float,s.split(','))) for s in a[5].split(';')]; KIND=a[6]
MARK=len(a)>7 and a[7]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
tex=bpy.data.images.load(TEX); W,H=tex.size
px=np.array(tex.pixels[:],dtype=np.float32).reshape(H,W,4)
# UV を色にしたテクスチャ
gx=(np.arange(W)+0.5)/W; gy=(np.arange(H)+0.5)/H
grad=np.zeros((H,W,4),np.float32); grad[:,:,0]=gx[None,:]; grad[:,:,1]=gy[:,None]; grad[:,:,3]=1.0
gimg=bpy.data.images.new("uvgrad",W,H); gimg.pixels=grad.ravel().tolist()
nodes=[n for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE']
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.view_settings.view_transform='Standard'; sc.render.film_transparent=True; sc.render.image_settings.color_mode='RGBA'
N=520; sc.render.resolution_x=N; sc.render.resolution_y=N; sc.render.image_settings.file_format='PNG'
sc.render.image_settings.color_depth='16'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=WID
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
tmp=os.path.join(os.path.dirname(OUT),"_uh"); os.makedirs(tmp,exist_ok=True)
def shoot(im,tag,i):
    for n in nodes: n.image=im
    p=os.path.join(tmp,"%s_%d.png"%(tag,i)); sc.render.filepath=p; bpy.ops.render.render(write_still=True)
    x=bpy.data.images.load(p); A=np.array(x.pixels[:],dtype=np.float32).reshape(N,N,4); bpy.data.images.remove(x); return A
mask=np.zeros((H,W),bool); total=0
for i,(AZ,EL) in enumerate(VIEWS):
    er,ar=math.radians(EL),math.radians(AZ); R=20
    loc=Vector((C.x+R*math.cos(er)*math.sin(ar), C.y-R*math.cos(er)*math.cos(ar), C.z+R*math.sin(er)))
    cam.location=loc; cam.rotation_euler=(C-loc).to_track_quat('-Z','Y').to_euler()
    A=shoot(tex,'a',i); Bv=shoot(gimg,'b',i)
    r,g,b=A[:,:,0],A[:,:,1],A[:,:,2]
    solid=A[:,:,3]>0.5                          # 背景を除く
    hairm=(r>0.24)&(g<r*0.78)&(b<r*0.60)&solid
    skinm=(((r>0.60)&(g>0.34)&(b>0.24)&(g<r*0.995)&(b<g*1.20))|((r>0.72)&(g>0.60)&(b>0.55)))&solid
    src = skinm if KIND=='hair' else hairm
    other = hairm if KIND=='hair' else skinm
    K=10
    L=np.zeros_like(other); Rr=np.zeros_like(other); U=np.zeros_like(other); D=np.zeros_like(other)
    for d in range(1,K+1):
        U[d:,:] |= other[:-d,:]; D[:-d,:] |= other[d:,:]
        L[:,d:] |= other[:,:-d]; Rr[:,:-d] |= other[:,d:]
    votes=U.astype(int)+D.astype(int)+L.astype(int)+Rr.astype(int)
    bad=src&(votes>=3)
    ys,xs=np.where(bad); total+=len(ys)
    for y,x in zip(ys,xs):
        u=Bv[y,x,0]; v=Bv[y,x,1]
        if u<=0 and v<=0: continue
        tx=int(np.clip(u,0,0.9999)*W); ty=int(np.clip(v,0,0.9999)*H)
        mask[max(0,ty-1):ty+2, max(0,tx-1):tx+2]=True
    print("UH 角度%.0f,%.0f: 間違い %d画素"%(AZ,EL,len(ys)))
print("UH 合計 %d画素 → テクスチャ上 %d画素"%(total,int(mask.sum())))
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
mask=box(mask,2)>0.0
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
good=((r>0.26)&(g<r*0.76)&(b<r*0.58)) if KIND=='hair' else ((r>0.62)&(g>0.36)&(b>0.26)&(g<r*0.995)&(b<g*1.18))
good=good&(~mask)
RR=18
gs=np.stack([box(np.where(good,px[:,:,k],0),RR) for k in range(3)],2); gc=np.maximum(box(good,RR),1e-6)
gcol=gs/gc[:,:,None]
out=px.copy()
if MARK:
    out[mask,0]=0; out[mask,1]=1; out[mask,2]=0
else:
    for k in range(3): out[:,:,k]=np.where(mask,gcol[:,:,k],out[:,:,k])
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("UH 書き出し",OUT)
