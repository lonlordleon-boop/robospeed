# -*- coding: utf-8 -*-
# 塗り替えたあとの絵に、元の絵で「はっきり鮮やかな赤の面」（ランドセル）の画素だけを戻す。
# 面の中央値（元の絵）が 赤の色相・鮮やかさ >= SMIN・明るさ >= 0.25 で、高さの範囲に入る面が対象。
# 実行: blender -b --factory-startup -P restorered.py -- 形の.glb 元の絵.png 塗った絵.png 出力.png z0,z1 SMIN [背中側 y 下限] [この高さより上は y に関係なく戻す]
# 例（秀才少女のランドセル）: ... 0.20,0.66 0.55 0.05 0.395
import bpy, sys, colorsys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, ORIG, NEW, OUT = a[0], a[1], a[2], a[3]
Z0, Z1 = [float(v) for v in a[4].split(",")]; SMIN = float(a[5])
YMIN = float(a[6]) if len(a) > 6 else -9.0; ZUP = float(a[7]) if len(a) > 7 else 9.0   # 背中側 y の下限、これより上の高さは y に関係なく戻す
# 9番目に skin と書くと、赤の面ではなく「肌の面」（中央値が 色相0.02〜0.11・鮮やかさ0.10〜0.45・明るさ0.45以上）を戻す。
# スカートの赤を塗り替えたとき、裾の影で赤っぽく塗られていた内股の肌まで色が付いたため
MODE = a[8] if len(a) > 8 else 'red'
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE"); arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
em = me.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); uvl = em.uv_layers.active.data; em.calc_loop_triangles()
def load(p):
    im = bpy.data.images.load(p); w, h = im.size
    return np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4), w, h
O, W, H = load(ORIG); N, _, _ = load(NEW)
cnt = 0; px = 0
for t in em.loop_triangles:
    c = P[list(t.vertices)].mean(0)
    if not (Z0 <= c[2] <= Z1): continue
    if not (c[1] >= YMIN or c[2] >= ZUP): continue   # スカートの前と横は戻さない（チェックの赤い升目まで戻ってしまう）
    uv = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    xs = uv[:, 0]*W; ys = uv[:, 1]*H
    x0 = max(0, int(np.floor(xs.min()))-1); x1 = min(W-1, int(np.ceil(xs.max()))+1)
    y0 = max(0, int(np.floor(ys.min()))-1); y1 = min(H-1, int(np.ceil(ys.max()))+1)
    gx, gy = np.meshgrid(np.arange(x0, x1+1)+0.5, np.arange(y0, y1+1)+0.5)
    d = (ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(d) < 1e-12: continue
    l1 = ((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/d
    l2 = ((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/d
    m = (l1 >= -0.05) & (l2 >= -0.05) & (1-l1-l2 >= -0.05)
    ob = O[y0:y1+1, x0:x1+1]
    inside = (l1 >= 0) & (l2 >= 0) & (1-l1-l2 >= 0)
    ref = ob[..., :3][inside] if inside.sum() >= 3 else ob[..., :3][m]
    if len(ref) == 0: continue
    h, s, v = colorsys.rgb_to_hsv(*np.median(ref, 0))
    if MODE == 'skin':
        if not (0.02 <= h <= 0.11 and 0.10 <= s <= 0.45 and v >= 0.45): continue
    elif not ((h < 0.05 or h > 0.95) and s >= SMIN and v >= 0.25): continue
    nb = N[y0:y1+1, x0:x1+1]
    nb[m] = ob[m]; N[y0:y1+1, x0:x1+1] = nb
    cnt += 1; px += int(m.sum())
print("RR 戻した面 %d  画素 %d" % (cnt, px))
out = bpy.data.images.new("o", W, H); out.pixels = N.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save(); print("RR 書き出し", OUT)
