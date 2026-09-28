# -*- coding: utf-8 -*-
"""生成したシーソーの男の子（座った姿の置物）を、公園のシーソーにそのまま乗せられる向き・大きさにそろえる。

   老夫婦（elderfit.py）と同じく骨は入れない。違いは原点の置き方で、
   老夫婦は「足元」が原点（ベンチの前の地面に置く）だが、男の子は板にまたがるので「お尻」を原点にする。
   park12.html は、原点を子の座る位置（板の上面 SS_TOP、端から SS_SEAT）に置き、真ん中を向かせるだけ。

   やっていること：
   1. glb を読み、メッシュを1つにまとめる（Meshy の出力は前が -Y・上が +Z）
   2. お尻の位置を探す：左右の真ん中（|x| が幅の 4% 以内）で一番低い所。脚は左右に開いて垂れているので、
      真ん中の一番低い所が、板に乗る股の下になる
   3. 「お尻から頭のてっぺんまで」が指定の高さになるよう拡大／縮小する
      （シーソーに座った女の子は 1.55。公園で測った。2026年9月23日）
   4. お尻を原点へ動かして書き出す（glTF では前が +Z）

   実行: blender -b -P boyfit.py -- 入力.glb 出力.glb お尻から上の高さ [確認画像.png]
   例:   ... -- boy_raw.glb boy_fit.glb 1.50 check.png"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, UPPER = os.path.abspath(a[0]), os.path.abspath(a[1]), float(a[2])
SHOT = os.path.abspath(a[3]) if len(a) > 3 else None
def log(s): print("[boyfit] " + str(s))

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=SRC)
ms = [o for o in bpy.context.scene.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1: bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = mesh.data
P = np.array([tuple(v.co) for v in me.vertices])
size = P.max(0) - P.min(0)
log("読み込み: 頂点 %d / 大きさ x %.3f y %.3f z %.3f" % (len(P), *size))

# お尻（股の下）の位置
cx = (P[:, 0].min() + P[:, 0].max()) / 2
mid = np.abs(P[:, 0] - cx) < size[0] * 0.04
zs = P[mid, 2]; zlow = zs.min()
low = mid & (P[:, 2] < zlow + size[2] * 0.02)
seat = np.array([cx, P[low, 1].mean(), zlow])
log("お尻: x %.3f y %.3f z %.3f（足の先は z %.3f）" % (*seat, P[:, 2].min()))

scale = UPPER / (P[:, 2].max() - seat[2])
Q = (P - seat) * scale
log("倍率 %.4f / お尻から上 %.3f / お尻から下（足の先）%.3f / 幅 %.3f / 前後 %.3f〜%.3f"
    % (scale, Q[:, 2].max(), -Q[:, 2].min(), Q[:, 0].max() - Q[:, 0].min(), Q[:, 1].min(), Q[:, 1].max()))
for i, v in enumerate(me.vertices): v.co = Vector(tuple(float(c) for c in Q[i]))
me.update()

if SHOT:   # 確かめの絵：板（原点を通る厚さ 0.07 の横長の箱）と一緒に、前・横・後ろから
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.035))
    plank = bpy.context.active_object; plank.scale = (0.3, 3.6, 0.07)
    sc = bpy.context.scene
    cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; cd.ortho_scale = 2.4
    cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
    sc.render.resolution_x = 320; sc.render.resolution_y = 360
    files = []
    for k, az in enumerate((0, 90, 180)):
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.08)).normalized()
        cam.location = Vector((0, 0, 0.45)) + d * 8; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        fn = os.path.join(os.path.dirname(SHOT), '_bfit_%d.png' % k); files.append(fn)
        sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
    imgs = [bpy.data.images.load(f) for f in files]; W, H = imgs[0].size
    buf = np.ones((H, W * 3, 4), np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); buf[:, k * W:(k + 1) * W] = px.reshape(H, W, 4)
    o = bpy.data.images.new('o', W * 3, H); o.pixels.foreach_set(buf.ravel()); o.filepath_raw = SHOT; o.file_format = 'PNG'; o.save()
    bpy.data.objects.remove(plank, do_unlink=True)
    log("確認の絵: " + SHOT)

bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                          export_animations=False, export_skins=False, export_image_format='JPEG', export_jpeg_quality=90)
log("書き出し: %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576.0))
