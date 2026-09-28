# -*- coding: utf-8 -*-
"""リボンと髪の塗り分けを直す（「塗りのマスクをまた作って塗り直して。髪の毛（左側頭部に黄色）やリボンに髪の色が入ってる」）。
   1) リボンの面を形で決める：黄色の面から、折れ目 TH 度未満でつながる隣へ広げる（箱の中だけ）。リボンと髪の境は折れ目なので止まる
   2) マスクの絵を作って残す：リボン=橙(255,128,0)・直す髪（左側頭部）=緑(0,255,0)・ほか=黒。三角形が覆う画素だけ塗り、最後に外へ4回広げる
   3) 塗り直す（明るさの比で陰影を残す）
      リボンの中の黄色でない画素 → リボンの黄色の中央値 ×（その画素の明るさ ÷ 黄色でない画素の明るさの中央値）
      左側頭部の髪の黄色い画素 → 髪の茶色の中央値 ×（明るさ ÷ 黄色い画素の明るさの中央値）
   出力の PNG は swaptex.py で glb に差し替える（Blender で書き出しても元の絵が出るため）
   実行: blender -b --factory-startup -P ribbonfix.py -- 入力.glb 直した絵.png マスク.png 確認.png [TH 20]"""
import bpy, sys, colorsys, math, os, numpy as np, collections
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUTPNG, MASKPNG, CHK = a[0], a[1], a[2], a[3]
TH = float(a[4]) if len(a) > 4 else 20.0
BOWBOX = (-0.21, -0.04, -0.15, 0.15, 0.92, 1.22)      # リボンを探す箱（体の右側・ポニーテールの結び目）
HAIRBOX = (0.06, 0.25, -0.20, 0.20, 0.95, 1.25)        # 直す髪（左側頭部の房）
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
me = next(o for o in bpy.data.objects if o.type == 'MESH'); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
print("RF 絵の大きさ", W_, H_)
uvl = m.uv_layers.active.data; MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in m.vertices])
C = {p.index: P[list(p.vertices)].mean(0) for p in m.polygons}
def inbox(f, B):
    c = C[f]; return B[0] <= c[0] <= B[1] and B[2] <= c[1] <= B[3] and B[4] <= c[2] <= B[5]
