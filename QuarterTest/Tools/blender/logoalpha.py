# タイトルロゴ（白背景）の白を抜いて透過PNGにする
# 実行: blender -b --factory-startup -P logoalpha.py -- 入力.png 出力.png 確かめ用の重ね絵.png（2026-09-23、タイトルロゴ案2で使用）
import bpy, numpy as np, sys
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT, PRE = a
im = bpy.data.images.load(SRC); W,H = im.size
A = np.array(im.pixels[:],np.float32).reshape(H,W,4)
BG = 0.996
d = np.clip((BG - A[...,:3].min(-1))/BG, 0, 1)          # 白からの離れ具合
T0, K = 0.02, 0.20
soft = np.clip((d - T0)/K, 0, 1)                         # 縁はなめらかに透ける
def grow(m,n,op):
    for _ in range(n):
        g=m.copy()
        for s,ax in ((1,0),(-1,0),(1,1),(-1,1)):
            r=np.roll(m,s,ax); g = (g|r) if op=='or' else (g&r)
        m=g
    return m
core = d > 0.10
core = grow(grow(core,4,'or'),4,'and')                   # 水彩のかすれの小さな穴は埋める（字の中の空きは大きいので残る）
core &= d > 0.035                                        # ほぼ白の所（内側の角に入りこんだ背景）は埋めない。埋めると白い粒になった
alpha = np.maximum(soft, core.astype(np.float32))
# 透ける所は、白と混ざっていた分を戻して色を濃くする（白の上に重ねると元どおりの見た目）
out = A.copy()
part = (alpha < 1) & (alpha > 0)
for c in range(3):
    ch = A[...,c]
    out[...,c] = np.where(part, np.clip(1 - (1-ch)/np.maximum(alpha,1e-3), 0, 1), ch)
out[...,3] = alpha
out[alpha==0,:3] = 1
print("OPAQUE %.3f PART %.3f CLEAR %.3f" % ((alpha==1).mean(), part.mean(), (alpha==0).mean()))
o = bpy.data.images.new('o',W,H,alpha=True); o.pixels.foreach_set(out.ravel())
o.filepath_raw = OUT; o.file_format='PNG'; o.save()
# 確かめ用：濃い紺・芝の緑・市松に重ねる
h2,w2 = H//2, W//2
def over(bg):
    return out[...,:3]*alpha[...,None] + bg*(1-alpha[...,None])
yy,xx = np.mgrid[0:H,0:W]; chk = np.where(((yy//40)+(xx//40))%2==0, 0.8, 0.55)[...,None]*np.ones(3)
tiles = [over(np.array([0.106,0.133,0.2])), over(np.array([0.36,0.58,0.30])), over(chk), over(np.array([0.95,0.85,0.70]))]
tiles = [t[::2,::2] for t in tiles]
grid = np.ones((h2*2, w2*2, 4), np.float32)
grid[:h2,:w2,:3]=tiles[2][:h2,:w2]; grid[:h2,w2:,:3]=tiles[0][:h2,:w2]; grid[h2:,:w2,:3]=tiles[1][:h2,:w2]; grid[h2:,w2:,:3]=tiles[3][:h2,:w2]
p = bpy.data.images.new('p',w2*2,h2*2); p.pixels.foreach_set(grid.ravel()); p.filepath_raw=PRE; p.file_format='PNG'; p.save()
