# -*- coding: utf-8 -*-
"""脚の重みの左右が逆になっている頂点を、歩きの「足が前後に離れているコマ」で見つける。
   自分の側の脚の骨より、反対側の脚の骨のほうにずっと近い頂点（複数コマで一致）を「逆」と判定し、
   その素の位置の一覧を JSON に書く（glTF 側で sidepatch.py が付け替える）。
   実行: blender -b --factory-startup -P wrongside.py -- 入力.glb 出力.json クリップ 時刻1,時刻2,..."""
import bpy, sys, json
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP = a[0], a[1], a[2]; FRACS=[float(x) for x in a[3].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
LN=['LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase']; RN=['RightUpLeg','RightLeg','RightFoot','RightToeBase']
nv=len(mesh.data.vertices)
lw=np.zeros(nv); rw=np.zeros(nv)
for v in mesh.data.vertices:
    for g in v.groups:
        if vg[g.group] in LN: lw[v.index]+=g.weight
        elif vg[g.group] in RN: rw[v.index]+=g.weight
cand=np.where((lw+rw)>0.3)[0]
own=np.where(lw>=rw,1,-1)
aw=arm.matrix_world
def P(n): return np.array(aw@arm.pose.bones[n].head)
def segs(names):
    p=[P(n) for n in names]; s=[(p[i],p[i+1]) for i in range(3)]; s.append((p[3],p[3]+(p[3]-p[2])*1.5)); return s
def dist(sg,q):
    best=1e9
    for a_,b_ in sg:
        ab=b_-a_; t=np.clip(np.dot(q-a_,ab)/max(1e-9,np.dot(ab,ab)),0,1); best=min(best,np.linalg.norm(q-(a_+ab*t)))
    return best
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
votes=np.zeros(nv,int)
for fr in FRACS:
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*fr))); bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    pos=np.array([tuple(ev.matrix_world@x.co) for x in me.vertices]); ev.to_mesh_clear()
    SL=segs(LN); SR=segs(RN)
    for v in cand:
        dl=dist(SL,pos[v]); dr=dist(SR,pos[v])
        do,dx=(dl,dr) if own[v]==1 else (dr,dl)
        if dx<0.6*do: votes[v]+=1
wrong=[v for v in cand if votes[v]>=max(2,len(FRACS)-1)]
bind=[tuple(mesh.matrix_world@mesh.data.vertices[v].co) for v in wrong]
print("WS 脚の重みを持つ頂点",len(cand),"個のうち、反対側の骨のほうにずっと近い（逆）と判定",len(wrong),"個  (左→右 %d, 右→左 %d)"%(sum(1 for v in wrong if own[v]==1),sum(1 for v in wrong if own[v]==-1)))
json.dump({'wrong':[[float(x) for x in b] for b in bind]},open(OUT,'w'))
