# -*- coding: utf-8 -*-
"""開いたときにカメラ視点・テクスチャ表示になるよう .blend を整える。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
n = 0
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type != 'VIEW_3D': continue
        for space in area.spaces:
            if space.type != 'VIEW_3D': continue
            space.shading.type = 'MATERIAL'          # テクスチャが見える表示
            r3d = getattr(space, "region_3d", None)
            if r3d is not None:
                r3d.view_perspective = 'CAMERA'
                n += 1
            for q in getattr(space, "region_quadviews", []):
                q.view_perspective = 'CAMERA'
print("VIEWS", n)
bpy.ops.wm.save_as_mainfile(filepath=a[0])
print("SAVED", a[0])