def hsv_face(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    return colorsys.rgb_to_hsv(*c)
def isyel(h, s): return 40/360 < h < 75/360 and s > 0.25
canon = {}; key = {}
for v in m.vertices:
    k = tuple(np.round(np.array(v.co), 5)); canon[v.index] = key.setdefault(k, v.index)
N = {p.index: (MW.to_3x3() @ p.normal).normalized() for p in m.polygons}
emap = collections.defaultdict(list)
for p in m.polygons:
    vs = [canon[v] for v in p.vertices]
    for i in range(len(vs)): emap[tuple(sorted((vs[i], vs[(i+1) % len(vs)])))].append(p.index)
nbr = collections.defaultdict(set)
for fs in emap.values():
    for f in fs:
        for g in fs:
            if f != g: nbr[f].add(g)
HSV = {p.index: hsv_face(p) for p in m.polygons if C[p.index][2] > 0.80}
seed = [f for f in HSV if inbox(f, BOWBOX) and isyel(*HSV[f][:2])]
bow = set(seed); st = list(seed); cth = math.cos(math.radians(TH))
while st:
    f = st.pop()
    for g in nbr[f]:
        if g in bow or g not in HSV or not inbox(g, BOWBOX): continue
        if N[f].dot(N[g]) < cth: continue
        bow.add(g); st.append(g)
# シワ：折れ目で止まってリボンから外れた面（茶色が残った）。リボンの面を NCLOSE 輪 広げてから同じだけ縮め（穴ふさぎ）、増えた面をシワとする
# 「リボンのシワに入った髪色を影に出来れば良いんだけど」→ シワは髪の色でなく、リボンの黄色の影の色で塗る
NCLOSE = int(a[5]) if len(a) > 5 else 6   # 3輪では結び目の切れ込みが埋まらなかった
dil = set(bow)
for it in range(NCLOSE):
    dil |= set(g for f in dil for g in nbr[f] if g in HSV and inbox(g, BOWBOX))
ero = set(dil)
for it in range(NCLOSE):
    ero = set(f for f in ero if all((g in ero) or (g not in HSV) or not inbox(g, BOWBOX) for g in nbr[f]))
crease = ero - bow
hairfix = set(f for f in HSV if f not in bow and f not in crease and inbox(f, HAIRBOX))
print("RF リボンの面 %d（種 %d）  シワ %d（穴ふさぎ %d 輪）  直す髪の面 %d" % (len(bow), len(seed), len(crease), NCLOSE, len(hairfix)))
# ---- 三角形が覆う画素を塗る（重心座標）----
LBL = np.zeros((H_, W_), np.uint8)          # 0=どこでもない 1=ほかの面 2=リボン 3=直す髪 4=リボンのシワ
for p in m.polygons:
    uv = [uvl[li].uv[:] for li in p.loop_indices]
    lab = 2 if p.index in bow else (4 if p.index in crease else (3 if p.index in hairfix else 1))
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        inside = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
        sub = LBL[y0:y1 + 1, x0:x1 + 1]
        if lab == 1: sub[inside & (sub == 0)] = 1
        else: sub[inside & (sub != 2)] = lab      # リボン・直す髪は、ほかの面より優先（リボンが一番強い）
covered = LBL > 0
# ---- 塗り直す ----
rgb = px[:, :, :3].copy()
mx = rgb.max(2); mn = rgb.min(2); s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
d = np.maximum(mx - mn, 1e-6); r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
yel = (hue > 38) & (hue < 75) & (s > 0.20)
yel_hair = (hue > 33) & (hue < 80) & (s > 0.10)   # 髪の中の薄い黄色も拾う（房のふちに薄い黄色の筋が残った）
K = 0.6                                         # 明るさの差を6割に（色合い・鮮やかさは手本に固定。RGB で掛けると明るい所で赤が振り切れ、緑がかった）
def paint(ref, ratio):
    h0, s0, v0 = colorsys.rgb_to_hsv(*ref)
    v = np.clip(v0 * (1 + K * (ratio - 1)), 0, 1)
    i = int(h0 * 6) % 6; f = h0 * 6 - int(h0 * 6)
    p_, q_, t_ = v * (1 - s0), v * (1 - s0 * f), v * (1 - s0 * (1 - f))
    return np.stack([(v, q_, p_, p_, t_, v)[i], (t_, v, v, q_, p_, p_)[i], (p_, p_, t_, v, v, q_)[i]], 1)
L = 0.299 * r + 0.587 * g + 0.114 * b
out = rgb.copy()
m2 = LBL == 2; m3 = LBL == 3; m4 = LBL == 4
ry = m2 & yel; rn = m2 & ~yel
yref = np.median(rgb[ry], 0); Lyn = np.median(L[rn]) if rn.any() else 1
out[rn] = paint(yref, L[rn] / Lyn)
hy = m3 & yel_hair; hb = m3 & ~yel_hair & (s > 0.35)
href = np.median(rgb[hb], 0); Lhy = np.median(L[hy]) if hy.any() else 1
out[hy] = paint(href, L[hy] / Lhy)
print("RF リボンの黄色 %s  塗り直したリボンの画素 %d（リボン全体 %d）" % (np.round(yref * 255).astype(int), int(rn.sum()), int(m2.sum())))
print("RF 髪の茶色 %s  塗り直した髪の画素 %d（直す範囲 %d）" % (np.round(href * 255).astype(int), int(hy.sum()), int(m3.sum())))
# シワは影の色：リボンの黄色より色相を4度赤へ、鮮やかさ1.15倍、明るさ0.70倍（14度赤へ寄せると髪の茶色と見分けにくかった）を手本にし、明るさの差を6割で残す
h_, s_, v_ = colorsys.rgb_to_hsv(*yref); yshadow = np.array(colorsys.hsv_to_rgb((h_ - 4/360) % 1, min(1.0, s_ * 1.15), v_ * 0.70))
if m4.any(): out[m4] = paint(yshadow, L[m4] / np.median(L[m4]))
print("RF シワの影の色 %s  塗った画素 %d" % (np.round(yshadow * 255).astype(int), int(m4.sum())))
changed = rn | hy | m4
# 島の外の帯（どの面も覆わない画素）へ4回広げる
for it in range(4):
    grow = np.zeros_like(changed); acc = np.zeros_like(out); cnt = np.zeros((H_, W_), np.float32)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.roll(np.roll(changed, dy, 0), dx, 1); so = np.roll(np.roll(out, dy, 0), dx, 1)
        acc += so * sh[..., None]; cnt += sh
    tgt = (cnt > 0) & ~covered & ~changed
    out[tgt] = acc[tgt] / cnt[tgt][:, None]; changed = changed | tgt
# マスクの絵（リボン=橙・直す髪=緑）。外へ4回広げる
MK = np.zeros((H_, W_, 4), np.float32); MK[..., 3] = 1
lab2 = m2.copy(); lab3 = m3.copy(); lab4 = m4.copy()
for it in range(4):
    for lb in (lab2, lab3, lab4):
        g = lb.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)): g |= np.roll(np.roll(lb, dy, 0), dx, 1)
        lb[:] = lb | (g & ~covered)
MK[lab3] = (0, 1, 0, 1); MK[lab2] = (1, 128/255, 0, 1); MK[lab4] = (128/255, 64/255, 0, 1)   # シワ＝こげ茶
def save(arr, path):
    im = bpy.data.images.new(os.path.basename(path), W_, H_, alpha=True)
    im.pixels = arr.ravel(); im.filepath_raw = path; im.file_format = 'PNG'; im.save()
o4 = px.copy(); o4[..., :3] = out
save(o4, OUTPNG); save(MK, MASKPNG)
print("RF 書き出し", OUTPNG, MASKPNG)
# ---- 確認：直した絵を貼って頭を6方向から描く ----
newimg = bpy.data.images.load(OUTPNG)
for n in me.active_material.node_tree.nodes:
    if n.type == 'TEX_IMAGE' and n.image: n.image = newimg
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
CW = 400; sc.render.resolution_x = CW; sc.render.resolution_y = CW
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.40
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
Cc = Vector((-0.02, 0.0, 1.03)); tiles = []; tmp = os.path.join(os.path.dirname(CHK), "_rf"); os.makedirs(tmp, exist_ok=True)
for az in (0, 90, 180, 225, 270, 315):
    ar = math.radians(az); cam.location = (Cc.x + 5*math.sin(ar), Cc.y - 5*math.cos(ar), Cc.z)
    cam.rotation_euler = (Cc - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmp, "r%d.png" % az); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
buf = np.ones((CW, CW*len(tiles), 4), np.float32)
for i, p in enumerate(tiles):
    im = bpy.data.images.load(p); buf[:, i*CW:(i+1)*CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
sh = bpy.data.images.new("s", CW*len(tiles), CW); sh.pixels = buf.ravel(); sh.filepath_raw = CHK; sh.file_format = 'PNG'; sh.save()
