# -*- coding: utf-8 -*-
"""1回の起動で、指定クリップを「正面・後ろ・真横」×「複数の時刻」で描き、1枚にまとめる。
   実行: blender -b --factory-startup -P views.py -- 入力.glb 出力.png クリップ名 時刻1,時刻2,...
   時刻はクリップ長に対する割合（0.0〜1.0）。"""
import bpy, sys, math, os
from mathutils import Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP = a[0], a[1], a[2]
FRACS = [float(x) for x in a[3].split(',')] if len(a) > 3 else [0.0, 0.25, 0.5, 0.75]
VIEWS = [("front", 0, 4), ("back", 180, 4), ("side", 90, 4)]
CW, CH = 320, 440

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
arm  = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
act = bpy.data.actions.get(CLIP)
print("ACTIONS", [x.name for x in bpy.data.actions])
if act is None:
    print("CLIP NOT FOUND", CLIP); sys.exit(0)
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = act
f0, f1 = act.frame_range

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
sc.render.resolution_x = CW; sc.render.resolution_y = CH
sc.render.image_settings.file_format = 'PNG'
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam

# 枠は骨から決める（頭のてっぺん〜つま先）。全コマ同じ枠にする
sc.frame_set(int(f0)); bpy.context.view_layer.update()
aw = arm.matrix_world
def bz(n): return (aw @ arm.pose.bones[n].head).z if n in arm.pose.bones else 0.0
top = bz("head_end"); low = min(bz("LeftToeBase"), bz("RightToeBase"))
H = max(1e-4, (top - low) * 1.20); cz = (top + low) / 2
cd.ortho_scale = H * 1.05

tiles = []
tmpdir = os.path.join(os.path.dirname(OUT), "_tiles"); os.makedirs(tmpdir, exist_ok=True)
for fi, fr in enumerate(FRACS):
    sc.frame_set(int(round(f0 + (f1 - f0) * fr))); bpy.context.view_layer.update()
    # 腰を中心に置く（クリップの前進移動を消す）
    hp = aw @ arm.pose.bones["Hips"].head
    for vi, (vname, az, el) in enumerate(VIEWS):
        er, ar = math.radians(el), math.radians(az); R = H * 20
        cam.location = (hp.x + R*math.cos(er)*math.sin(ar), hp.y - R*math.cos(er)*math.cos(ar), cz + R*math.sin(er))
        d = Vector((hp.x, hp.y, cz)) - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(tmpdir, "t_%d_%d.png" % (fi, vi))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append((fi, vi, p))

# 1枚にまとめる（列＝時刻、行＝角度）
W = CW * len(FRACS); Hh = CH * len(VIEWS)
sheet = bpy.data.images.new("sheet", W, Hh)
buf = [1.0] * (W * Hh * 4)
for fi, vi, p in tiles:
    img = bpy.data.images.load(p); px = img.pixels[:]
    for y in range(CH):
        srow = y * CW * 4
        drow = ((Hh - 1 - (vi * CH + (CH - 1 - y))) * W + fi * CW) * 4
        buf[drow:drow + CW*4] = px[srow:srow + CW*4]
    bpy.data.images.remove(img)
sheet.pixels = buf
sheet.filepath_raw = OUT; sheet.file_format = 'PNG'; sheet.save()
print("SHEET", OUT, "列=時刻", FRACS, "行=正面/後ろ/真横")
