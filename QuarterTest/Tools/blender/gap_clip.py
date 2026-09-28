# -*- coding: utf-8 -*-
"""指定クリップを何コマかサンプリングして、左右の靴の隙間と膝の間隔を測る。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('char'))
act = next((x for x in bpy.data.actions if x.name==CLIP), None)
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = act
f0, f1 = act.frame_range
gi = {g.name: g.index for g in mesh.vertex_groups}
def grp(names): return [gi[n] for n in names if n in gi]
LF=grp(("LeftFoot","LeftToeBase")); RF=grp(("RightFoot","RightToeBase")); LK=grp(("LeftLeg",)); RK=grp(("RightLeg",))
def side_of(groups_l, groups_r):
    s={}
    for v in mesh.data.vertices:
        l=sum(g.weight for g in v.groups if g.group in groups_l); r=sum(g.weight for g in v.groups if g.group in groups_r)
        if max(l,r)>0.5: s[v.index]='L' if l>r else 'R'
    return s
sf=side_of(LF,RF); sk=side_of(LK,RK)
rows=[]
for k in range(8):
    fr = f0 + (f1-f0)*k/8.0
    bpy.context.scene.frame_set(int(round(fr)))
    bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get()
    me=bpy.data.meshes.new_from_object(mesh.evaluated_get(dg)); mw=mesh.matrix_world
    pts=[mw@v.co for v in me.vertices]
    H=max(p.z for p in pts)-min(p.z for p in pts)
    def gap(s):
        L=[pts[i].x for i in s if s[i]=='L']; R=[pts[i].x for i in s if s[i]=='R']
        if not L or not R: return None
        if sum(L)/len(L) > sum(R)/len(R): L,R=R,L
        return (min(R)-max(L))/H*100
    rows.append((gap(sf), gap(sk)))
    bpy.data.meshes.remove(me)
fg=[r[0] for r in rows if r[0] is not None]; kg=[r[1] for r in rows if r[1] is not None]
print("GAPC %-11s 靴の隙間 最小%5.1f%% 平均%5.1f%%   膝の隙間 最小%5.1f%% 平均%5.1f%%"
      % (CLIP, min(fg), sum(fg)/len(fg), min(kg), sum(kg)/len(kg)))
