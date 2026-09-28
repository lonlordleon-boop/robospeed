# -*- coding: utf-8 -*-
"""描いた絵の中で「上下を髪色に挟まれた肌色」の画素を機械的に見つけ、
   そこに写っている面を割り出して、テクスチャを髪の色に塗り替える。
   頬に垂れた髪の房の途中に肌色が乗っている箇所を、目分量ではなく画像から特定するためのもの。
   実行: blender -b --factory-startup -P strandheal.py -- 入力.glb 元テクスチャ 出力テクスチャ x,y,z 幅 方位角;方位角... [mark]"""
import bpy, sys, math, os
from mathutils import Vector
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]
C=Vector(tuple(map(float,a[3].split(',')))); WID=float(a[4])
AZS=[float(x) for x in a[5].split(';')]; LIMR=float(a[6]); MARK=len(a)>7 and a[7]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
for m in bpy.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE': n.image=img
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
N=500; sc.render.resolution_x=N; sc.render.resolution_y=N; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=WID
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
mwi=mesh.matrix_world.inverted()
tmp=os.path.join(os.path.dirname(OUT),"_sh"); os.makedirs(tmp,exist_ok=True)
target=set()
for AZ in AZS:
    er,ar=0.0,math.radians(AZ); R=20
    loc=Vector((C.x+R*math.sin(ar), C.y-R*math.cos(ar), C.z))
    fwd=(C-loc).normalized(); right=fwd.cross(Vector((0,0,1))).normalized(); up=right.cross(fwd).normalized()
    cam.location=loc; cam.rotation_euler=(C-loc).to_track_quat('-Z','Y').to_euler()
    p=os.path.join(tmp,"r_%d.png"%int(AZ)); sc.render.filepath=p; bpy.ops.render.render(write_still=True)
    im=bpy.data.images.load(p); A=np.array(im.pixels[:],dtype=np.float32).reshape(N,N,4)[:,:,:3]
    bpy.data.images.remove(im)
    r,g,b=A[:,:,0],A[:,:,1],A[:,:,2]
    hairm=(r>0.25)&(g<r*0.75)&(b<r*0.55)
    skinm=((r>0.64)&(g>0.38)&(b>0.28)&(g<r*0.99)&(b<g*1.15))|((r>0.70)&(g>0.60)&(b>0.55))  # 白っぽい抜けも対象
    K=26
    up_h=np.zeros_like(hairm); dn_h=np.zeros_like(hairm)
    for d in range(1,K+1):
        up_h[d:,:] |= hairm[:-d,:]; dn_h[:-d,:] |= hairm[d:,:]
    bad=skinm&up_h&dn_h
    ys,xs=np.where(bad)
    cnt=0
    d3=(mwi.to_3x3()@fwd).normalized()
    for y,x in zip(ys,xs):
        sx=(x+0.5)/N; sy=1.0-(y+0.5)/N     # 画像は下から上
        o=mwi@(loc + right*((sx-0.5)*WID) + up*((0.5-sy)*WID))
        hit,pp,nn,fi = mesh.ray_cast(o,d3)
        if hit: target.add(fi); cnt+=1
    print("SD 方位角%3.0f: 上下を髪に挟まれた肌色 %d画素 → 面 %d"%(AZ,len(ys),cnt))
# 指定した場所のまわりだけを対象にする（襟など別の場所を巻き込まないため）
mwv=mesh.matrix_world
target=sorted(i for i in target if (np.linalg.norm(np.array(tuple(mwv@me.polygons[i].center))-np.array([C.x,C.y,C.z]))<LIMR))
print("SD 対象の面 %d"%len(target))
NF=len(me.polygons); col=np.zeros((NF,3)); ctr=np.zeros((NF,3)); K2=np.zeros(NF,int)
mw=mesh.matrix_world
for f in me.polygons:
    uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    c=px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]; col[f.index]=c; ctr[f.index]=tuple(mw@f.center)
    r,g,b=c
    K2[f.index]= 1 if (r>0.64 and g>0.38 and b>0.28 and g<r*0.99 and b<g*1.15) else (2 if (r>0.28 and g<r*0.75 and b<r*0.55) else 0)
hair=np.where(K2==2)[0]
me.calc_loop_triangles()
tri_of=[[] for _ in range(NF)]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
out=px.copy(); n=0
for i in target:
    d=np.linalg.norm(ctr[hair]-ctr[i],axis=1); fc=np.median(col[hair[np.argsort(d)[:16]]],0)
    for t in tri_of[i]:
        uv=np.array([uvl[li].uv for li in t.loops],float)
        xs=uv[:,0]*W; ys2=uv[:,1]*H
        x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
        y0=max(0,int(np.floor(ys2.min()))-1); y1=min(H-1,int(np.ceil(ys2.max()))+1)
        if x1<x0 or y1<y0 or (x1-x0)>400 or (y1-y0)>400: continue
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        dd=(ys2[1]-ys2[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys2[0]-ys2[2])
        if abs(dd)<1e-12: continue
        l1=((ys2[1]-ys2[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys2[2]))/dd
        l2=((ys2[2]-ys2[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys2[2]))/dd
        l3=1-l1-l2; m=(l1>=-0.1)&(l2>=-0.1)&(l3>=-0.1)
        c2=[0,1,0] if MARK else fc
        sub=out[y0:y1+1,x0:x1+1]
        for k in range(3): sub[:,:,k]=np.where(m,c2[k],sub[:,:,k])
        out[y0:y1+1,x0:x1+1]=sub; n+=int(m.sum())
print("SD 塗り替えた画素 %d"%n)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("SD 書き出し",OUT)
