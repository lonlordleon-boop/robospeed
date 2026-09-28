# -*- coding: utf-8 -*-
"""頭のアップを、指定の角度・複数の時刻で並べて描く（髪の崩れ探し用）。
   実行: blender -b --factory-startup -P headshot.py -- 入力.glb 出力.png クリップ 方位角 仰角 時刻1,時刻2,..."""
import bpy, sys, math, os
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP, AZ, EL = a[0], a[1], a[2], float(a[3]), float(a[4])
FRACS = [float(x) for x in a[5].split(',')]
CW, CH = 400, 400
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
act = bpy.data.actions.get(CLIP)
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action = act; f0, f1 = act.frame_range
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
sc.render.resolution_x = CW; sc.render.resolution_y = CH; sc.render.image_settings.file_format = 'PNG'
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
aw = arm.matrix_world
tiles=[]; tmpdir=os.path.join(os.path.dirname(OUT), "_tiles"); os.makedirs(tmpdir, exist_ok=True)
for fi, fr in enumerate(FRACS):
    sc.frame_set(int(round(f0 + (f1 - f0) * fr))); bpy.context.view_layer.update()
    hp = aw @ arm.pose.bones["Head"].head; top = aw @ arm.pose.bones["head_end"].head
    low = min((aw @ arm.pose.bones[n].head).z for n in ("LeftToeBase","RightToeBase")); Hh = top.z - low
    c = Vector((hp.x, hp.y, hp.z + Hh*0.16)); cd.ortho_scale = Hh * 0.8
    er, ar = math.radians(EL), math.radians(AZ); R = 20
    cam.location = (c.x + R*math.cos(er)*math.sin(ar), c.y - R*math.cos(er)*math.cos(ar), c.z + R*math.sin(er))
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmpdir, "h_%d.png" % fi); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
W = CW * len(FRACS); sheet = bpy.data.images.new("sheet", W, CH); buf = [1.0] * (W * CH * 4)
for fi, p in enumerate(tiles):
    img = bpy.data.images.load(p); px = img.pixels[:]
    for y in range(CH):
        buf[(y * W + fi * CW) * 4:(y * W + fi * CW) * 4 + CW * 4] = px[y * CW * 4:(y + 1) * CW * 4]
    bpy.data.images.remove(img)
sheet.pixels = buf; sheet.filepath_raw = OUT; sheet.file_format = 'PNG'; sheet.save(); print("HEAD", OUT)
