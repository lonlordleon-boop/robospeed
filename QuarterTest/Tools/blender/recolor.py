# -*- coding: utf-8 -*-
"""服や鞄の色だけを塗り替える。
   テクスチャは面ごとにバラバラに並んでいるので、画像の上で「服のあたり」を選ぶことはできない。
   そこで画素ごとに「モデルのどこに当たるか」を求め、位置の箱と色合い（色相）の両方が合うものだけを塗り替える。
   明るさと鮮やかさは元のまま残すので、しま模様や陰影はそのまま生きる。
   規則の書き方（複数ある場合は ; で区切る）:
     xlo,xhi,ylo,yhi,zlo,zhi|色相の下限,上限|新しい色相,鮮やかさ倍率,明るさ倍率[,鮮やかさの下限][,面まとめの割合][,面まとめのときの下限][,ばらつきの残し具合][,明るさの下限]
   鮮やかさの下限は、これより くすんだ画素を塗り替えないための線引き（省略すると 0.20）。
   肌は約0.3、服の赤は約0.87なので、赤い服だけを塗り替えたいときは 0.55 くらいを指定する。
   面まとめの割合を書くと、まず面ごとに「その面は服か」を判定する。
   面の画素のうち、はっきりその色をしているものがこの割合を超えたら、その面は服とみなし、
   色相の窓を広げて（±0.06）まとめて塗り替える。
   境目の画素は赤と隣の色が混ざって色相がずれるため、画素ごとの判定では取り残されて
   ふちに細い赤線が残る。面ごとに決めれば、その面の中の混ざった画素もいっしょに塗り替えられる。
   肌の面には はっきりした服の色が無いので、まるごと除外され、肌に色が乗ることもない。
   面まとめのときの下限（省略すると 0.18）は、しま模様の白を残すためのもの。
   明るさを落とす塗り替えでは、ここを 0.05 くらいまで下げないと、面のふちに網目模様が出る。
   ばらつきの残し具合（省略すると 1.0＝そのまま）は、鮮やかさと明るさの散らばりをどれだけ残すか。
   面のふちの画素はもともと少し暗く、鮮やかさも低い。鮮やかさや明るさを大きく落とす塗り替えでは、
   その差が目立って網目模様に見える。0.3 くらいにすると、陰影は残したまま模様が消える。
   8番目の明るさの下限（省略すると 0＝下限なし）は、元の明るさがこれより暗い画素を塗り替えない。
   芸術少女は髪が暗い紫で、服の淡い紫と色相が近く、肩にかかる毛先まで塗り替わった。
   髪がかかる高さの規則にだけ 0.5 を付けて、暗い髪を外す（靴の暗い影まで外れないよう、低い所の規則には付けない）。
   色相は 0〜1（赤=0、黄=0.13、緑=0.33、水色=0.5、青=0.62、紫=0.78、桃=0.92）。
   実行: blender -b --factory-startup -P recolor.py -- 入力.glb 出力テクスチャ.png 規則"""
import bpy, sys, colorsys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
# mask=マスク.png[:ラベル]（skinmask.py で作ったもの）を渡すと、そのラベルの画素だけを塗り替える。
# ラベルは cloth（既定）/ hair / skin / shoe / parts。色相の窓で肌や髪を取りこぼす心配がなくなる。
MASKARG = next((v[5:] for v in a if v.startswith('mask=')), None)
a = [v for v in a if not v.startswith('mask=')]
SRC, OUT = a[0], a[1]
RULES = []
for r in a[2].split(';'):
    box, hr, to = r.split('|')
    RULES.append(([float(x) for x in box.split(',')],
                  [float(x) for x in hr.split(',')],
                  [float(x) for x in to.split(',')]))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data
uvl = mesh.uv_layers.active.data
img = None
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
MW = me.matrix_world
print("RC テクスチャ %dx%d、規則 %d 個" % (W, H, len(RULES)))

MASKSEL = None
if MASKARG:
    import os
    mpath, _, mlab = MASKARG.partition(':')
    mlab = mlab or 'cloth'
    mi = bpy.data.images.load(os.path.abspath(mpath))
    if tuple(mi.size) != (W, H):
        print("RC ！ マスクの大きさが絵と違う（%dx%d と %dx%d）" % (mi.size[0], mi.size[1], W, H)); sys.exit(1)
    MM = np.array(mi.pixels[:], dtype=np.float32).reshape(H, W, 4)[..., :3] > 0.5
    WANT = {'skin': (1, 0, 0), 'hair': (0, 1, 0), 'cloth': (0, 0, 1),
            'shoe': (1, 1, 0), 'parts': (1, 0, 1)}[mlab]
    MASKSEL = np.ones((H, W), bool)
    for k in range(3):
        MASKSEL &= (MM[..., k] == bool(WANT[k]))
    print("RC マスクを使う: %s の %s（%d 画素・%.1f%%）" % (mpath, mlab, MASKSEL.sum(), 100*MASKSEL.mean()))

def hue_in(h, lo, hi):
    return (lo <= h <= hi) if lo <= hi else (h >= lo or h <= hi)   # 赤は 0 をまたぐ

