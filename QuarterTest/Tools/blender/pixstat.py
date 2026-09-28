# -*- coding: utf-8 -*-
"""PNG の明るさ分布を測る。白飛びしているかを数値で見る。"""
import bpy, sys
argv = sys.argv[sys.argv.index("--")+1:]
for path in argv:
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    n = len(px)//4
    over = 0; near = 0; tot = 0.0
    for i in range(0, n*4, 4):
        r,g,b = px[i], px[i+1], px[i+2]
        m = max(r,g,b)
        tot += m
        if m >= 0.999: over += 1
        elif m >= 0.95: near += 1
    print("STAT %-28s 画素%d  真っ白%.1f%%  ほぼ白%.1f%%  平均の明るさ%.3f"
          % (path.split("\\")[-1].split("/")[-1], n, 100*over/n, 100*near/n, tot/n))
    bpy.data.images.remove(img)
