# -*- coding: utf-8 -*-
"""テクスチャの画素に「ここは肌・ここは髪・ここは服」と印を付けた絵（マスク）を作る。

   生成したモデルは**全身がメッシュ1個・材質1個・絵1枚**で、肌も髪も服も同じ絵に混ざっている。
   しかも三角形ごとにバラバラに散らばっているので、絵を開いて「顔のあたり」を探すことはできない。
   そのため色を直すたびに「どの画素が肌か」を推測していて、事故が起きた。

   - 秀才少女：チェックのスカートの白い升が肌と判定され、茶色くなった
   - ギャル少女：金髪(228,204,183・鮮やかさ0.202)と肌(231,208,184・0.204)が色として同じで、
     直すと髪まで桃色になった

   溶接して調べたが、髪と肌はメッシュとしてつながっている（全身が1つのかたまり）ので、
   形だけでも分けられない。**だから一度だけ人の目で作って、あとはずっと使い回す。**

   出てくるマスクの色（そのままの値。にじませないこと）:
     赤 (255,0,0) 肌 ／ 緑 (0,255,0) 髪 ／ 青 (0,0,255) 服 ／ 黄 (255,255,0) 靴 ／ 黒 どこでもない

   自動の決め方（身長に対する割合で見る）:
     z < 0.075          → 靴
     z > 0.50（頭）     → 肌らしい色なら肌、ちがえば髪
     z < 0.30 かつ細い  → 肌らしい色なら肌、ちがえば服
     それ以外           → 肌らしい色なら肌（手・腕）、ちがえば服

   自動で間違うところは、**箱で上書きする**。箱はあとに書いたものが勝つ。
     ラベル:x0,x1,y0,y1,z0,z1   （身長に対する割合。前は −y、上は +z）
     ラベルは skin / hair / cloth / shoe / none
   例（ギャル少女の金髪を髪にする）: hair:-0.45,0.45,-0.30,0.30,0.72,1.05

   確認の絵は、マスクを貼ったまま3方向から描く。**必ず見てから使うこと。**

   実行: blender -b --factory-startup -P skinmask.py -- 入力.glb マスク.png 確認.png [箱...]
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUTMASK, OUTSHOT = a[0], a[1], a[2]
BOXES = [v for v in a[3:] if not v.startswith("facetop=")]

LAB = {'none': 0, 'cloth': 1, 'shoe': 2, 'hair': 3, 'skin': 4, 'parts': 5}
COL = np.array([[0, 0, 0], [0, 0, 1], [1, 1, 0], [0, 1, 0], [1, 0, 0], [1, 0, 1]], dtype=np.float64)
NAME = {v: k for k, v in LAB.items()}
JP = {'none': 'どこでもない', 'cloth': '服', 'shoe': '靴', 'hair': '髪', 'skin': '肌', 'parts': '目・口・眉'}

# 肌らしさの窓（見た目の色。skinclip.py と同じ）
H0, H1, S0, S1, V0 = -0.04, 0.12, 0.08, 0.45, 0.50

def log(s):
    print("[skinmask] " + str(s))

def lin2srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.maximum(c, 0) ** (1 / 2.4) - 0.055)

# ---------------------------------------------------------------- 読み込み
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
mesh = me.data
img = next(n.image for m in mesh.materials if m and m.use_nodes
           for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float64).reshape(H, W, 4)
C = np.clip(lin2srgb(A[:, :, :3]), 0, 1)
log("読み込み: 頂点 %d / 絵 %dx%d" % (len(mesh.vertices), W, H))

# ---------------------------------------------------------------- 肌らしい色か
mx = C.max(2); mn = C.min(2); d = np.maximum(mx - mn, 1e-6)
r, g, b = C[..., 0], C[..., 1], C[..., 2]
h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
hh = np.where(h > 0.5, h - 1.0, h)
skinlike = (hh > H0) & (hh < H1) & (s > S0) & (s < S1) & (mx > V0)

# ---------------------------------------------------------------- 自動でふり分ける
P = np.array([tuple(v.co) for v in mesh.vertices])
uvl = mesh.uv_layers.active.data
S = P[:, 2].max() - P[:, 2].min()
bot = P[:, 2].min()
lab = np.zeros((H, W), dtype=np.uint8)          # 0 = どこでもない
done = np.zeros((H, W), dtype=bool)

mesh.calc_loop_triangles()

def uvcover(loops, tol=-0.05):
    """三角形が実際に覆う画素だけを返す。
       囲み箱で塗ると、隣の三角形の箱と重なって四角い塗り残しが出る（髪で斑になった）。"""
    us = np.array([uvl[li].uv for li in loops], dtype=np.float64)
    xs = us[:, 0] * W; ys = us[:, 1] * H
    x0 = max(0, int(np.floor(xs.min())) - 1); x1 = min(W - 1, int(np.ceil(xs.max())) + 1)
    y0 = max(0, int(np.floor(ys.min())) - 1); y1 = min(H - 1, int(np.ceil(ys.max())) + 1)
    if x1 < x0 or y1 < y0: return None
    den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if abs(den) < 1e-12: return None
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
    l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
    l3 = 1.0 - l1 - l2
    cov = (l1 >= tol) & (l2 >= tol) & (l3 >= tol)
    if not cov.any(): return None
    return y0, y1, x0, x1, cov

# 顔の前面（目・口・眉がある所）。ここで肌でない濃い色は、髪ではなく「目・口・眉」
# 顔は「頭の中心から前を向いた円錐の中」。四角い箱で切ると、丸い頬のふちが顔から外れて
# 色を直したとき斑に見えた（ギャル少女で実際に出た）。角度で決めれば形に沿う。
head = P[P[:, 2] > bot + 0.50 * S]
ymid = np.median(head[:, 1])
# 鼻のある側が前。頭の帯で、左右の中心に近い点の前後の端を見て決める
band = head[np.abs(head[:, 0]) < 0.02 * S]
FSIGN = -1 if abs(band[:, 1].min() - ymid) > abs(band[:, 1].max() - ymid) else 1
HC = np.array([0.0, ymid, bot + 0.76 * S])       # 頭のだいたいの中心
FACE_COS = 0.50                                  # 前から約60度までを顔とみなす
FACE_TOP = float(next((v[8:] for v in a if v.startswith("facetop=")), 0.72))   # これより上は前髪。facetop= で変えられる
def in_cone(c):
    d = np.array(c) - HC
    n = np.linalg.norm(d)
    return n > 1e-6 and (d[1] / n) * FSIGN > FACE_COS

def is_face(c):
    return in_cone(c) and (c[2] - bot) / S <= FACE_TOP

for poly in mesh.loop_triangles:
    c = np.mean([P[i] for i in poly.vertices], 0)
    z = (c[2] - bot) / S
    cv = uvcover(poly.loops)
    if cv is None: continue
    y0, y1, x0, x1, cov = cv
    sl = skinlike[y0:y1 + 1, x0:x1 + 1]
    if z < 0.075:
        base, other = LAB['shoe'], LAB['shoe']       # 靴は色に関係なく靴
    elif z > 0.50:                                    # 頭
        base = LAB['hair'] if not is_face(c) else LAB['skin']
        if is_face(c):
            # 顔の中では、はっきり暗い所（目・眉・口）だけを分ける。
            # 肌らしさの窓だけで分けると、影になった肌が穴になり、色を直したとき斑に見えた。
            # 目・眉・口の輪郭は「暗い」、白目は「色味がまったく無い」で拾う
            mxb = mx[y0:y1 + 1, x0:x1 + 1]; sb = s[y0:y1 + 1, x0:x1 + 1]
            notskin = (mxb < 0.45) | ((mxb > 0.85) & (sb < 0.06))
            tile = np.where(sl | ~notskin, LAB['skin'], LAB['parts']).astype(np.uint8)
            win = lab[y0:y1 + 1, x0:x1 + 1]; dn = done[y0:y1 + 1, x0:x1 + 1]
            lab[y0:y1 + 1, x0:x1 + 1] = np.where(cov & ~dn, tile, win)
            done[y0:y1 + 1, x0:x1 + 1] |= cov
            continue
        other = LAB['hair']
    elif z < 0.20:
        base, other = LAB['skin'], LAB['cloth']      # 脚（靴下は鮮やかさが低いので服になる）
    elif z > 0.40 and abs(c[0]) < 0.10 * S:
        base, other = LAB['skin'], LAB['cloth']      # 首（ここを服にすると、あごの下に境目が出る）
    else:
        base, other = LAB['cloth'], LAB['cloth']     # 胴・スカート・腕。手は箱で足す
    tile = np.where(sl, base, other).astype(np.uint8)
    win = lab[y0:y1 + 1, x0:x1 + 1]
    dn = done[y0:y1 + 1, x0:x1 + 1]
    # 先に付いた印は残す（縁の画素は隣の三角形も覆うので、あとから消さない）
    lab[y0:y1 + 1, x0:x1 + 1] = np.where(cov & ~dn, tile, win)
    done[y0:y1 + 1, x0:x1 + 1] |= cov

log("自動: " + " / ".join("%s %.1f%%" % (JP[NAME[k]], 100 * (lab == k).mean()) for k in sorted(NAME)))

# ---------------------------------------------------------------- 箱で上書き
for spec in BOXES:
    name, nums = spec.split(':')
    only = name.endswith('?')                       # 「skin?」なら、肌らしい色の画素だけ塗り替える
    notonly = name.endswith('!')                    # 「parts!」なら、肌らしくない画素だけ塗り替える
    name = name.rstrip('?!')
    x0, x1, y0b, y1b, z0, z1 = [float(v) for v in nums.split(',')]
    n = 0
    for poly in mesh.loop_triangles:
        c = np.mean([P[i] for i in poly.vertices], 0)
        if not (x0 * S <= c[0] <= x1 * S): continue
        if not (y0b * S <= c[1] <= y1b * S): continue
        if not (z0 * S <= c[2] - bot <= z1 * S): continue
        cv = uvcover(poly.loops)
        if cv is None: continue
        n += 1
        yy0, yy1, xx0, xx1, cov = cv
        sel = cov
        if only or notonly:
            sl = skinlike[yy0:yy1 + 1, xx0:xx1 + 1]
            if notonly: sl = ~sl
            sel = cov & sl
        win = lab[yy0:yy1 + 1, xx0:xx1 + 1]
        lab[yy0:yy1 + 1, xx0:xx1 + 1] = np.where(sel, LAB[name], win)
    log("箱 %s → %s（三角形 %d%s）"
        % (spec, JP[name], n, "・肌色だけ" if only else ("・肌色でない所だけ" if notonly else "")))

log("仕上がり: " + " / ".join("%s %.1f%%" % (JP[NAME[k]], 100 * (lab == k).mean()) for k in sorted(NAME)))

# ---------------------------------------------------------------- 島の外へ少し広げる
# 三角形が覆う画素だけを塗ると、島の外側の「塗り広げ」の帯が空白のまま残る。
# そこを直さないと、絵を縮めたときに古い色がにじみ出る（texpad.py と同じ理由）。
for _ in range(4):
    e = lab == 0
    if not e.any(): break
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        src = np.roll(lab, (dy, dx), (0, 1))
        lab = np.where(e & (src != 0), src, lab)
        e = lab == 0
log("外へ広げたあと: どこでもない %.1f%%" % (100 * (lab == 0).mean()))

# ---------------------------------------------------------------- マスクを書き出す
Mi = COL[lab]
B = np.ones((H, W, 4), dtype=np.float64); B[:, :, :3] = Mi
out = bpy.data.images.new('mask', W, H)
out.colorspace_settings.name = 'Non-Color'
out.pixels = B.ravel().tolist()
out.filepath_raw = os.path.abspath(OUTMASK); out.file_format = 'PNG'; out.save()
log("マスク: %s (%.2f MB)" % (OUTMASK, os.path.getsize(OUTMASK) / 1048576.0))

# ---------------------------------------------------------------- 確認の絵（マスクを貼って3方向）
import math
from mathutils import Vector
newimg = bpy.data.images.load(os.path.abspath(OUTMASK))
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE': n.image = newimg
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith('Icosphere'): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'TEXTURE'
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
sc.view_settings.view_transform = 'Standard'
CW = 420; sc.render.resolution_x = CW; sc.render.resolution_y = CW
cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; cd.ortho_scale = S * 1.15 / 100.0 * 100.0
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
ctr = Vector((0, 0, bot + S * 0.62)) * (me.matrix_world.to_scale()[0])
ctr = me.matrix_world @ Vector((0, 0, bot + S * 0.62))
cd.ortho_scale = (me.matrix_world.to_scale()[0]) * S * 1.15
tmp = os.path.join(os.path.dirname(os.path.abspath(OUTSHOT)), '_m')
os.makedirs(tmp, exist_ok=True)
files = []
for i, az in enumerate((0, 90, 180)):
    ar = math.radians(az); R = 20
    cam.location = (ctr.x + R * math.sin(ar), ctr.y - R * math.cos(ar), ctr.z)
    cam.rotation_euler = (ctr - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmp, 'm_%d.png' % i); sc.render.filepath = p
    bpy.ops.render.render(write_still=True); files.append(p)
ims = [bpy.data.images.load(f) for f in files]
buf = np.ones((CW, CW * len(ims), 4), dtype=np.float32)
for k, im in enumerate(ims):
    px = np.empty(CW * CW * 4, dtype=np.float32); im.pixels.foreach_get(px)
    buf[:, k * CW:(k + 1) * CW] = px.reshape(CW, CW, 4)
o2 = bpy.data.images.new('o', CW * len(ims), CW); o2.pixels.foreach_set(buf.ravel())
o2.filepath_raw = os.path.abspath(OUTSHOT); o2.file_format = 'PNG'; o2.save()
log("確認の絵: %s（赤=肌 緑=髪 青=服 黄=靴 黒=どこでもない）" % OUTSHOT)
print("[skinmask] DONE")
