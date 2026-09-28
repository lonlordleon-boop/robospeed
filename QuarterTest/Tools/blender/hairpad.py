# -*- coding: utf-8 -*-
"""髪の絵の島のふちの外側（どの面も使っていない画素）に、髪の色を広げる（パディング）。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、目の横の房のふちに、肌色の細い筋が何度塗っても残った（「髪の毛についた肌色…マスクできないのかな？」）。
   面ごと・画素ごとに塗るマスクを作っても取れなかったのは、その肌色が**面の中でなく、島と島のすき間（未使用の画素）**にあったから。
   絵は 2048×2048 の半分が未使用で、髪の島のふちに接する未使用の明るい画素が 5,218 あった。細い房の島は幅が数画素しかなく、
   描く時のぼかし（ミップマップ・バイリニア）でふちの外の画素が混ざって、房のふちが肌色に見えていた。
   1) 全画素について「どの面が使っているか」の地図を作る（暗い面＝髪・明るい面＝肌や服・その他）
   2) 未使用の画素を、髪の画素と、髪以外の使用画素の両方から同時に 1 画素ずつ広げ、先に届いた方の色で埋める（R 画素まで）。
      髪に近い未使用画素だけ髪の色（となりの埋まった画素の平均）になり、肌や服の島のふちの外は今のまま
   --mask で、髪の色で埋めた画素だけ緑のマスクの絵を書く。**塗る前にマスクを見る**（絵の上で、島のふちの外だけ緑であること）
   実行: blender -b --factory-startup -P hairpad.py -- 入力.glb 出力.png [--r 16] [--mask マスク.png]"""
import bpy, sys, colorsys, numpy as np
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
R = int(opt('--r', 16)); MASK = opt('--mask', None); TEX = opt('--tex', None)   # --tex：glb の中の絵でなく、この PNG を元にする（islandpaint.py の出力など）
SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = bpy.data.images.load(TEX) if TEX else next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
def fcol(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0); return px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
cls = np.zeros((H_, W_), np.int8)   # 0 未使用 1 髪（暗い面） 2 それ以外の面
def raster(p):
    uv = [uvl[li].uv[:] for li in p.loop_indices]; out = []
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        M = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02); out.append((y0, y1, x0, x1, M))
    return out
for p in m.polygons:
    c = 1 if colorsys.rgb_to_hsv(*fcol(p))[2] < 0.4 else 2
    for y0, y1, x0, x1, M in raster(p):
        cc = cls[y0:y1+1, x0:x1+1]; cc[M] = np.where(cc[M] == 2, 2, c)   # 髪以外の面が使う画素は髪で上書きしない
print("HP 画素：髪 %d・それ以外の面 %d・未使用 %d" % ((cls == 1).sum(), (cls == 2).sum(), (cls == 0).sum()))
res = px.copy(); lab = cls.copy(); filled = np.zeros((H_, W_), bool)
def shifts(A):
    # 上下左右の 4 近傍
    U = np.zeros_like(A); U[1:] = A[:-1]; Dn = np.zeros_like(A); Dn[:-1] = A[1:]
    L = np.zeros_like(A); L[:, 1:] = A[:, :-1]; Rr = np.zeros_like(A); Rr[:, :-1] = A[:, 1:]
    return U, Dn, L, Rr
for it in range(R):
    h = lab == 1; o = lab == 2; free = lab == 0
    hn = np.zeros((H_, W_), np.int32); on = np.zeros((H_, W_), np.int32); csum = np.zeros((H_, W_, 3), np.float32)
    for S in shifts(h): hn += S
    for S in shifts(o): on += S
    # 髪の色の平均（4 近傍の髪の画素）
    for S, dy, dx in ((None, 1, 0), (None, -1, 0), (None, 0, 1), (None, 0, -1)):
        src = np.zeros((H_, W_, 3), np.float32); msk = np.zeros((H_, W_), bool)
        if dy == 1: src[1:] = res[:-1, :, :3]; msk[1:] = h[:-1]
        elif dy == -1: src[:-1] = res[1:, :, :3]; msk[:-1] = h[1:]
        elif dx == 1: src[:, 1:] = res[:, :-1, :3]; msk[:, 1:] = h[:, :-1]
        else: src[:, :-1] = res[:, 1:, :3]; msk[:, :-1] = h[:, 1:]
        csum += src * msk[..., None]
    toh = free & (hn > 0) & (hn >= on)      # 髪が先に届く（同点は髪）
    too = free & (on > 0) & (on > hn)       # それ以外が先に届く（色は変えない。境目を止めるだけ）
    res[toh, :3] = csum[toh] / hn[toh][:, None]
    lab[toh] = 1; lab[too] = 2; filled |= toh
    if not toh.any() and not too.any(): break
print("HP 髪の色で埋めた未使用の画素 %d（R=%d）" % (filled.sum(), R))
if MASK:
    mk = np.zeros((H_, W_, 4), np.float32); mk[..., 3] = 1; mk[filled, 1] = 1; mk[cls == 1, 2] = 0.4
    im = bpy.data.images.new("m", W_, H_, alpha=True); im.pixels = mk.ravel(); im.filepath_raw = MASK; im.file_format = 'PNG'; im.save(); print("HP マスク", MASK)
im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save(); print("HP 書き出し", OUT)
