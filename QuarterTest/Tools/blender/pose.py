# -*- coding: utf-8 -*-
"""指定のアニメの指定フレームで描く。Unity の書き出しと同じ条件にする。
   実行: blender -b --factory-startup -P pose.py -- 入力.glb 出力.png クリップ名 時刻秒 方位 伏角"""
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP, T = a[0], a[1], a[2], float(a[3])
AZ, EL = float(a[4]), float(a[5])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')

act = bpy.data.actions.get(CLIP)
print("ACTIONS", [x.name for x in bpy.data.actions])
if act is None:
    print("CLIP NOT FOUND", CLIP); sys.exit(0)
if arm.animation_data is None: arm.animation_data_create()
# NLA を止めて、指定のアクションだけを効かせる
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = act
fps = bpy.context.scene.render.fps
bpy.context.scene.frame_set(int(round(T * fps)) + int(act.frame_range[0]))
bpy.context.view_layer.update()

dg = bpy.context.evaluated_depsgraph_get()
ev = mesh.evaluated_get(dg)
me = ev.to_mesh()
mw = mesh.matrix_world
zs = [(mw @ v.co).z for v in me.vertices]
xs = [(mw @ v.co).x for v in me.vertices]
ys = [(mw @ v.co).y for v in me.vertices]
z0, z1 = min(zs), max(zs)
cx, cy, cz = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (z0+z1)/2
H = z1 - z0
print("POSE_HEIGHT %.4f" % H)
ev.to_mesh_clear()

cd = bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale = 1.7321*0.62*2
cam = bpy.data.objects.new("c", cd); bpy.context.scene.collection.objects.link(cam)
er, ar = math.radians(EL), math.radians(AZ); R = 20
cam.location = (cx + R*math.cos(er)*math.sin(ar), cy - R*math.cos(er)*math.cos(ar), z0 + 1.7321*0.50)
d = Vector((cx, cy, z0 + 1.7321*0.50)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera = cam
sc = bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'; sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.render.resolution_x=700; sc.render.resolution_y=950
sc.render.filepath=OUT; sc.render.image_settings.file_format='PNG'
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT)
