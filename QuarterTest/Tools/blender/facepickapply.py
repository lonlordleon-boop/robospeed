# -*- coding: utf-8 -*-
"""面えらび（Tools/preview/facepick.html）で選んだ面を、髪の色にする。形・骨・重み・動きはそのまま、UV だけ。
   お嬢様（小学生編）は、前髪の毛先に肌色の三角のかけらが残った（v25）。前髪は額と形がつながっていて、
   決まり（明るさ・となりの色・形）で選ぶと額やまぶたまで入った（「間違いが多過ぎる」）。そこで、ユーザーがツールで
   1面ずつクリックして選び、その面に「いちばん近い髪の面」の UV の真ん中を貼る（面えらびの「髪の色で塗る」と同じ見え方）。
   入力の JSON は {"選んだ面": 色をもらう髪の面, ...}（面えらびの window.__FP.donors）。"__chk": [[面, [x,y,z]], ..] を入れると、
   ブラウザと Blender で面の番号が同じ面を指しているか（面の真ん中の位置、glTF の座標）を確かめ、合わなければ直さずに止める。
   --check で、直す面を赤にして頭を4方向から描く（glb は書かない）
   実行: blender -b --factory-startup -P facepickapply.py -- 入力.glb 出力.glb 選んだ面.json [--check 絵.png]"""
import bpy, bmesh, sys, os, math, json, numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
CHECK = opt('--check', None)
SRC, OUT, JS = a[0], a[1], a[2]
pairs = json.load(open(JS, encoding='utf-8')); chk = pairs.pop('__chk', [])
pairs = {int(k): int(v) for k, v in pairs.items()}
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table(); uvL = bm.loops.layers.uv.active
print("FA 面数", len(bm.faces), "選んだ面", len(pairs), "色をもらう面が無い", sum(1 for v in pairs.values() if v < 0))
# 面の番号が同じ面か：glTF (x, y, z) は Blender の (x, −z, y)
bad = 0
for f, (x, y, z) in chk:
    c = me.matrix_world @ bm.faces[f].calc_center_median(); d = (c - Vector((x, -z, y))).length   # 形の座標は 100 倍で、物体の縮尺 0.01 で戻っている
    print("FA 番号の確かめ 面 %d ずれ %.5f m" % (f, d)); bad += d > 1e-3
if bad: raise SystemExit("FA 面の番号がブラウザと合わない。直さずに止める")
def uvc(f): return sum((l[uvL].uv for l in bm.faces[f].loops), Vector((0, 0))) / len(bm.faces[f].loops)
fix = {f: uvc(d).copy() for f, d in pairs.items() if d >= 0}   # 貼り替える前の UV で決める（色をもらう面が選んだ面でも、元の髪の色を使う）
if CHECK:
    img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
    ry, rx = H_ - 4, W_ - 4; px[ry:ry+4, rx:rx+4] = (1, 0, 0, 1); img.pixels = px.ravel()   # 絵の隅に赤を置き、直す面をそこへ向ける
    for f in fix:
        for l in bm.faces[f].loops: l[uvL].uv = ((rx + 2) / W_, (ry + 2) / H_)
    bm.to_mesh(m); m.update()
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
    if arm.animation_data:
        for tr in arm.animation_data.nla_tracks: tr.mute = True
        arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis.identity()
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
    sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
    CW = 400; sc.render.resolution_x = CW; sc.render.resolution_y = CW
    cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.30; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
    C = Vector((0, -0.01, 0.97)); tiles = []; tmp = os.path.join(os.path.dirname(os.path.abspath(CHECK)), "_fa"); os.makedirs(tmp, exist_ok=True)
    for az, el in ((0, 0), (-35, 0), (35, 0), (0, 30)):
        ar_, el_ = math.radians(az), math.radians(el)
        cam.location = (C.x + 5*math.sin(ar_)*math.cos(el_), C.y - 5*math.cos(ar_)*math.cos(el_), C.z + 5*math.sin(el_))
        cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(tmp, "p%d.png" % len(tiles)); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
    buf = np.ones((CW, CW * len(tiles), 4), np.float32)
    for i, p in enumerate(tiles):
        im = bpy.data.images.load(p); buf[:, i * CW:(i + 1) * CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
    sh = bpy.data.images.new("s", CW * len(tiles), CW); sh.pixels = buf.ravel(); sh.filepath_raw = CHECK; sh.file_format = 'PNG'; sh.save(); print("FA 確かめ", CHECK)
else:
    for f, uv in fix.items():
        for l in bm.faces[f].loops: l[uvL].uv = uv
    bm.to_mesh(m); bm.free(); m.update()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
    print("FA 書き出し", OUT, "直した面", len(fix))
