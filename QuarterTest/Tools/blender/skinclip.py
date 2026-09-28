# -*- coding: utf-8 -*-
"""顔の肌が「振り切れて」白っぽくなったテクスチャを直す。

   skinmatch.py の手本の色 (1.00, 0.82, 0.72) は、赤が表せる一番上の値そのもの。
   肌の中央値をそこへ合わせるので、中央値より明るい肌は赤が上限を超えて切り捨てられる。
   しかも秀才少女・ギャル少女では「明るさ 0.62 以上」など明るい側だけを肌と見る窓を渡したので、
   一番明るい肌の中央値が 1.0 に置かれ、顔がまるごと振り切れた。
   測った結果、顔の肌で赤が振り切れていた割合は
   元気少女 0.1% / ギャル少女 0% に対し、お嬢様 49.6% / 秀才少女 85.1%。
   赤だけが平らになり、緑と青だけが陰影を持つので、色が抜けて青白く見える。

   緑と青は1画素も振り切れていない（陰影はそのまま残っている）。
   そこで、振り切れていない肌の画素から「赤は緑からどう決まるか」を直線で当てはめ、
   振り切れた画素の赤を緑から作り直す。そのあと、顔の肌の中央値が三面図の顔の色になるよう
   倍率を掛ける。倍率は肌らしさの重みを付けて掛けるので、服や髪は動かない。

   skinmatch.py と違い、計算は**見た目の色（sRGB）のまま**行う。
   「255 で振り切れている」を直接扱いたいのと、三面図から測った手本の色をそのまま渡せるため。

   手本は「三面図の顔の中央値」を sRGB の 0〜255 で渡す（例 232,192,172）。
   三面図ぜんぶの肌から測ると金髪や赤いスカートが混ざるので、顔の四角から測ること。

   出てくるのは PNG だけ。glb へ戻すのは swaptex.py（動きや骨に触らないので安全）。

   肌らしさの窓は見た目の色（sRGB）で書く。既定は 4人ぶん確かめた値。
   ギャル少女は**金髪が肌と同じ色相**なので、鮮やかさの上限を下げて外すこと（肌 0.21・金髪 0.37）。
   窓が合っているかは、必ず全身の絵を描いて、髪や服の色が変わっていないか見ること。

   実行: blender -b --factory-startup -P skinclip.py -- 入力.glb 出力.png 手本r,g,b [h0,h1] [s0,s1] [v0]
   例:   ... -- shusai.glb shusai_skin.png 232,192,172
   例（金髪を外す）: ... -- gyaru.glb gyaru_skin.png 234,198,180 "" 0.08,0.28
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
MASKARG = next((v[5:] for v in a if v.startswith('mask=')), None)   # mask=マスク.png（どこに書いてもよい）
a = [v for v in a if not v.startswith('mask=')]
SRC, OUTPNG = a[0], a[1]
TARGET = np.array([float(v) for v in a[2].split(',')], dtype=np.float64) / 255.0
CLIP = 254.0 / 255.0               # ここ以上は「振り切れている」とみなす

# 肌らしさの窓（見た目の色で測った値。4人ぶん確かめて、髪・目・服が外れることを見てある）
H0, H1 = -0.04, 0.12               # 色相（赤〜橙）
S0, S1 = 0.08, 0.45                # 鮮やかさ
V0 = 0.50                          # 明るさの下限
if len(a) > 3 and a[3]: H0, H1 = [float(v) for v in a[3].split(',')]
if len(a) > 4 and a[4]: S0, S1 = [float(v) for v in a[4].split(',')]
if len(a) > 5 and a[5]: V0 = float(a[5])

def log(s):
    print("[skinclip] " + str(s))

def lin2srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.maximum(c, 0) ** (1 / 2.4) - 0.055)
def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

# ---------------------------------------------------------------- 読み込み
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
mesh = me.data
img = next(n.image for m in mesh.materials if m and m.use_nodes
           for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float64).reshape(H, W, 4)
C = np.clip(lin2srgb(A[:, :, :3]), 0, 1)          # ここから先は見た目の色で計算する
log("読み込み: 頂点 %d / 絵 %dx%d" % (len(mesh.vertices), W, H))

# ---------------------------------------------------------------- 肌らしさ
mx = C.max(2); mn = C.min(2); d = np.maximum(mx - mn, 1e-6)
r, g, b = C[..., 0], C[..., 1], C[..., 2]
h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
hh = np.where(h > 0.5, h - 1.0, h)
def ramp(x, a0, a1): return np.clip((x - a0) / max(a1 - a0, 1e-6), 0, 1)
# 窓の端をなだらかにする（境目で色が段になるのを防ぐ）
w = ramp(hh, H0 - 0.02, H0) * (1 - ramp(hh, H1, H1 + 0.02)) \
    * ramp(s, S0 - 0.02, S0) * (1 - ramp(s, S1, S1 + 0.05)) * ramp(mx, V0 - 0.05, V0)
core = w > 0.9
log("肌の画素 %d（%.1f%%）" % (core.sum(), 100 * core.mean()))

# ---------------------------------------------------------------- 顔の画素を拾う
# 三角形の重心が「頭の前半分」に入っていたら、その三角形の UV の囲み箱を顔とみなす。
# （テクスチャは三角形ごとにバラバラなので、囲み箱で十分細かい）
# ちび体型は頭が大きいので、頭の帯は身長の3割ほど取る。髪・目・口は肌らしさの窓で外れる。
P = np.array([tuple(v.co) for v in mesh.vertices])
uvl = mesh.uv_layers.active.data
S = P[:, 2].max() - P[:, 2].min()
top = P[:, 2].max()
head = P[P[:, 2] > top - 0.33 * S]
ymid = np.median(head[:, 1])
log("身長 %.3f / 頭の帯 %.1f〜%.1f / 頭の前後の中心 %.1f" % (S, top - 0.33 * S, top, ymid))

def region_mask(f):
    """重心が f を満たす三角形の、UV の囲み箱をまとめた覆い"""
    m = np.zeros((H, W), dtype=bool)
    n = 0
    for poly in mesh.polygons:
        c = np.mean([P[i] for i in poly.vertices], 0)
        if not f(c): continue
        n += 1
        us = [uvl[li].uv for li in poly.loop_indices]
        x0 = max(0, int(min(u[0] for u in us) * W)); x1 = min(W - 1, int(np.ceil(max(u[0] for u in us) * W)))
        y0 = max(0, int(min(u[1] for u in us) * H)); y1 = min(H - 1, int(np.ceil(max(u[1] for u in us) * H)))
        m[y0:y1 + 1, x0:x1 + 1] = True
    return m, n

def face_mask(sign):
    m = np.zeros((H, W), dtype=bool)
    n = 0
    for poly in mesh.polygons:
        vs = [P[i] for i in poly.vertices]
        c = np.mean(vs, 0)
        if abs(c[0]) > 0.10 * S: continue
        if c[2] < top - 0.30 * S or c[2] > top - 0.03 * S: continue
        if (c[1] - ymid) * sign <= 0.02 * S: continue        # 頭の前半分だけ
        n += 1
        us = [uvl[li].uv for li in poly.loop_indices]
        x0 = max(0, int(min(u[0] for u in us) * W)); x1 = min(W - 1, int(np.ceil(max(u[0] for u in us) * W)))
        y0 = max(0, int(min(u[1] for u in us) * H)); y1 = min(H - 1, int(np.ceil(max(u[1] for u in us) * H)))
        m[y0:y1 + 1, x0:x1 + 1] = True
    return m, n

# 顔は肌が多い側。後頭部は髪ばかりなので、肌の割合で前後を決める
picks = {}
for sign in (+1, -1):
    m, n = face_mask(sign)
    picks[sign] = (m, n, int((core & m).sum()))
sign = max(picks, key=lambda k: picks[k][2])
face, ntri, nskin = picks[sign]
log("顔の向き: y の%s側（三角形 %d・肌の画素 %d／反対側は %d）"
    % ("＋" if sign > 0 else "−", ntri, nskin, picks[-sign][2]))
# ---------------------------------------------------------------- 直してよい場所（胴を外す）
# 色だけでは、チェックのスカートの白い升や、金髪を肌と見分けられない（実際に染まった）。
# 肌が出ているのは「頭から上」と「スカートより下の脚」だけなので、そこだけに限る。
# 手は胴の幅の中にあって分けられないので外す（画面では数画素なので目立たない）。
bot = P[:, 2].min()
if MASKARG:
    # skinmask.py で作ったマスクがあるなら、そちらを使う（赤 = 肌）
    mi = bpy.data.images.load(os.path.abspath(MASKARG))
    if tuple(mi.size) != (W, H):
        log("！ マスクの大きさが絵と違う（%dx%d と %dx%d）" % (mi.size[0], mi.size[1], W, H)); sys.exit(1)
    MA = np.array(mi.pixels[:], dtype=np.float64).reshape(H, W, 4)[:, :, :3]
    MA = np.clip(lin2srgb(MA), 0, 1) if mi.colorspace_settings.name != 'Non-Color' else MA
    skinreg = (MA[..., 0] > 0.5) & (MA[..., 1] < 0.5) & (MA[..., 2] < 0.5)     # 赤だけ
    log("マスクを使う: %s（肌の画素 %d・%.1f%%）" % (MASKARG, skinreg.sum(), 100 * skinreg.mean()))
    # 顔の箱を下へ広げる。上のほうだけだと前髪しか入らず、顔の画素が0になった（お嬢様）。
    # 頭ぜんぶを箱にすると、UVの囲み箱が脚の島まで拾ってしまう（中央値が暗くなる）。
    face, nf = region_mask(lambda c: abs(c[0]) < 0.085 * S
                           and top - 0.48 * S < c[2] < top - 0.05 * S
                           and (c[1] - ymid) * sign > 0.02 * S)
    log("顔を測る場所: 顔の正面の箱（三角形 %d）" % nf)
else:
    skinreg, nreg = region_mask(lambda c: c[2] > bot + 0.50 * S
                                or (c[2] < bot + 0.22 * S and abs(c[0]) < 0.14 * S))
    log("直してよい場所: 三角形 %d（頭から上と、脚だけ。マスクがあれば mask= で渡すこと）" % nreg)
w = w * skinreg
core = core & skinreg
fc = core & face
if fc.sum() < 500:
    log("！ 顔の肌の画素が少なすぎる（%d）" % fc.sum()); sys.exit(1)

def report(X, m, tag):
    v = X[m]
    mm = np.median(v, 0)
    ss = np.median((v.max(1) - v.min(1)) / np.maximum(v.max(1), 1e-6))
    cl = float((v[:, 0] >= CLIP).mean())
    log("%s: 中央値 %s  鮮やかさ %.3f  赤の振り切れ %.1f%%（画素 %d）"
        % (tag, np.round(mm * 255).astype(int), ss, 100 * cl, len(v)))
    return mm

med0 = report(C, fc, "直す前の顔")

# ---------------------------------------------------------------- 振り切れた赤を、緑から作り直す
keep = core & (C[..., 0] < CLIP)
hit = core & (C[..., 0] >= CLIP)
if keep.sum() < 500 or hit.sum() == 0:
    log("赤の作り直しは要らない（振り切れ %d 画素）" % hit.sum())
else:
    aa, bb = np.polyfit(C[..., 1][keep], C[..., 0][keep], 1)
    C[..., 0][hit] = np.maximum(CLIP, aa * C[..., 1][hit] + bb)
    log("赤の作り直し: 赤 = %.3f×緑 + %.3f（当てはめ %d 画素 → 作り直し %d 画素・最大 %.3f）"
        % (aa, bb, keep.sum(), hit.sum(), C[..., 0][hit].max()))

# ---------------------------------------------------------------- 顔の中央値を手本へ寄せる
med1 = np.median(C[fc], 0)
gain = TARGET / np.maximum(med1, 1e-4)
log("倍率: 今の顔 %s → 手本 %s  倍率 %s"
    % (np.round(med1 * 255).astype(int), np.round(TARGET * 255).astype(int), np.round(gain, 3)))
NEW = np.clip(C * (1 + (gain - 1) * w[..., None]), 0, 1)

report(NEW, fc, "直したあとの顔")
bodyc = core & ~face
if bodyc.sum():
    log("体の肌: %s → %s" % (np.round(np.median(C[bodyc], 0) * 255).astype(int),
                              np.round(np.median(NEW[bodyc], 0) * 255).astype(int)))

# ---------------------------------------------------------------- 書き出し
A[:, :, :3] = srgb2lin(NEW)
img.pixels = A.ravel().tolist()
img.filepath_raw = os.path.abspath(OUTPNG); img.file_format = 'PNG'; img.save()
log("書き出し: %s (%.2f MB)" % (OUTPNG, os.path.getsize(OUTPNG) / 1048576.0))
print("[skinclip] DONE")
