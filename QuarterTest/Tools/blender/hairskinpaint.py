# -*- coding: utf-8 -*-
"""髪の房の内側に塗られた肌色・白を、髪の色で塗り直す。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、前髪の毛先や顔の横の房の内側、耳のまわりの髪が肌色に塗られていた（「髪の毛の内側に肌色が入っている」）。
   貼り直しの絵は形のまとまりごとに絵の島に分かれていて、読み込んだモデルでは島ごとに頂点がつながっている。
   1) 島（頂点のつながり）のうち、頭のまわり（真ん中の高さ ≥ 0.85m）で、面の半分以上が暗い（明るさ < 0.4）もの＝髪の島
   2) 髪の島の面の中の、明るい画素（明るさ ≥ 0.45・彩度 < 0.4・青系でない）を、その島の暗い面の色（中央値）で塗る。
      面の中だけ塗り、まわりへは広げない。面の真ん中の色で面ごとに決めたら、暗い面の中に描かれた白い筋が残った
   3) 顔の正面で目の高さより下（|x| < 0.08・y < −0.12・高さ < 0.985m）の面は外す。前髪の島に眉間の肌の三角が入っていて、
      塗ると眉間に黒い三角が出る
   4) 下を向いた面（面の向きの上下 < −0.35）は外す。顎の下の肌が髪と同じ絵の島に入っていて（髪 35 面・肌 10 面）、
      島の多数決だけで決めたら顎の下が黒くなった（「ちゃんとマスクしてる？顎裏に髪の色が黒くついてる」）。
      髪の房の内側・前髪の毛先はほぼ横を向く
   **塗る前に必ずマスクを見る**：--mask で塗る所だけ緑のマスクの絵を、--check で塗る所を緑にした確かめ用の glb を書き出す
   （--check のときは出力の絵を書かない）。確かめ用の glb を前・横・下から描いて、顔や顎にかかっていないことを見てから塗る
   面の真ん中の色で決めるので、元の絵（貼り直した絵）と、その絵が入った glb を使う
   実行: blender -b --factory-startup -P hairskinpaint.py -- 入力.glb 元の絵.png 出力.png [--mask マスク.png] [--check 確かめ.glb]"""
import bpy, sys, colorsys, numpy as np, collections
a = sys.argv[sys.argv.index("--")+1:]
MASK = CHECK = None; PIX = True   # 画素ごとに明るい所だけ塗る
if '--mask' in a: i = a.index('--mask'); MASK = a[i+1]; a = a[:i] + a[i+2:]
if '--check' in a: i = a.index('--check'); CHECK = a[i+1]; a = a[:i] + a[i+2:]
SRC, TEX, OUT = a[0], a[1], a[2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = bpy.data.images.load(TEX); W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; MW = me.matrix_world
par = list(range(len(m.vertices)))
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for e in m.edges:
    ra, rb = find(e.vertices[0]), find(e.vertices[1])
    if ra != rb: par[ra] = rb
def fuv(p): return np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
def fcol(p):
    uv = fuv(p); return px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
K = {}; comp = collections.defaultdict(list)
for p in m.polygons:
    h, s, v = colorsys.rgb_to_hsv(*fcol(p))
    # 塗る色は肌色・白に加えて、色味の薄い灰色（明るさ ≥ 0.45・彩度 < 0.4）も。前髪の毛先の灰色の筋が白っぽく見えた。
    # リボンの紺など、はっきりした色（彩度 ≥ 0.4）は塗らない
    # 青系（色相 0.5〜0.8・彩度 ≥ 0.1）はリボンなので塗らない（紺の色味の薄い所をリボンで拾った）
    K[p.index] = 'D' if v < 0.4 else ('S' if (v >= 0.45 and s < 0.4 and not (0.5 <= h <= 0.8 and s >= 0.1)) else 'O')
    comp[find(p.vertices[0])].append(p.index)
def raster(p):
    uv = [uvl[li].uv[:] for li in p.loop_indices]; out = []
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        M = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
        out.append((y0, y1, x0, x1, M))
    return out
N3 = MW.to_3x3().inverted().transposed()
res = px.copy(); msk = np.zeros((H_, W_, 4), np.float32); msk[..., 3] = 1; nf = 0; ni = 0; npx = 0; ndown = 0
for r, fs in comp.items():
    cs = np.array([tuple(MW @ m.polygons[f].center) for f in fs])
    if cs[:, 2].mean() < 0.85: continue
    dk = [f for f in fs if K[f] == 'D']
    if len(dk) / len(fs) < 0.5: continue
    tgt = []
    for f, c in zip(fs, cs):
        # 面の真ん中の色は見ない（前髪の毛先の白い筋は、暗い面の中に描かれていて、面の真ん中の色では拾えなかった）。
        # 髪の島の面の中の、明るい画素だけを下で塗る
        if K[f] == 'D' and PIX is False: continue
        # 目の高さより下の顔の正面は外す（左右 8cm にしたら、目の横の房の先の白い三角まで外れた → 6cm）
        if abs(c[0]) < 0.06 and c[1] < -0.12 and c[2] < 0.985: continue
        if (N3 @ m.polygons[f].normal).normalized().z < -0.35: ndown += 1; continue   # 下向き（顎の下）は外す
        tgt.append(f)
    if not tgt: continue
    hair = np.median(np.array([fcol(m.polygons[f]) for f in dk]), 0)
    for f in tgt:
        for y0, y1, x0, x1, M in raster(m.polygons[f]):
            sub0 = px[y0:y1 + 1, x0:x1 + 1, :3]
            mxp = sub0.max(2); mnp = sub0.min(2); sp = (mxp - mnp) / np.maximum(mxp, 1e-6)
            # 画素ごとの色相（青系＝リボンは外す）
            rr, gg, bb = sub0[..., 0], sub0[..., 1], sub0[..., 2]; dd = np.maximum(mxp - mnp, 1e-6)
            hp = np.where(mxp == rr, ((gg - bb) / dd) % 6, np.where(mxp == gg, (bb - rr) / dd + 2, (rr - gg) / dd + 4)) / 6
            light = (mxp >= 0.45) & (sp < 0.4) & ~((hp >= 0.5) & (hp <= 0.8) & (sp >= 0.1))
            MM = M & light
            if not MM.any(): continue
            sub = res[y0:y1 + 1, x0:x1 + 1]; sub[MM, :3] = (0, 1, 0) if CHECK else hair; npx += int(MM.sum())
            msub = msk[y0:y1 + 1, x0:x1 + 1]; msub[MM, :3] = (0, 1, 0)
    nf += len(tgt); ni += 1
print("HK 髪の島 %d か所の肌色・白の面 %d を%s（%d 画素）。下向きで外した面 %d" % (ni, nf, '緑で印を付けた' if CHECK else '髪の色で塗った', npx, ndown))
if MASK:
    im = bpy.data.images.new("m", W_, H_, alpha=True); im.pixels = msk.ravel(); im.filepath_raw = MASK; im.file_format = 'PNG'; im.save()
    print("HK マスク", MASK)
if CHECK:
    img0 = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    img0.scale(W_, H_); img0.pixels = res.ravel(); img0.pack()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=CHECK, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
    print("HK 確かめ用", CHECK)
else:
    im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save()
    print("HK 書き出し", OUT)
