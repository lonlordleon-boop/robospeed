# 耳を戻す（3版）：耳の島の画素と、すき間（どの面も使っていない画素）のうち「耳の島の方が、ほかの面の画素より近い」ものだけを v20 の色に戻す。
# 2版はすき間を耳のまわり 4 画素ぜんぶ戻したので、絵の上で耳のとなりにある髪の房のふちまで肌色がにじんだ
# お嬢様（小学生編）は v21 で耳を髪の色に塗った（islandpaint.py、言われていない変更）。「耳を出して欲しい」と言われて戻した（v26）
# 実行: blender -b --factory-startup -P earback.py -- 塗る前.glb 今の.glb 耳のマスク.png 出力.png 4 → swaptex.py で今の glb に貼る
import bpy, sys, numpy as np
a = sys.argv[sys.argv.index("--")+1:]; V20, V25, MASK, OUT, D = a[0], a[1], a[2], a[3], int(a[4])
def load(p):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=p)
    me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
    img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    return me, np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)
_, p20 = load(V20); me, p25 = load(V25); H, W = p25.shape[:2]
ear = np.array(bpy.data.images.load(MASK).pixels[:], np.float32).reshape(H, W, 4)[..., 1] > 0.5
# どの面かが使っている画素（v25 の UV で三角を塗る。すき間を少し広めに見ないよう内側だけ）
used = np.zeros((H, W), bool); m = me.data; uvl = m.uv_layers.active.data
for p in m.polygons:
    uv = np.array([uvl[li].uv[:] for li in p.loop_indices]) * [W, H]
    x0, y0 = np.floor(uv.min(0)).astype(int); x1, y1 = np.ceil(uv.max(0)).astype(int)
    x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W-1); y1 = min(y1, H-1)
    if x1 < x0 or y1 < y0: continue
    xs, ys = np.meshgrid(np.arange(x0, x1+1)+.5, np.arange(y0, y1+1)+.5)
    for k in range(1, len(uv)-1):
        (ax, ay), (bx, by), (cx, cy) = uv[0], uv[k], uv[k+1]; d = (by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(d) < 1e-12: continue
        l1 = ((by-cy)*(xs-cx)+(cx-bx)*(ys-cy))/d; l2 = ((cy-ay)*(xs-cx)+(ax-cx)*(ys-cy))/d
        used[y0:y1+1, x0:x1+1] |= (l1 >= 0) & (l2 >= 0) & (1-l1-l2 >= 0)
other = used & ~ear
# 耳と、ほかの面の画素から同時に 1 画素ずつ広げ、先に届いた方のものにする（同時なら、ほかの面のもの）
lab = np.zeros((H, W), np.int8); lab[other] = 2; lab[ear] = 1
def grow(msk):
    r = msk.copy(); r[1:] |= msk[:-1]; r[:-1] |= msk[1:]; r[:, 1:] |= msk[:, :-1]; r[:, :-1] |= msk[:, 1:]; return r
for _ in range(D):
    free = lab == 0; g2 = grow(lab == 2) & free; g1 = grow(lab == 1) & free & ~g2
    lab[g2] = 2; lab[g1] = 1
gut = (lab == 1) & ~ear
print("EB3 耳の画素", int(ear.sum()), "戻すすき間", int(gut.sum()), "（2版は 13101）")
res = p25.copy(); sel = ear | gut; res[sel] = p20[sel]
im = bpy.data.images.new("o", W, H, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save(); print("EB3 書き出し", OUT)
