# -*- coding: utf-8 -*-
"""高さで区切った区画を、決めた一色（肌色か白）＋なだらかな陰影で塗り直す。

   skinclean.py（汚れた画素だけを近くの色で埋める方式）は、脚の緑の筋を茶色の筋に
   置き換えただけで、靴下と肌の境目も直せなかった。理由は二つ。
     ・「近くのきれいな画素」にも焼き込まれた陰影が混ざっていて、それを平均すると
       まだら模様になる。
     ・靴下に入り込んだ肌色、肌に入り込んだ白は、色だけ見れば「正しい色」なので
       汚れと判定できない。
   そこでこの道具は、区画を高さ（z）で切り、区画ごとに「ここは肌」「ここは靴下」と
   決め打ちして、その区画にある画素を対象の色で塗りつぶす。陰影は、まわり40点の
   明るさの中央値からなだらかに作り直す（細い筋や斑は消え、丸みだけ残る）。

   区画は「x下,x上,y下,y上,z下,z上:種類」を ; でつないで複数書ける。種類は
     skin  … 肌。白も肌にする（靴下が肌に入り込んだ所を直す）
     face  … 肌だが白は残す（顎の下。襟の白を守る）
     white … 白（靴下）。肌色も白にする
     legs  … 靴下と脚をまとめて。靴下の上端は「上を向いた面」の高さから左右の脚ごとに
             自動で見つけ、その下を white、上を skin として塗る。高さで真横に切ると
             靴下の縁や靴の口に食い込むので、脚はこれを使うこと。
     cloth … 白い服。うすい肌色（服に入り込んだ肌）と白だけを白にし、灰色（ベストや影）と
             はっきりした肌（手・首）は残す。
     cloth! … 白い服。灰色も白にする（服に焼き込まれた髪の影を消すとき）。
     white! … 靴下。暗い所だけを残して全部白にする（靴下に入り込んだ靴の紺色を消すとき）。
             靴が区画に入らないよう、下限の高さは靴の口より上にすること。
   種類のうしろに @数字 を付けると、その区画だけ陰影の強さを変えられる（例 legs@0.25）。
   白の区画では、靴の茶色（鮮やかで暗い色）は触らない。
   どの種類でも、暗い所（髪・靴）、鮮やかな赤（口・紐・スカート）、青緑（縞）は触らない
   （white! だけは暗い所以外を全部塗る）。
   Blender の画像は下の行が先頭。UV の v はそのまま行番号に使う。

   実行: blender -b --factory-startup -P zonepaint.py -- 入力.glb 出力.png "区画;区画;..." [陰影の強さ 既定0.5]
"""
import bpy, sys, colorsys
import numpy as np
from mathutils import kdtree

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
ZONES = []
for z in a[2].split(';'):
    box, kind = z.split(':'); kind = kind.strip(); sh = None
    if '@' in kind: kind, sh = kind.split('@'); sh = float(sh)
    ZONES.append(([float(v) for v in box.split(',')], kind, sh))
SHADE = float(a[3]) if len(a) > 3 else 0.5

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data; uvl = mesh.uv_layers.active.data
img = None
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
MW = me.matrix_world
print("ZP テクスチャ %dx%d、区画 %d 個" % (W, H, len(ZONES)))

def texels(f):
    vs = [mesh.vertices[v].co for v in f.vertices]
    uv = [uvl[li].uv for li in f.loop_indices]
    out = []
    for i in range(1, len(vs)-1):
        tri = [vs[0], vs[i], vs[i+1]]; tuv = [uv[0], uv[i], uv[i+1]]
        xs = [t.x*W for t in tuv]; ys = [t.y*H for t in tuv]
        x0 = max(0, int(min(xs))-1); x1 = min(W-1, int(max(xs))+1)
        y0 = max(0, int(min(ys))-1); y1 = min(H-1, int(max(ys))+1)
        den = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(den) < 1e-12 or x1 < x0 or y1 < y0: continue
        for py in range(y0, y1+1):
            for px in range(x0, x1+1):
                gx, gy = px+0.5, py+0.5
                l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2]))/den
                l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2]))/den
                l3 = 1.0 - l1 - l2
                if l1 < -0.05 or l2 < -0.05 or l3 < -0.05: continue
                out.append((px, py, MW @ (tri[0]*l1 + tri[1]*l2 + tri[2]*l3)))
    return out

def hsv(c): return colorsys.rgb_to_hsv(float(c[0]), float(c[1]), float(c[2]))
def lum(c): return 0.299*c[0] + 0.587*c[1] + 0.114*c[2]
def is_dark(h, s, v, kind): return v < 0.20   # 靴下の縁の暗い筋も白にしたいので、白の区画でも低めにしてある
def is_red(h, s, v): return s > 0.45 and (h < 0.06 or h > 0.93)
def is_cool(h, s, v): return 0.25 < h < 0.85 and s > 0.22
def is_white(h, s, v): return s < 0.12 and v > 0.70
def is_skin(h, s, v): return (h <= 0.13 or h > 0.95) and 0.13 <= s <= 0.62 and v >= 0.55

