# -*- coding: utf-8 -*-
"""生成した老夫婦のモデルを、仮モデルと同じ寸法・向きにそろえる。

   老夫婦は動かない置物なので、骨は入れない（→ キャラ作成の手順.md 15章と同じ考え方）。
   park12.html は「足元が原点・前が +Z・地面に置くだけ」で使うので、そこにそろえる。

   やっていること：
   1. glb を読み、メッシュを1つにまとめる
   2. 向きをそろえる（前が -Y、上が +Z。Meshy の出力はこの向きで出てくる）
   3. 高さを合わせて拡大／縮小する（仮モデルと同じ高さ。公園は実物の1.4倍の縮尺）
   4. 足を z=0 に、左右の中心を x=0 に、いちばん前（つま先）を狙った位置に置く
   5. 書き出す

   5. （任意）すねを伸ばして、お尻を座面の高さへ持ち上げる
      生成モデルは「低い腰掛けに座った」形で出てくることがある。そのままベンチに置くと
      座面の板がふとももを貫いてしまう。骨が無いので、高さで区切って縦に伸ばして直す。
      y0 より下（靴・足首）はそのまま、y0〜y1（すね）を縦に伸ばし、y1 より上（腰から頭）は
      そのまま lift ぶん持ち上げる。足は地面に着いたまま、お尻だけが座面まで上がる。
   6. 書き出す

   実行: blender -b -P elderfit.py -- 入力.glb 出力.glb 高さ つま先のy [確認画像.png [y0 y1 lift]]
   例:   ... -- grandma_raw.glb elder_grandma.glb 1.901 -0.617 check.png
   例:   ... -- grandpa_raw.glb new_grandpa.glb 1.819 -0.942 check.png 0.12 0.435 0.19
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(a[0])
OUT = os.path.abspath(a[1])
HEIGHT = float(a[2])
FRONT_Y = float(a[3])                 # いちばん前（つま先）を置く y。仮モデルに合わせる
SHOT = os.path.abspath(a[4]) if len(a) > 4 else None
LEG0, LEG1, LIFT = (float(a[5]), float(a[6]), float(a[7])) if len(a) > 7 else (0.0, 0.0, 0.0)

def log(s):
    print("[fit] " + str(s))

# ---------------------------------------------------------------- 読み込み
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=SRC)
ms = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not ms:
    log("メッシュが無い"); sys.exit(1)
bpy.ops.object.select_all(action='DESELECT')
for o in ms:
    o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1:
    bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = mesh.data
P = np.array([tuple(v.co) for v in me.vertices])
tri = sum(len(p.vertices) - 2 for p in me.polygons)
log("読み込み: 頂点 %d / 三角形 %d" % (len(P), tri))
log("  元の大きさ: x %.3f / y %.3f / z %.3f" % tuple(P.max(axis=0) - P.min(axis=0)))

# ---------------------------------------------------------------- 向きの確認
# Meshy は「前が -Y・上が +Z」で出してくる。念のため、一番うすい向きが左右かだけ見る
size = P.max(axis=0) - P.min(axis=0)
if int(np.argmin(size)) != 0:
    log("！ 左右の向きが x ではない（%s が一番うすい）。書き出す前に確認すること" % "xyz"[int(np.argmin(size))])

# ---------------------------------------------------------------- 大きさと位置
scale = HEIGHT / size[2]
Q = P * scale
Q[:, 0] -= (Q[:, 0].min() + Q[:, 0].max()) / 2      # 左右の中心を0へ
Q[:, 1] -= Q[:, 1].min() - FRONT_Y                  # いちばん前（つま先）を狙った位置へ
Q[:, 2] -= Q[:, 2].min()                            # 足を0へ
log("そろえた後: 倍率 %.4f / 幅 %.3f / 前後 %.3f〜%.3f / 高さ %.3f"
    % (scale, Q[:, 0].max() - Q[:, 0].min(), Q[:, 1].min(), Q[:, 1].max(), Q[:, 2].max()))

# ---------------------------------------------------------------- すねを伸ばす（任意）
# 低い腰掛けに座った形で出てきたとき用。足は地面に着けたまま、お尻を座面の高さへ上げる
if LIFT > 0:
    zz = Q[:, 2]
    up = np.where(zz <= LEG0, 0.0,
         np.where(zz >= LEG1, LIFT, LIFT * (zz - LEG0) / max(1e-6, LEG1 - LEG0)))
    Q[:, 2] = zz + up
    log("すねを伸ばした: %.3f〜%.3f を縦に伸ばし、その上を %.3f 持ち上げた（高さ %.3f）"
        % (LEG0, LEG1, LIFT, Q[:, 2].max()))

for i, v in enumerate(me.vertices):
    v.co = Vector((float(Q[i, 0]), float(Q[i, 1]), float(Q[i, 2])))
me.update()

# ---------------------------------------------------------------- 確認の絵（ベンチと並べる）
if SHOT:
    SEAT = 0.64                                     # ベンチの座面の高さ（park12.py と同じ）
    import math
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.18, SEAT - 0.03))
    seat = bpy.context.active_object; seat.scale = (0.45, 0.28, 0.03)
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
    sc = bpy.context.scene
    cam_d = bpy.data.cameras.new('c'); cam_d.type = 'ORTHO'; cam_d.ortho_scale = 2.6
    cam = bpy.data.objects.new('c', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_shadows = True
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
    sc.render.resolution_x = 300; sc.render.resolution_y = 380
    files = []
    for k, az in enumerate((0, 90, 180)):
        d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(6)),
                    -math.cos(math.radians(az)) * math.cos(math.radians(6)), math.sin(math.radians(6))))
        cam.location = Vector((0, 0, HEIGHT / 2)) + d * 8
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        fn = os.path.join(os.path.dirname(SHOT), '_fit_%d.png' % k); files.append(fn)
        sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
    imgs = [bpy.data.images.load(f) for f in files]
    W, H = imgs[0].size
    buf = np.ones((H, W * len(imgs), 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(W * H * 4, dtype=np.float32); im.pixels.foreach_get(px)
        buf[:, k * W:(k + 1) * W] = px.reshape(H, W, 4)
    o = bpy.data.images.new('o', W * len(imgs), H); o.pixels.foreach_set(buf.ravel())
    o.filepath_raw = SHOT; o.file_format = 'PNG'; o.save()
    log("確認の絵: %s（灰色の板が、ベンチの座面の高さ 0.64）" % SHOT)
    bpy.data.objects.remove(seat, do_unlink=True)
    for ob in [x for x in bpy.context.scene.objects if x.type in ('MESH',) and x is not mesh]:
        bpy.data.objects.remove(ob, do_unlink=True)

# ---------------------------------------------------------------- 書き出し
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                          export_animations=False, export_skins=False,
                          export_image_format='JPEG', export_jpeg_quality=90)
log("書き出し: %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576.0))
print("[fit] DONE")
