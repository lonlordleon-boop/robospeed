# -*- coding: utf-8 -*-
"""左右の靴を頂点グループで分けて、それぞれの範囲と隙間を測る。"""
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

gi = {g.name: g.index for g in mesh.vertex_groups}
LG = [gi[n] for n in ("LeftFoot","LeftToeBase") if n in gi]
RG = [gi[n] for n in ("RightFoot","RightToeBase") if n in gi]
side = {}
for v in mesh.data.vertices:
    l = sum(g.weight for g in v.groups if g.group in LG)
    r = sum(g.weight for g in v.groups if g.group in RG)
    if max(l, r) > 0.5: side[v.index] = 'L' if l > r else 'R'

dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(mesh.evaluated_get(dg))
mw = mesh.matrix_world
pts = [mw @ v.co for v in me.vertices]
z0 = min(p.z for p in pts); z1 = max(p.z for p in pts); H = z1 - z0
Lx = [pts[i].x for i in side if side[i]=='L' and i < len(pts)]
Rx = [pts[i].x for i in side if side[i]=='R' and i < len(pts)]
if not Lx or not Rx:
    print("NOFOOT"); sys.exit(0)
# 左足は -X 側か +X 側か、中心で判定
if sum(Lx)/len(Lx) > sum(Rx)/len(Rx): Lx, Rx = Rx, Lx
gap = min(Rx) - max(Lx)
print("GAP2 身長%.4f  左足 %.3f〜%.3f  右足 %.3f〜%.3f  隙間%.4f = 身長の%.2f%%"
      % (H, min(Lx), max(Lx), min(Rx), max(Rx), gap, 100*gap/H))
