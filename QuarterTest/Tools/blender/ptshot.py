# 指定の点のまわりを、素の姿勢で複数の向きから拡大して描く（絵の色のまま）
import bpy, sys, math, os, numpy as np
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
C = Vector(tuple(map(float, a[2].split(',')))); SCALE = float(a[3]); AZS = [float(x) for x in a[4].split(',')]
EL = float(a[5]) if len(a) > 5 else 0.0
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
CW = 400; sc.render.resolution_x = CW; sc.render.resolution_y = CW
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = SCALE
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
tiles = []; tmp = os.path.join(os.path.dirname(OUT), "_pt"); os.makedirs(tmp, exist_ok=True)
for az in AZS:
    ar = math.radians(az); el = math.radians(EL)
    cam.location = (C.x + 5*math.sin(ar)*math.cos(el), C.y - 5*math.cos(ar)*math.cos(el), C.z + 5*math.sin(el))
    cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmp, "p%d.png" % len(tiles)); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
buf = np.ones((CW, CW*len(tiles), 4), np.float32)
for i, p in enumerate(tiles):
    im = bpy.data.images.load(p); buf[:, i*CW:(i+1)*CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
sh = bpy.data.images.new("s", CW*len(tiles), CW); sh.pixels = buf.ravel(); sh.filepath_raw = OUT; sh.file_format = 'PNG'; sh.save()
