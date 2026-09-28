# -*- coding: utf-8 -*-
"""足の骨に付いているのに、その骨から遠く離れた位置にある頂点を探す（正体を知るため）。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIP=a[1]; FR=float(a[2])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
aw=arm.matrix_world
def P(n): return np.array(aw@arm.pose.bones[n].head)
def segd(p,a_,b_):
    ab=b_-a_; t=np.clip(np.dot(p-a_,ab)/max(1e-9,np.dot(ab,ab)),0,1); return np.linalg.norm(p-(a_+ab*t))
bind=np.array([tuple(mesh.matrix_world@v.co) for v in mesh.data.vertices])
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
bpy.context.scene.frame_set(int(round(f0+(f1-f0)*FR))); bpy.context.view_layer.update()
dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
pos=np.array([tuple(ev.matrix_world@v.co) for v in me.vertices]); ev.to_mesh_clear()
for side,(L,F,Tb) in (('Left',('LeftLeg','LeftFoot','LeftToeBase')),('Right',('RightLeg','RightFoot','RightToeBase'))):
    lp,fp,tp=P(L),P(F),P(Tb)
    far=[]
    for v in mesh.data.vertices:
        w=sum(g.weight for g in v.groups if vg[g.group] in (F,Tb))
        if w<0.6: continue
        d=min(segd(pos[v.index],lp,fp),segd(pos[v.index],fp,tp),segd(pos[v.index],tp,tp+(tp-fp)*1.2))
        if d>0.07: far.append((round(d,3),v.index))
    far.sort(reverse=True)
    print("FV %s 足に付いていて骨から7cm以上離れた頂点: %d 個"%(side,len(far)))
    for d,i in far[:6]:
        print("FV   d=%.3f 今(%.3f,%.3f,%.3f) 素(%.3f,%.3f,%.3f) 重み %s"%(d,*pos[i],*bind[i],[(vg[g.group],round(g.weight,2)) for g in mesh.data.vertices[i].groups if g.weight>0.01]))
