# -*- coding: utf-8 -*-
"""テクスチャの肌の画素だけ、色を手本の肌の色へ寄せる。

   貼り直し（meshy_v5_retexture）で肌がくすんだ。三面図と生成直後の絵の肌は (1.00, 0.82, 0.72)・鮮やかさ 0.28 の
   温かい桃色なのに、貼り直し後は (0.87, 0.77, 0.69)・鮮やかさ 0.20 の灰色がかったベージュになり、
   「肌が汚い」と見えた。

   肌の画素（色相が赤〜橙、鮮やかさ 0.06〜0.5、明るさ 0.5 以上）に、
   「手本の肌の色 ÷ 今の肌の色」の倍率を、肌らしさの度合いで重みを付けて掛ける。
   白い服（鮮やかさが低い）、黒髪、紺、首元の黄色（色相が黄）は外れる。頬の赤みも肌として一緒に寄る。
   今の肌の色は、テクスチャの肌の画素の中央値で測る。

   秀才少女では、赤チェックのスカートのくすんだ赤も肌と判定され、明るいピンクに変わった。
   測ると、肌は色相 0.03〜0.07・明るさ 0.63 以上、頬は色相 0.034〜0.043、スカートの赤は色相 −0.017〜0.035
   （中央値 0.003）・明るさ 0.47〜0.67。位置の箱で外すと、スカートの下の腿まで外れて色の段差が出た。
   5番目に「色相の下限の窓 h0,h1」、6番目に「明るさの下限の窓 v0,v1」を書くと、肌らしさの窓の下端を変えられる
   （既定は -0.07,-0.04 と 0.45,0.55）。

   ギャル少女では、金髪（色相 0.063〜0.083・鮮やかさ 0.31〜0.55）が肌と同じ色相で、肌と判定されて顔が白く飛んだ。
   肌は鮮やかさ 0.24〜0.29。7番目に「鮮やかさの上限の窓 s0,s1」を書くと、髪を外せる（既定は 0.45,0.55）。

   実行: blender -b --factory-startup -P skinmatch.py -- 入力.glb 出力.png 出力.glb 手本の肌 r,g,b [h0,h1] [v0,v1] [s0,s1]
   例（秀才少女・赤チェックを外す）: ... 1.0,0.824,0.718 0.012,0.028 0.55,0.62
   例（ギャル少女・金髪とピンクのパーカーを外す）: ... 1.0,0.824,0.718 0.00,0.02 "" 0.30,0.34
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUTPNG, OUTGLB = a[0], a[1], a[2]
TARGET = np.array([float(v) for v in a[3].split(',')], dtype=np.float32)
HLO = [float(v) for v in a[4].split(',')] if len(a) > 4 and a[4] else [-0.07, -0.04]
VLO = [float(v) for v in a[5].split(',')] if len(a) > 5 and a[5] else [0.45, 0.55]
SHI = [float(v) for v in a[6].split(',')] if len(a) > 6 and a[6] else [0.45, 0.55]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
mesh = me.data
img = next(n.image for m in mesh.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
C = A[:, :, :3]
mx = C.max(2); mn = C.min(2); d = np.maximum(mx - mn, 1e-6)
r, g, b = C[..., 0], C[..., 1], C[..., 2]
h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
# 肌らしさ（0〜1）。色相・鮮やかさ・明るさのそれぞれの窓の端をなだらかにする
def ramp(x, a0, a1): return np.clip((x - a0) / max(a1 - a0, 1e-6), 0, 1)
hh =np.where(h > 0.5, h - 1.0, h)                      # 赤を 0 付近にまとめる（-0.5〜0.5）
hue_ok = ramp(hh, HLO[0], HLO[1]) * (1 - ramp(hh, 0.10, 0.125))
sat_ok = ramp(s, 0.04, 0.08) * (1 - ramp(s, SHI[0], SHI[1]))
val_ok = ramp(mx, VLO[0], VLO[1])
w = hue_ok * sat_ok * val_ok
core = w > 0.9
cur = np.median(C[core], 0)
gain = TARGET / np.maximum(cur, 1e-4)
print("SM 肌の画素 %d（%.1f%%）  今の肌の中央値 %s  手本 %s  倍率 %s" % (core.sum(), 100 * core.mean(), np.round(cur, 3), np.round(TARGET, 3), np.round(gain, 3)))
NEW = np.clip(C * (1 + (gain - 1) * w[..., None]), 0, 1)
after = np.median(NEW[core], 0)
nm = NEW[core]; ns = (nm.max(1) - nm.min(1)) / np.maximum(nm.max(1), 1e-6)
print("SM 直したあとの肌の中央値 %s  鮮やかさ %.3f" % (np.round(after, 3), float(np.median(ns))))
A[:, :, :3] = NEW
img.pixels = A.ravel().tolist()
img.filepath_raw = OUTPNG; img.file_format = 'PNG'; img.save()
newimg = bpy.data.images.load(OUTPNG)
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image == img: n.image = newimg
bpy.ops.object.select_all(action='SELECT')
# 絵はこれ以上 JPEG で圧縮しない（貼り直しと書き出しで2回 JPEG になり、肌がざらついていた）
bpy.ops.export_scene.gltf(filepath=OUTGLB, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='AUTO')
print("SM 書き出し", OUTGLB, os.path.getsize(OUTGLB))
