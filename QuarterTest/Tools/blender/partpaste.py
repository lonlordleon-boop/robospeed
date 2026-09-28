# -*- coding: utf-8 -*-
"""顔の部品（眉・目・口）の絵を、決めた位置・大きさ・傾きで顔の絵に焼き込む。

   preview.html の「福笑い」欄と同じ計算をする。ページで合わせた数字をそのまま渡せば、同じ見た目になる。
   - 部品の絵は、1枚の絵の一部を切り抜いて使える（目と口は 元気少女の目と口.png の中の四角）。
   - 中心 x, z（m）、幅（m、高さは絵の縦横比から）、傾き（度、ページと同じ向き）。
   - 顔の三角形ごとに、テクスチャの画素の位置を求め、傾きを戻して部品の絵の座標にし、双一次補間で色を拾う。
     絵の透明度で上から重ねる（ページのキャンバスと同じ）。部品は並べた順に重ねる。
   - 三角形のふちの外 2 画素も塗る。ただし、どの三角形にも属さない隙間の画素だけ（隣の三角形を上書きしない）。
   頂点は骨で動かす前の位置を使う（ページも glb の頂点をそのまま使っている）。
   書き出しは絵を PNG のまま（JPEG で重ねて圧縮しない）。

   実行: blender -b --factory-startup -P partpaste.py -- 入力.glb 部品.json 出力.png 出力.glb
   部品.json: [{"name":"左目", "img":"絵.png", "src":[x,y,幅,高さ] または null, "x":..,"z":..,"w":..,"rot":.., "len":1.0（眉の長さ、省略可）}, ...]
"""
import bpy, sys, os, json, math
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, PARTS, OUTPNG, OUTGLB = a[0], a[1], a[2], a[3]
parts = json.load(open(PARTS, encoding='utf-8'))
# 眉は最後に重ねる（preview.html の福笑いと同じ順番）。眉を先に描くと、目の部品の上端のふち（肌色がにじんだ半透明の縁）が
# 眉にかぶり、眉と目の間が狭い秀才少女で、キャラの左眉が肌色で欠けて見えた
parts = [p for p in parts if '眉' not in p['img']] + [p for p in parts if '眉' in p['img']]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data; mesh.calc_loop_triangles()
MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in mesh.vertices], dtype=np.float64)
UV = np.array([tuple(l.uv) for l in mesh.uv_layers.active.data], dtype=np.float64)
TL = np.array([tuple(t.loops) for t in mesh.loop_triangles]); TV = np.array([tuple(t.vertices) for t in mesh.loop_triangles])
img = next(n.image for m in mesh.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)     # 下の行が先頭

def tri_pix(t, tolpx):
    px = UV[TL[t]] * np.array([W, H])
    x0, x1 = max(0, int(np.floor(px[:,0].min() - tolpx))), min(W-1, int(np.ceil(px[:,0].max() + tolpx)))
    y0, y1 = max(0, int(np.floor(px[:,1].min() - tolpx))), min(H-1, int(np.ceil(px[:,1].max() + tolpx)))
    if x1 < x0 or y1 < y0: return None
    (ax, ay), (bx, by), (cx, cy) = px
    det = (bx-ax)*(cy-ay) - (cx-ax)*(by-ay)
    if abs(det) < 1e-9: return None
    xs, ys = np.meshgrid(np.arange(x0, x1+1), np.arange(y0, y1+1))
    sx, sy = xs.ravel() + 0.5, ys.ravel() + 0.5
    l1 = ((bx-sx)*(cy-sy) - (cx-sx)*(by-sy)) / det
    l2 = ((cx-sx)*(ay-sy) - (ax-sx)*(cy-sy)) / det
    l3 = 1 - l1 - l2
    def hgt(p, q): return abs(det) / max(np.hypot(q[0]-p[0], q[1]-p[1]), 1e-9)
    h1, h2, h3 = hgt(px[1], px[2]), hgt(px[2], px[0]), hgt(px[0], px[1])
    ok = (l1 >= -tolpx/h1 - 1e-6) & (l2 >= -tolpx/h2 - 1e-6) & (l3 >= -tolpx/h3 - 1e-6)
    return ys.ravel()[ok], xs.ravel()[ok], np.stack([l1[ok], l2[ok], l3[ok]], 1)

# 眉は、元の絵で肌の画素にだけ描く（前髪の上に眉が乗って見えないように。ギャル少女で眉が金髪の前髪の上に出た）。
# 肌 = 赤>=緑>=青・明るい・鮮やかさが低い。おでこの肌は 明るさ1.0・鮮やかさ0.19〜0.24、金髪の前髪は鮮やかさ0.30以上、黒髪は暗い。
# 境目はなだらかにする（鮮やかさ 0.28〜0.34、明るさ 0.85〜0.92）
_C = A[..., :3]; _mx = _C.max(-1); _mn = _C.min(-1); _s = np.where(_mx > 0, (_mx - _mn) / np.maximum(_mx, 1e-6), 0)
SKINW = ((_C[..., 0] >= _C[..., 1]) & (_C[..., 1] >= _C[..., 2])).astype(np.float32) \
        * np.clip((0.34 - _s) / 0.06, 0, 1) * np.clip((_mx - 0.85) / 0.07, 0, 1)

