# -*- coding: utf-8 -*-
"""Idle の先頭で、左右の靴のあいだの隙間を測る。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
arm  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('char'))
act = next((x for x in bpy.data.actions if x.name=='Idle'), None)
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
if act: arm.animation_data.action = act
bpy.context.scene.frame_set(bpy.context.scene.frame_start)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(mesh.evaluated_get(dg))
mw = mesh.matrix_world
pts = [mw @ v.co for v in me.vertices]
z0 = min(p.z for p in pts); z1 = max(p.z for p in pts); H = z1 - z0
foot = [p for p in pts if p.z < z0 + H*0.06]          # 靴の高さ帯
L = [p.x for p in foot if p.x < 0]; R = [p.x for p in foot if p.x > 0]
gap = (min(R) - max(L)) if L and R else 0.0
outer = max(p.x for p in foot) - min(p.x for p in foot)
print("GAP 身長%.4f  靴の隙間%.4f = 身長の%.2f%%  靴の外幅%.4f = %.2f%%"
      % (H, gap, 100*gap/H, outer, 100*outer/H))
