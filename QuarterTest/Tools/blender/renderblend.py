import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
sc = bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'
sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.render.resolution_x=1500; sc.render.resolution_y=560
sc.render.filepath=a[1]; sc.render.image_settings.file_format='PNG'
bpy.ops.render.render(write_still=True)
print("RENDERED", a[1])