owned = np.zeros((H, W), bool)
for t in range(len(TV)):
    r = tri_pix(t, 0.0)
    if r is not None: owned[r[0], r[1]] = True

cache = {}
for p in parts:
    if p['img'] not in cache:
        im = bpy.data.images.load(p['img']); iw, ih = im.size
        cache[p['img']] = np.array(im.pixels[:], dtype=np.float32).reshape(ih, iw, 4)[::-1].copy()   # 上の行が先頭
    D = cache[p['img']]
    if p.get('src'):
        sx0, sy0, sw, sh = p['src']; D = D[sy0:sy0+sh, sx0:sx0+sw].copy()
        # SKINCUT: 目と口の部品のふちに残った肌色の画素を透明にする（preview.html と同じ判定）。
        # 肌色 = 赤 >= 緑 >= 青、鮮やかさ 0.08〜0.45、明るさ 0.60 以上。白目・瞳・まつ毛・舌は外れる
        r_, g_, b_ = D[..., 0], D[..., 1], D[..., 2]
        mx_ = D[..., :3].max(-1); mn_ = D[..., :3].min(-1); s_ = np.where(mx_ > 0, (mx_ - mn_) / np.maximum(mx_, 1e-6), 0)
        cut = (r_ >= g_) & (g_ >= b_) & (s_ >= 0.08) & (s_ <= 0.45) & (mx_ >= 0.60)
        D[cut, 3] = 0.0
    DH, DW = D.shape[:2]
    cx, cz, mw, rot = p['x'], p['z'], p['w'], p['rot']
    mh = mw * DH / DW
    # 眉の「長さ」（preview.html の福笑いの長さスライダー）。横だけ伸ばし、高さ（太さ）は変えない
    mw = mw * p.get('len', 1.0)
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    R = 0.8 * max(mw, mh)
    done = np.zeros((H, W), bool); n = 0
    for tolpx in (0.0, 2.0):
        for t in range(len(TV)):
            Q = P[TV[t]]
            # ページと同じ選び方: 三角形の範囲が中心から R の範囲と重なる、前面（Blender の y が -0.12 より前）。
            # 前は3頂点とも R 以内の三角形だけを塗っていたので、おでこの三角形が大きい秀才少女で眉の真ん中が欠けた
            if Q[:,0].max() < cx-R or Q[:,0].min() > cx+R or Q[:,2].max() < cz-R or Q[:,2].min() > cz+R or np.any(Q[:,1] > -0.12): continue
            r = tri_pix(t, tolpx)
            if r is None: continue
            ys, xs, L = r
            sel = ~done[ys, xs]
            if tolpx > 0: sel &= ~owned[ys, xs]
            ys, xs, L = ys[sel], xs[sel], L[sel]
            if not len(ys): continue
            wp = L @ Q
            dx, dz = wp[:,0] - cx, wp[:,2] - cz
            rx = dx*c + dz*s; ry = -dx*s + dz*c
            u = (rx/mw + 0.5) * DW - 0.5; v = (-ry/mh + 0.5) * DH - 0.5
            inside = (u > -1) & (u < DW) & (v > -1) & (v < DH)
            ys, xs, u, v = ys[inside], xs[inside], u[inside], v[inside]
            if not len(ys): continue
            u0 = np.clip(np.floor(u).astype(int), 0, DW-1); v0 = np.clip(np.floor(v).astype(int), 0, DH-1)
            u1 = np.clip(u0+1, 0, DW-1); v1 = np.clip(v0+1, 0, DH-1)
            fu = np.clip(u - np.floor(u), 0, 1)[:, None]; fv = np.clip(v - np.floor(v), 0, 1)[:, None]
            # 範囲外の端は透明として補間する
            def px_(vv, uu):
                q = D[vv, uu].copy()
                return q
            smp = (px_(v0,u0)*(1-fu)*(1-fv) + px_(v0,u1)*fu*(1-fv) + px_(v1,u0)*(1-fu)*fv + px_(v1,u1)*fu*fv)
            al = smp[:, 3:4]
            if '眉' in p['img']: al = al * SKINW[ys, xs][:, None]
            col = np.where(al > 1e-4, smp[:, :3] / np.maximum(al, 1e-4), 0) if False else smp[:, :3]
            A[ys, xs, :3] = A[ys, xs, :3] * (1 - al) + col * al
            done[ys, xs] = True; n += len(ys)
    print("PP %s: 中心 x %.4f z %.4f 幅 %.4f 高さ %.4f 傾き %.0f度  塗った画素 %d" % (p.get('name', '?'), cx, cz, mw, mh, rot, n))

img.pixels = A.ravel().tolist()
img.filepath_raw = OUTPNG; img.file_format = 'PNG'; img.save()
newimg = bpy.data.images.load(OUTPNG)
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for nd in m.node_tree.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image == img: nd.image = newimg
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUTGLB, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='AUTO')
print("PP 書き出し", OUTGLB, os.path.getsize(OUTGLB))
