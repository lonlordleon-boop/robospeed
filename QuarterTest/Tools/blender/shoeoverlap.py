# -*- coding: utf-8 -*-
"""靴の内側の縁どうしの横方向の隙間（左靴の内側x − 右靴の内側x）をコマごとに出す。負なら重なっている。
   靴の頂点は足首より下で、重みで左右に分ける。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS = a[1].split(','); N = int(a[2]) if len(a)>2 else 16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
side=np.zeros(len(mesh.data.vertices),int)
for v in mesh.data.vertices:
    l=sum(g.weight for g in v.groups if vg[g.group] in ('LeftFoot','LeftToeBase'))
    r=sum(g.weight for g in v.groups if vg[g.group] in ('RightFoot','RightToeBase'))
    if l>0.6: side[v.index]=1
    elif r>0.6: side[v.index]=-1
def verts():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
arm.animation_data.action=None; bpy.context.view_layer.update(); v=verts(); H=v[:,2].max()-v[:,2].min()
L=v[side==1]; R=v[side==-1]
print("SO 素の姿勢: 左靴 x %.3f..%.3f  右靴 x %.3f..%.3f  靴幅 %.3f  隙間 %.3f (身長 %.3f)"%(L[:,0].min(),L[:,0].max(),R[:,0].min(),R[:,0].max(),L[:,0].max()-L[:,0].min(),L[:,0].min()-R[:,0].max(),H))
for c in CLIPS:
    act=bpy.data.actions.get(c); arm.animation_data.action=act; f0,f1=act.frame_range
    row=[]
    for k in range(N):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
        v=verts(); L=v[side==1]; R=v[side==-1]
        # 前後が重なっている高さ帯だけで比べる（すれ違い中でも前後にずれていれば触れない）
        gap=None
        for zlo in np.arange(0,0.12,0.02):
            Ls=L[(L[:,2]>=zlo*H+v[:,2].min())&(L[:,2]<(zlo+0.02)*H+v[:,2].min())]; Rs=R[(R[:,2]>=zlo*H+v[:,2].min())&(R[:,2]<(zlo+0.02)*H+v[:,2].min())]
            if len(Ls)==0 or len(Rs)==0: continue
            # 前後(y)が重なる範囲だけ
            ylo=max(Ls[:,1].min(),Rs[:,1].min()); yhi=min(Ls[:,1].max(),Rs[:,1].max())
            if yhi<=ylo: continue
            Ls=Ls[(Ls[:,1]>=ylo)&(Ls[:,1]<=yhi)]; Rs=Rs[(Rs[:,1]>=ylo)&(Rs[:,1]<=yhi)]
            if len(Ls)==0 or len(Rs)==0: continue
            g=Ls[:,0].min()-Rs[:,0].max()
            gap=g if gap is None else min(gap,g)
        row.append(gap if gap is not None else 9.99)
    print("SO %-10s 横の隙間(身長%%): "%c + " ".join("%5.1f"%(x/H*100) for x in row))