# 一巡目：規則ごとに「その材質のふつうの鮮やかさ・明るさ」を測る。
# 二巡目でここへ寄せることで、面のふちの散らばりを抑える。
def scan_median():
    acc = [[] for _ in RULES]
    for f in mesh.polygons:
        c = MW @ f.center
        hit = [i for i, (b, _, _) in enumerate(RULES)
               if b[0]-0.05 <= c.x <= b[1]+0.05 and b[2]-0.05 <= c.y <= b[3]+0.05 and b[4]-0.05 <= c.z <= b[5]+0.05]
        if not hit: continue
        uv = [uvl[li].uv for li in f.loop_indices]
        u = (sum(t.x for t in uv)/len(uv), sum(t.y for t in uv)/len(uv))
        px = int(u[0]*W) % W; py = int(u[1]*H) % H
        hh, ss, vv = colorsys.rgb_to_hsv(float(A[py,px,0]), float(A[py,px,1]), float(A[py,px,2]))
        if MASKSEL is not None and not MASKSEL[py, px]: continue    # マスクの外は基準にも入れない
        for i in hit:
            box, hr, to = RULES[i]
            smin = to[3] if len(to) > 3 else 0.20
            if ss >= smin and hue_in(hh, hr[0], hr[1]): acc[i].append((ss, vv))
    out = []
    for i, lst in enumerate(acc):
        if lst:
            arr = np.array(lst)
            out.append((float(np.median(arr[:,0])), float(np.median(arr[:,1]))))
        else:
            out.append((0.7, 0.9))
        print("RC 規則%d の基準 鮮やかさ%.2f 明るさ%.2f（%d面）" % (i+1, out[i][0], out[i][1], len(lst)))
    return out
BASE = scan_median()

counts = [0]*len(RULES)
# 画素は1回だけ塗る。三角形のふちの画素は隣の三角形の枠にも入るので、塗り替えたあとの色がもう一度窓に入ると
# （面まとめで窓を ±0.06 広げたとき、赤 0.99 が 0.04〜0.22 の窓に入った）鮮やかさが二重に掛かり、網目の線が浮き出た（わんぱく少女のベスト）
PAINTED = np.zeros((H, W), bool)
for f in mesh.polygons:
    c = MW @ f.center
    hit = [i for i, (b, _, _) in enumerate(RULES)
           if b[0]-0.05 <= c.x <= b[1]+0.05 and b[2]-0.05 <= c.y <= b[3]+0.05 and b[4]-0.05 <= c.z <= b[5]+0.05]
    if not hit: continue
    vs = [mesh.vertices[v].co for v in f.vertices]
    uv = [uvl[li].uv for li in f.loop_indices]
    for i in range(1, len(vs)-1):
        tri = [vs[0], vs[i], vs[i+1]]; tuv = [uv[0], uv[i], uv[i+1]]
        xs = [t.x*W for t in tuv]; ys = [t.y*H for t in tuv]
        x0 = max(0, int(min(xs))-1); x1 = min(W-1, int(max(xs))+1)
        y0 = max(0, int(min(ys))-1); y1 = min(H-1, int(max(ys))+1)
        den = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(den) < 1e-12 or x1 < x0 or y1 < y0: continue
        # まずこの面が使っている画素を集める
        cells = []
        for py in range(y0, y1+1):
            for px in range(x0, x1+1):
                gx, gy = px+0.5, py+0.5
                l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2]))/den
                l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2]))/den
                l3 = 1.0 - l1 - l2
                if l1 < -0.05 or l2 < -0.05 or l3 < -0.05: continue
                p = MW @ (tri[0]*l1 + tri[1]*l2 + tri[2]*l3)
                r, g, b = float(A[py, px, 0]), float(A[py, px, 1]), float(A[py, px, 2])
                cells.append((px, py, p, colorsys.rgb_to_hsv(r, g, b)))
        if not cells: continue

        for i in hit:
            box, hr, to = RULES[i]
            smin = to[3] if len(to) > 3 else 0.20
            gate = to[4] if len(to) > 4 else 0.0
            wslim = to[5] if len(to) > 5 else 0.18
            inbox = [c for c in cells
                     if box[0] <= c[2].x <= box[1] and box[2] <= c[2].y <= box[3] and box[4] <= c[2].z <= box[5]]
            if not inbox: continue
            wide = False
            if gate > 0.0:
                # はっきりその色をしている画素が、この面のどれくらいを占めるか
                n = sum(1 for c in inbox if c[3][1] >= smin and hue_in(c[3][0], hr[0], hr[1]))
                if n >= gate*len(inbox): wide = True
            lo, hi = (hr[0]-0.06, hr[1]+0.06) if wide else (hr[0], hr[1])
            lo %= 1.0; hi %= 1.0
            # 面ごとにまとめて塗るときの下限。
            # ここを高くしたままで明るさを落とすと、面のふちの淡い画素だけが塗り残されて、
            # 暗くなった地の上に明るい網目模様として浮き出る。
            slim = wslim if wide else smin
            for px, py, p, (hh, ss, vv) in inbox:
                if MASKSEL is not None and not MASKSEL[py, px]: continue   # マスクの外は触らない
                if PAINTED[py, px]: continue
                if ss < slim: continue                    # 白やごく淡い色は残す（しまの白など）
                if len(to) > 7 and vv < to[7]: continue   # 明るさの下限（暗い髪を外す）
                if not hue_in(hh, lo, hi): continue
                keep = to[6] if len(to) > 6 else 1.0
                bs, bv = BASE[i]
                ns = (bs + (ss - bs)*keep) * to[1]
                nv = (bv + (vv - bv)*keep) * to[2]
                nr, ng, nb = colorsys.hsv_to_rgb(to[0], min(1.0, max(0.0, ns)), min(1.0, max(0.0, nv)))
                A[py, px, 0], A[py, px, 1], A[py, px, 2] = nr, ng, nb
                PAINTED[py, px] = True
                counts[i] += 1
for i, n in enumerate(counts):
    print("RC 規則%d で塗り替えた画素 %d" % (i+1, n))

out = bpy.data.images.new("recolor", W, H, alpha=True)
out.pixels = A.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("RC 書き出し", OUT)
