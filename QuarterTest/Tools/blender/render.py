# -*- coding: utf-8 -*-
"""GLB を読み込んで正射影で描く。Unity と見比べるための独立した絵。
   実行: blender -b --factory-startup -P render.py -- 入力.glb 出力.png"""
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = argv[0], argv[1]
AZ = float(argv[2]) if len(argv) > 2 else 45.0
EL = float(argv[3]) if len(argv) > 3 else 30.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

# 大きさを測る（Blender は Z が高さ）
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
mw = mesh.matrix_world
zs = [(mw @ v.co).z for v in mesh.data.vertices]
xs = [(mw @ v.co).x for v in mesh.data.vertices]
ys = [(mw @ v.co).y for v in mesh.data.vertices]
z0, z1 = min(zs), max(zs); H = z1 - z0
cx, cy, cz = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (z0+z1)/2

cam_data = bpy.data.cameras.new("cam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = H * 1.25
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
er, ar = math.radians(EL), math.radians(AZ)
R = H * 10
cam.location = (cx + R*math.cos(er)*math.sin(ar), cy - R*math.cos(er)*math.cos(ar), cz + R*math.sin(er))
d = Vector((cx, cy, cz)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new("w")
sc.world.use_nodes = False
sc.world.color = (1, 1, 1)
sc.render.resolution_x = 700
sc.render.resolution_y = 950
sc.render.filepath = OUT
sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT, "H=%.4f" % H)
