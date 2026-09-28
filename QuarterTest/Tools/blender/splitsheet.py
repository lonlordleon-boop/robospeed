# -*- coding: utf-8 -*-
"""三面図（正面・横・後ろが1枚に並んだ絵）を、1体ずつの正方形の絵に切り分ける。
   Meshy へ渡すときは1枚に1体でないといけないので、この道具で分ける。

   列ごとに「背景でない画素」を数えて人のいる塊を三つ見つけ、
   その中心を真ん中にした正方形（高さと同じ幅）で切り出す。
   絵の外へはみ出す分は背景の色で埋めるので、人の大きさと位置は三枚でそろう。

   Blender の画像は下の行が先頭だが、ここは横に切るだけなので上下はそのまま扱える。

   実行: blender -b --factory-startup -P splitsheet.py -- 入力.png 出力の頭 [枚数]
   例:   ... -- 三面図.png out/girl   →  out/girl_1.png out/girl_2.png out/girl_3.png
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, PRE = a[0], a[1]
N = int(a[2]) if len(a) > 2 else 3

img = bpy.data.images.load(SRC)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
print("SS 入力 %dx%d" % (W, H))

# 背景の色は四隅の平均で決める（三面図はどれも無地の薄い灰色）
c = np.array([A[0,0,:3], A[0,W-1,:3], A[H-1,0,:3], A[H-1,W-1,:3]]).mean(axis=0)
d = np.linalg.norm(A[:, :, :3] - c, axis=2)
col = (d > 0.06).sum(axis=0)          # 列ごとの、背景でない画素の数
thr = max(3, int(H * 0.004))          # これ未満の列は「人がいない」とみなす
on = col > thr

# 続いている区間を拾う。細かい途切れ（髪の隙間など）はつなぐ
runs = []
i = 0
while i < W:
    if on[i]:
        j = i
        while j+1 < W and (on[j+1] or (j+40 < W and on[j+1:j+40].any())):
            j += 1
        runs.append((i, j))
        i = j+1
    else:
        i += 1
runs = [r for r in runs if r[1]-r[0] > W*0.02]
print("SS 見つけた塊 %d 個: %s" % (len(runs), runs))
if len(runs) != N:
    print("SS 【注意】塊の数が %d 枚と合わない。等分で切る" % N)
    runs = [(int(W*k/N), int(W*(k+1)/N)-1) for k in range(N)]

os.makedirs(os.path.dirname(PRE) or ".", exist_ok=True)
S = H                                  # 切り出す一辺は高さに合わせる
for k, (x0, x1) in enumerate(runs):
    cx = (x0 + x1)//2
    out = np.empty((S, S, 4), np.float32)
    # 埋める色は、行ごとに元の絵の左端から取る。
    # 一色でまとめて塗ると、背景の薄い濃淡と食い違って縦じまが出る
    out[:, :, :3] = A[:, 0, :3][:, None, :]
    out[:, :, 3] = 1.0
    # 隣に並んだ人の手などが端に写り込むと Meshy が迷うので、この塊の外は背景で埋める
    m = int((x1-x0)*0.06)
    b0 = max(0, x0-m); b1 = min(W-1, x1+m)
    sx = cx - S//2                     # 元の絵での左端
    a0 = max(b0, sx); a1 = min(b1+1, sx+S)
    if a1 > a0:
        out[:, a0-sx:a1-sx, :] = A[:, a0:a1, :]
    o = bpy.data.images.new("part%d" % k, S, S, alpha=True)
    o.pixels = out.ravel().tolist()
    path = "%s_%d.png" % (PRE, k+1)
    o.filepath_raw = path; o.file_format = 'PNG'; o.save()
    print("SS 書き出し %s （中心 x=%d、幅 %d）" % (path, cx, x1-x0))
