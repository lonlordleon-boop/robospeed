# -*- coding: utf-8 -*-
"""腕と胴のつなぎ目に、影の線をテクスチャへ描く。

   生成したモデルは、腕が胴とひとつながりに溶接されていることがある。
   秀才少女とギャル少女がそれで、袖と服が同じ色のため**腕の輪郭が消えて一枚の塊に見える**。

   `bakeao.py` は効かない。さえぎる凹みが形として無いので、計算しても影が出ない（実際に焼いて確かめた）。
   `spread_arms.py` で腕を開けば手の先は離れるが、肩の付け根は溶接されたままで変わらない。

   そこで**骨の重み**を使う。腕の骨（LeftArm など）の重みが 0.5 になる線が、
   ちょうど腕と胴の境目＝袖の付け根にあたる。そこへ細い影を掛ける。
   形にも重みにも触らないので、動きは1コマも変わらない。

   仕上がりの色 = 元の色 × (1 − 強さ × exp(−((重み−0.5)/幅)^2))

   実行: blender -b --factory-startup -P seamshade.py -- 入力.glb 出力.png [強さ 0.30] [幅 0.20] [骨,...]
   例:   ... -- gy1_v2.glb out.png 0.30 0.20
   骨を省くと LeftArm,LeftForeArm,LeftHand,RightArm,RightForeArm,RightHand を使う
   （肩 LeftShoulder は胴の側に入れる。そうすると影が袖の付け根に来る）。

   glb へ戻すのは swaptex.py。
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], a[1]
AMT = float(a[2]) if len(a) > 2 else 0.30
WID = float(a[3]) if len(a) > 3 else 0.20
BONES = a[4].split(',') if len(a) > 4 else \
    ['LeftArm', 'LeftForeArm', 'LeftHand', 'RightArm', 'RightForeArm', 'RightHand']

def log(s):
    print("[seamshade] " + str(s))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
mesh = me.data
img = next(n.image for m in mesh.materials if m and m.use_nodes
           for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float64).reshape(H, W, 4)

# ---------------------------------------------------------------- 頂点ごとの「腕らしさ」
gi = [me.vertex_groups[b].index for b in BONES if b in me.vertex_groups]
if not gi:
    log("！ その名前の頂点グループが無い: " + ",".join(BONES)); sys.exit(1)
log("腕とみなす骨: " + ", ".join(b for b in BONES if b in me.vertex_groups))
wv = np.zeros(len(mesh.vertices), dtype=np.float64)
for v in mesh.vertices:
    s = 0.0
    for g in v.groups:
        if g.group in gi: s += g.weight
    wv[v.index] = min(1.0, s)
log("腕の重み: 1.0 に近い頂点 %d / 0.5 付近 %d / 0 の頂点 %d"
    % ((wv > 0.9).sum(), ((wv > 0.3) & (wv < 0.7)).sum(), (wv < 0.01).sum()))

# ---------------------------------------------------------------- 境目に影を掛ける
uvl = mesh.uv_layers.active.data
mesh.calc_loop_triangles()
shade = np.zeros((H, W), dtype=np.float64)
for t in mesh.loop_triangles:
    ws = np.array([wv[i] for i in t.vertices])
    if ws.max() < 0.05 or ws.min() > 0.95: continue          # 境目から遠い面は飛ばす
    us = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    xs = us[:, 0] * W; ys = us[:, 1] * H
    x0 = max(0, int(np.floor(xs.min())) - 1); x1 = min(W - 1, int(np.ceil(xs.max())) + 1)
    y0 = max(0, int(np.floor(ys.min())) - 1); y1 = min(H - 1, int(np.ceil(ys.max())) + 1)
    if x1 < x0 or y1 < y0: continue
    den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if abs(den) < 1e-12: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
    l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
    l3 = 1.0 - l1 - l2
    cov = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
    if not cov.any(): continue
    ww = l1 * ws[0] + l2 * ws[1] + l3 * ws[2]                 # その画素の腕の重み
    band = np.exp(-((ww - 0.5) / max(WID, 1e-6)) ** 2)
    blk = shade[y0:y1 + 1, x0:x1 + 1]
    shade[y0:y1 + 1, x0:x1 + 1] = np.where(cov, np.maximum(blk, band), blk)

n = (shade > 0.05).sum()
log("影を掛けた画素 %d（%.2f%%）  一番濃い所 ×%.3f" % (n, 100.0 * n / (W * H), 1 - AMT * shade.max()))
A[:, :, :3] = np.clip(A[:, :, :3] * (1 - AMT * shade)[..., None], 0, 1)

img.pixels = A.ravel().tolist()
img.filepath_raw = os.path.abspath(OUT); img.file_format = 'PNG'; img.save()
log("書き出し: %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576.0))
print("[seamshade] DONE")
