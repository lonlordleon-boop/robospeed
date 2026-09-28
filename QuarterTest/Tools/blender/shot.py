# クリップのコマを、指定の向きから絵の色で描いて横に並べる
# 実行: blender -b -P shot.py -- in.glb out.png CLIP f1,f2,.. az el scale cz [cx]
import bpy, sys, math, os, numpy as np
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT, CLIP = a[0], a[1], a[2]
FRS = [int(x) for x in a[3].split(',')]; AZ = float(a[4]); EL = float(a[5]); SCALE = float(a[6]); CZ = float(a[7])
CX = float(a[8]) if len(a) > 8 else 0.0
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH')
print("BFC", [ (m.name, m.use_backface_culling) for m in me.data.materials])
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
act = next(x for x in bpy.data.actions if x.name.startswith(CLIP)); arm.animation_data.action = act
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_backface_culling = False   # キャラクターツール（preview.html）は面の裏も描く（DoubleSide）ので合わせる
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
CW = 420; CH = int(CW * 1.6); sc.render.resolution_x = CW; sc.render.resolution_y = CH
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = SCALE
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
tmp = os.path.join(os.path.dirname(OUT), "_sh"); os.makedirs(tmp, exist_ok=True); tiles = []
for f in FRS:
    sc.frame_set(f); bpy.context.view_layer.update()
    hp = arm.matrix_world @ arm.pose.bones['Hips'].head
    C = Vector((hp.x + CX, hp.y, CZ))
    ar = math.radians(AZ); el = math.radians(EL)
    cam.location = (C.x + 5*math.sin(ar)*math.cos(el), C.y - 5*math.cos(ar)*math.cos(el), C.z + 5*math.sin(el))
    cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmp, "p%d.png" % len(tiles)); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
buf = np.ones((CH, CW*len(tiles), 4), np.float32)
for i, p in enumerate(tiles):
    im = bpy.data.images.load(p); buf[:, i*CW:(i+1)*CW] = np.array(im.pixels[:], np.float32).reshape(CH, CW, 4)
sh = bpy.data.images.new("s", CW*len(tiles), CH); sh.pixels = buf.ravel(); sh.filepath_raw = OUT; sh.file_format = 'PNG'; sh.save()
print("SHOT", OUT)
