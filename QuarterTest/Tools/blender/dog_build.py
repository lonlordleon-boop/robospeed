# -*- coding: utf-8 -*-
"""公園に入ってくる犬（緊急ミッション用）を、球や円柱の組み合わせで作る。
   ・elder_build.py と同じ作り方（ローポリ調・無地の色・骨なし）。動かすのは使う側（park12.html）。
   ・大きさは公園の世界の単位そのまま。足元が原点、前は -Y（キャラと同じ向き）。
     背の高さ 0.62・鼻先まで 0.95 ほど。女の子（リボンまで1.73）の腰より少し下。
   実行: blender -b --factory-startup -P dog_build.py -- 出力フォルダ
   出力: dog.glb と、確かめ用の絵 check_dog.png"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(a[0])
os.makedirs(os.path.join(OUT, 'parts'), exist_ok=True)

FUR = (0.80, 0.60, 0.36); BELLY = (0.97, 0.94, 0.88); DARK = (0.16, 0.13, 0.12); TONGUE = (0.88, 0.45, 0.48)

def lin(c):   # 見た目の色（sRGB）を、材質に渡す直線の値へ
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def mat(rgb):
    name = 'm_%.2f_%.2f_%.2f' % rgb
    m = bpy.data.materials.get(name)
    if m: return m
    v = tuple(lin(c) for c in rgb)
    m = bpy.data.materials.new(name); m.diffuse_color = (*v, 1); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*v, 1); b.inputs['Roughness'].default_value = 0.85
    return m

PARTS = []
def keep(o, rgb):
    o.data.materials.append(mat(rgb))
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.shade_smooth()
    PARTS.append(o); return o
def sphere(c, r, rgb, scale=(1, 1, 1), seg=24, ring=16):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=c, segments=seg, ring_count=ring)
    o = bpy.context.active_object; o.scale = scale; return keep(o, rgb)
def tube(p, q, r, rgb, r2=None, seg=14):
    p, q = Vector(p), Vector(q); d = q - p
    if r2 is None: bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(p + q) / 2, vertices=seg)
    else: bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=d.length, location=(p + q) / 2, vertices=seg)
    o = bpy.context.active_object
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.normalized().to_track_quat('Z', 'Y')
    return keep(o, rgb)
def torus(c, R, r, rgb, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=c, rotation=rot, major_segments=20, minor_segments=8)
    return keep(bpy.context.active_object, rgb)
def cone(c, r, h, rgb, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=0, depth=h, location=c, rotation=rot, vertices=12)
    return keep(bpy.context.active_object, rgb)

bpy.ops.wm.read_factory_settings(use_empty=True)

# 柴犬のような形。胴は低めで長く、頭は小さめ、鼻づらを長く、耳は立ち耳、しっぽは背中の上へ巻く
# 胴・胸・尻
sphere((0, 0.02, 0.40), 1.0, FUR, scale=(0.125, 0.26, 0.125), seg=28, ring=18)
sphere((0, -0.20, 0.40), 0.135, FUR, seg=24, ring=16)                      # 胸
sphere((0, 0.24, 0.42), 0.125, FUR, seg=24, ring=16)                       # 尻
sphere((0, -0.06, 0.32), 1.0, BELLY, scale=(0.095, 0.20, 0.055))           # 白いお腹
# 首と頭（頭は胸より少し前・上）
tube((0, -0.19, 0.48), (0, -0.30, 0.60), 0.085, FUR)
sphere((0, -0.33, 0.62), 0.115, FUR, seg=28, ring=18)
# 鼻づら（長め）・鼻・白い口もと
tube((0, -0.38, 0.605), (0, -0.50, 0.585), 0.055, FUR, r2=0.042)
sphere((0, -0.44, 0.565), 1.0, BELLY, scale=(0.045, 0.06, 0.028))
sphere((0, -0.515, 0.592), 0.026, DARK)
sphere((0, -0.47, 0.545), 1.0, TONGUE, scale=(0.025, 0.035, 0.015))        # 少し出した舌
# 立ち耳（三角）と目、柴犬らしい眉の点
for s in (1, -1):
    cone((s * 0.068, -0.30, 0.735), 0.048, 0.11, FUR, rot=(math.radians(-8), math.radians(s * 14), 0))
    sphere((s * 0.055, -0.405, 0.645), 0.021, DARK)
    sphere((s * 0.058, -0.375, 0.695), 1.0, BELLY, scale=(0.022, 0.016, 0.012))
# 脚（前はまっすぐ、後ろは少し後ろへ）と白い足先
for s in (1, -1):
    tube((s * 0.072, -0.17, 0.36), (s * 0.072, -0.18, 0.06), 0.038, FUR, r2=0.032)
    sphere((s * 0.072, -0.20, 0.045), 1.0, BELLY, scale=(0.042, 0.06, 0.035))
    tube((s * 0.082, 0.16, 0.37), (s * 0.082, 0.19, 0.06), 0.042, FUR, r2=0.034)
    sphere((s * 0.082, 0.17, 0.045), 1.0, BELLY, scale=(0.046, 0.06, 0.035))
# 背中の上へ巻くしっぽ（球を弧に並べる）
for k in range(13):
    a_ = math.radians(205 - k * 21)
    sphere((0, 0.27 + 0.10 * math.cos(a_), 0.60 + 0.10 * math.sin(a_)), 0.048 - k * 0.0018, FUR if k < 10 else BELLY, seg=16, ring=10)
# 赤い首輪
torus((0, -0.24, 0.535), 0.088, 0.016, (0.78, 0.22, 0.22), rot=(math.radians(76), 0, 0))

# ひとつにまとめる
bpy.ops.object.select_all(action='DESELECT')
for o in PARTS: o.select_set(True)
body = PARTS[0]; bpy.context.view_layer.objects.active = body
bpy.ops.object.join(); body.name = 'dog'
V = np.array([tuple(body.matrix_world @ v.co) for v in body.data.vertices])
print("DB 犬: 頂点 %d 高さ %.3f 前後 %.3f〜%.3f 幅 %.3f" % (len(V), V[:, 2].max(), V[:, 1].min(), V[:, 1].max(), V[:, 0].max() - V[:, 0].min()))

# ---- 確かめの絵 ----
sc = bpy.context.scene
cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_shadows = True
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
sc.render.resolution_x = 320; sc.render.resolution_y = 260
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0))
bpy.context.active_object.data.materials.append(mat((0.80, 0.78, 0.72)))
files = []
for az in (0, 90, 35):
    cam_d.ortho_scale = 1.3
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(12)), -math.cos(math.radians(az)) * math.cos(math.radians(12)), math.sin(math.radians(12))))
    cam.location = Vector((0, -0.05, 0.38)) + d * 6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    fn = os.path.join(OUT, 'parts', 'dog_%d.png' % az); files.append(fn)
    sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
imgs = [bpy.data.images.load(f) for f in files]
w_, h_ = imgs[0].size
buf = np.ones((h_, w_ * len(imgs), 4), dtype=np.float32)
for k, im in enumerate(imgs):
    px = np.empty(w_ * h_ * 4, dtype=np.float32); im.pixels.foreach_get(px)
    buf[:, k * w_:(k + 1) * w_] = px.reshape(h_, w_, 4)
o_ = bpy.data.images.new('j', w_ * len(imgs), h_); o_.pixels.foreach_set(buf.ravel())
o_.filepath_raw = os.path.join(OUT, 'check_dog.png'); o_.file_format = 'PNG'; o_.save()

# ---- 書き出し ----
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active = body
path = os.path.join(OUT, 'dog.glb')
bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                          export_animations=False, export_skins=False, export_yup=True)
print("DB 書き出し", path, os.path.getsize(path))
