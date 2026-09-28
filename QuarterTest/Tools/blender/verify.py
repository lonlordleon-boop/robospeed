# -*- coding: utf-8 -*-
"""Blender 側で独立に検証する。腿ウェイトの高さ分布と、アニメが5本残っているか。"""
import bpy, sys
argv = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=argv[0])
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
arm  = next((o for o in bpy.data.objects if o.type=='ARMATURE'), None)
gi = {g.name: g.index for g in mesh.vertex_groups}
LEG = [gi[n] for n in ("LeftUpLeg","RightUpLeg") if n in gi]
mw = mesh.matrix_world
zs = [(mw @ v.co).z for v in mesh.data.vertices]
z0, z1 = min(zs), max(zs); H = z1-z0
print("R HEIGHT %.4f  VERTS %d  ACTIONS %d" % (H, len(mesh.data.vertices), len(bpy.data.actions)))
print("R ACTIONNAMES " + ", ".join(sorted(a.name for a in bpy.data.actions)))
B=20; tot=[0.0]*B; cnt=[0]*B
for i,v in enumerate(mesh.data.vertices):
    b = min(B-1, int((zs[i]-z0)/H*B))
    w = sum(g.weight for g in v.groups if g.group in LEG)
    tot[b]+=w; cnt[b]+=1
for i in range(B):
    if cnt[i]<5: continue
    a = tot[i]/cnt[i]
    if a < 0.001: continue
    print("R BAND %5.0f%%  %.3f  %s" % (100*(i+0.5)/B, a, "#"*int(a*60)))
if arm:
    aw = arm.matrix_world
    for b in ("Hips","Spine","LeftShoulder","Head"):
        if b in arm.data.bones:
            print("R BONE %-13s %5.1f%%" % (b, 100*((aw @ arm.data.bones[b].head_local).z - z0)/H))