def paint(kind, box, items, shade=None):
    """items = [(px,py,p,色)]。kind の決まりで塗る対象を選び、一色＋なだらかな陰影で塗る"""
    global total
    SH = SHADE if shade is None else shade
    to_white = kind in ('white', 'white!', 'cloth', 'cloth!')
    cand = []; ref = []
    for px, py, p, c in items:
        h, s, v = hsv(c)
        warm = (h <= 0.13 or h > 0.95)
        if kind == 'white':
            if not ((s < 0.35 and v >= 0.20) or is_skin(h, s, v)): continue   # 靴の茶色（鮮やかで暗い）は除く
        elif kind == 'white!':
            if v < 0.20: continue
        elif kind in ('cloth', 'cloth!'):
            if is_dark(h, s, v, kind) or is_red(h, s, v) or is_cool(h, s, v): continue
            strong_skin = warm and s >= 0.22 and v >= 0.50          # 手や首。残す
            beige = warm and 0.08 <= s < 0.22 and v >= 0.45         # 服に入り込んだ肌色
            white = s < 0.08 and v > 0.75
            grey = s < 0.08 and 0.35 <= v <= 0.75                   # ベストや焼き込まれた影
            if strong_skin: continue
            if not (beige or white or (grey and kind == 'cloth!')): continue
        else:
            if is_dark(h, s, v, kind) or is_red(h, s, v) or is_cool(h, s, v): continue
            if kind == 'face' and is_white(h, s, v): continue
        cand.append((px, py, p, lum(c)))
        if (to_white and is_white(h, s, v)) or (not to_white and is_skin(h, s, v)):
            ref.append(c)
    if not cand:
        print("ZP %s 区画 %s に画素が無い" % (kind, box)); return
    if len(ref) >= 300:
        M = np.median(np.array(ref, np.float32), axis=0)
    else:
        M = np.array([0.90, 0.90, 0.92] if to_white else [0.62, 0.45, 0.42], np.float32)
        print("ZP 【注意】基準になる色が %d 画素しか無いので、決め打ちの色を使う" % len(ref))
    # 陰影：まわり40点の明るさの中央値をなだらかな陰影として使う（8画素に1つを目印にする）
    sub = cand[::8]
    kd = kdtree.KDTree(len(sub))
    for i, (_, _, p, _) in enumerate(sub): kd.insert(p, i)
    kd.balance()
    Ls = np.empty(len(cand), np.float32)
    for i, (_, _, p, _) in enumerate(cand):
        hits = kd.find_n(p, 40)
        Ls[i] = np.median([sub[j][3] for (_, j, _) in hits])
    Lz = float(np.median(Ls)); Lm = float(lum(M))
    for i, (px, py, p, _) in enumerate(cand):
        Lt = Lm + SH*(Ls[i] - Lz)
        A[py, px, :3] = np.clip(M * (Lt / max(1e-4, Lm)), 0.0, 1.0)
    total += len(cand)
    print("ZP %-5s 塗った画素 %d、基準の色 %s、陰影の幅 %.2f〜%.2f"
          % (kind, len(cand), np.round(M, 3), float(Ls.min()), float(Ls.max())))

total = 0
for box, kind, shade in ZONES:
    def inbox(p): return box[0] <= p.x <= box[1] and box[2] <= p.y <= box[3] and box[4] <= p.z <= box[5]
    faces = [f for f in mesh.polygons if inbox(MW @ f.center)]
    if kind != 'legs':
        items = []
        for f in faces:
            for px, py, p in texels(f):
                if inbox(p): items.append((px, py, p, A[py, px, :3]))
        print("ZP %s 面 %d 枚" % (kind, len(faces)))
        paint(kind, box, items, shade)
        continue
    # ---- legs：靴下の上端を左右の脚ごとに見つける ----
    # 上を向いた面（靴下の縁の上面）のうち暗くないものの高さを集め、その上のほうの値を縁の高さにする
    R = MW.to_3x3()
    ledge = {}
    for side in (-1, 1):
        zs = []
        for f in faces:
            c = MW @ f.center
            if (c.x < 0) != (side < 0): continue
            n = (R @ f.normal).normalized()
            if n.z < 0.5: continue
            uv = [uvl[li].uv for li in f.loop_indices]
            cx = sum(u.x for u in uv)/len(uv); cy = sum(u.y for u in uv)/len(uv)
            col = A[min(H-1, int(cy*H)), min(W-1, int(cx*W)), :3]
            if hsv(col)[2] < 0.35: continue
            zs.append(c.z)
        ledge[side] = float(np.percentile(zs, 85)) if zs else (box[4]+box[5])/2
    print("ZP legs 靴下の上端  左(x<0) %.3f  右(x>0) %.3f" % (ledge[-1], ledge[1]))
    sock_items = []; skin_items = []
    for f in faces:
        c = MW @ f.center
        top = ledge[-1] if c.x < 0 else ledge[1]
        dst = sock_items if c.z <= top + 0.004 else skin_items
        for px, py, p in texels(f):
            if inbox(p): dst.append((px, py, p, A[py, px, :3]))
    print("ZP legs 面 %d 枚（靴下側 %d 画素、脚側 %d 画素）" % (len(faces), len(sock_items), len(skin_items)))
    paint('white!', box, sock_items, shade)      # 靴下。靴の色が入り込んだ所も白にする
    paint('skin', box, skin_items, shade)

print("ZP 合計 %d 画素" % total)
out = bpy.data.images.new("zoned", W, H, alpha=True)
out.pixels = A.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("ZP 書き出し", OUT)
