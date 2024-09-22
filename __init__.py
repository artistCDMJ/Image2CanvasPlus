# GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Image2CanvasPlus",
    "author": "CDMJ",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Image Editor > Image Tab > Image2CanvasPlus",
    "description": "Create Image Plane and Matching Camera from Generated Image",
    "warning": "",
    "category": "Paint",
}

import bpy

### reused functions from D2P
def create_image_plane_from_image(active_image, scale_factor=0.01):
    width = active_image.size[0]
    height = active_image.size[1]

    name = active_image.name + "_canvas"
    print(f"Active image dimensions: {width} x {height}")

    mesh = bpy.data.meshes.new(name=name + "Mesh")
    obj = bpy.data.objects.new(name=name, object_data=mesh)

    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.primitive_plane_add(size=1)
    bpy.ops.transform.resize(value=(width * scale_factor / 5, height * scale_factor / 5, 1))
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Create material and node setup with Emission and Principled BSDF
    mat = bpy.data.materials.new(name=name + "Material")
    mat.use_nodes = True
    
    # Get nodes
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.location = (-212.01303100585938, 704.966796875)
    tex_image = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_image.location = (-617.7554931640625, 626.1090087890625)
    tex_image.image = active_image
    
    # Add Emission shader node
    emission = mat.node_tree.nodes.new('ShaderNodeEmission')
    emission.location = (-172.02610778808594, 348.537109375)
    
    
    # Add Mix Shader node
    mix_shader = mat.node_tree.nodes.new('ShaderNodeMixShader')
    mix_shader.location = (250.89752197265625, 651.1596069335938)
    
    # Connect Image texture to both shaders (BSDF and Emission)
    mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])
    mat.node_tree.links.new(emission.inputs['Color'], tex_image.outputs['Color'])
    
    # Connect both shaders to the Mix Shader
    mat.node_tree.links.new(mix_shader.inputs[1], bsdf.outputs['BSDF'])
    mat.node_tree.links.new(mix_shader.inputs[2], emission.outputs['Emission'])
    
    # Optionally add a Value node to control the mix factor
    mix_factor = mat.node_tree.nodes.new('ShaderNodeValue')
    mix_factor.location = (243.66448974609375, 506.4412841796875)
    mix_factor.outputs[0].default_value = 0.5  # Default to 50% mix
    mat.node_tree.links.new(mix_shader.inputs[0], mix_factor.outputs[0])
    
    # Connect Mix Shader to Material Output
    material_output = mat.node_tree.nodes['Material Output']
    material_output.location = (453.1165466308594, 643.1837768554688)
    mat.node_tree.links.new(material_output.inputs['Surface'], mix_shader.outputs['Shader'])
    
    # Apply the material to the object
    obj.data.materials.append(mat)

    # Rename the UV map
    uv_layer = obj.data.uv_layers.active
    uv_layer.name = name + "_uvmap"

    # Update the view layer to ensure transformations are applied
    bpy.context.view_layer.update()

    return obj, width * scale_factor, height * scale_factor

def create_matching_camera(image_plane_obj, width, height, distance=1):
    im_name = image_plane_obj.name + "_camera_view"
    cam_data = bpy.data.cameras.new(name=im_name)
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(width, height) / 5

    cam_obj = bpy.data.objects.new(name=im_name, object_data=cam_data)

    bpy.context.collection.objects.link(cam_obj)

    cam_obj.location = (0, 0, distance)
    cam_obj.rotation_euler = (0, 0, 0)

    scene = bpy.context.scene
    scene.render.resolution_x = int(width / 0.01)  # Converting back to original resolution
    scene.render.resolution_y = int(height / 0.01)  # Converting back to original resolution

    # Set the camera as the main (active) camera
    bpy.context.scene.camera = cam_obj

    return cam_obj



def switch_to_camera_view(camera_obj):
    # Set the camera as the active camera for the scene
    bpy.context.scene.camera = camera_obj

    # Iterate over all the areas in the current screen to find the VIEW_3D areas
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            # Override the context for each 3D view area
            with bpy.context.temp_override(area=area):
                space = area.spaces.active
                space.region_3d.view_perspective = 'CAMERA'


def move_object_to_collection(obj, collection_name):
    # Get the collection or create it if it doesn't exist
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    # Unlink the object from all its current collections
    for coll in obj.users_collection:
        coll.objects.unlink(obj)

    # Link the object to the new collection
    collection.objects.link(obj)


### reused operator from Draw2Paint with modification
class D2P_OT_Image2CanvasPlus(bpy.types.Operator):
    """Create Canvas and Camera from Active Image In Image Editor"""
    bl_description = "Create Canvas and Camera from Active Image In Image Editor"
    bl_idname = "image.canvas_and_camera"
    bl_label = "Generate Image Plane and Matching Camera from Image Editor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_image = None
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                active_image = area.spaces.active.image
                break

        if not active_image:
            self.report({'WARNING'}, "No active image found.")
            return {'CANCELLED'}
        
        # Switch to 3D view
        bpy.context.area.ui_type = 'VIEW_3D'
        
        # Create image plane and matching camera
        image_plane_obj, width, height = create_image_plane_from_image(active_image)
        if not image_plane_obj:
            self.report({'WARNING'}, "Failed to create image plane.")
            return {'CANCELLED'}
        
        camera_obj = create_matching_camera(image_plane_obj, width, height)
        bpy.context.view_layer.objects.active = camera_obj
                
        camera_obj.data.show_name = True
        
        # Ensure the correct context is active before applying view settings
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(area=area):
                    area.spaces.active.shading.type = 'SOLID'
                    area.spaces.active.shading.light = 'FLAT'
                    area.spaces.active.shading.color_type = 'TEXTURE'
        
                
        # Move camera and image plane to 'canvas_view' collection
        move_object_to_collection(image_plane_obj, 'canvas_view')
        move_object_to_collection(camera_obj, 'canvas_view')
        
        # Switch to camera view (inside the 3D View context)
        switch_to_camera_view(camera_obj)
        
        # Switch back to Image Editor
        bpy.context.area.ui_type = 'IMAGE_EDITOR'

        return {'FINISHED'}

### reused UI from D2P
############################### IMAGE EDITOR PANEL OPTION
class D2P_PT_Image2CanvasPlus(bpy.types.Panel):
    bl_label = "Image2Canvas+"
    bl_idname = "D2P_PT_image_plane_panel"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Image'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("image.canvas_and_camera", text="Create Canvas and Camera")
        
def register():
    bpy.utils.register_class(D2P_OT_Image2CanvasPlus)
    bpy.utils.register_class(D2P_PT_Image2CanvasPlus)

def unregister():
    bpy.utils.unregister_class(D2P_OT_Image2CanvasPlus)
    bpy.utils.unregister_class(D2P_PT_Image2CanvasPlus)

if __name__ == "__main__":
    register()
