import sys,pdb,cv2,imageio,shutil,subprocess
with open("/tmp/path.txt") as file:
    paths = eval(file.read())
for p in paths:
    sys.path.insert(0,p)
import argparse, sys, os, math, re
import bpy
from mathutils import Vector, Matrix
import mathutils
import numpy as np
import json
import random
import glob
import threading


# global variable
DATA_EXPORT = {}
rgb_node = None
depth_file_output = None
flow_file_output = None

def make_obj_emissive(obj, color):
    new_mat = bpy.data.materials.new(name="seg")
    new_mat.use_nodes = True
    new_mat.cycles.sample_as_light = False
    emission_node = new_mat.node_tree.nodes.new(type='ShaderNodeEmission')
    output = new_mat.node_tree.nodes.get("Material Output")

    emission_node.inputs['Color'].default_value[:3] = color
    new_mat.node_tree.links.new(emission_node.outputs['Emission'], output.inputs['Surface'])

    if len(obj.material_slots) > 0:
        for imat,mat in enumerate(obj.material_slots):
                obj.data.materials[imat] = new_mat
    else:
        obj.data.materials.append(new_mat)



def add_light_under(obj,dist = 0.01,power=5):
    light_data = bpy.data.lights.new(name=obj.name+"_light", type='POINT')
    light_data.energy = power
    light_object = bpy.data.objects.new(name=obj.name+"_light", object_data=light_data)
    light_object.location = (0, 0, -dist)
    bpy.context.collection.objects.link(light_object)
    light_object.parent = obj
    # raise()


def make_segmentation_scene(scene_name='segmentation', path='/tmp'):
    global DATA_EXPORT, depth_file_output, flow_file_output, rgb_node
    os.makedirs(path, exist_ok=True)

    bpy.ops.scene.new(type='FULL_COPY')
    bpy.context.scene.name = scene_name


    bpy.context.scene.cycles.samples =1
    bpy.context.view_layer.cycles.use_denoising = False
    bpy.context.scene.render.use_motion_blur = False
    bpy.context.view_layer.use_pass_vector = True
    bpy.context.scene.render.image_settings.file_format="OPEN_EXR"
    bpy.context.scene.render.image_settings.compression=0
    bpy.context.scene.render.image_settings.color_mode="RGB"
    bpy.context.scene.render.image_settings.color_depth="32"
    bpy.context.scene.render.image_settings.exr_codec="NONE"
    bpy.context.scene.render.image_settings.use_zbuffer=True
    bpy.context.view_layer.use_pass_z=True

    # lets update all the materials of the objects to emmissive
    to_change = []
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH':
            to_change.append(ob)

    import colorsys

    for ob in to_change:
        while True:
            c = colorsys.hsv_to_rgb(
                random.uniform(0,255)/255,
                random.uniform(200,255)/255,
                random.uniform(200,255)/255
                )
            found = False
            for obj in DATA_EXPORT:
                if 'color_seg' in DATA_EXPORT[obj] and c == DATA_EXPORT[obj]['color_seg']:
                    found = True
            if found is True:
                continue
            if ob.name.split(".")[0] in DATA_EXPORT:
                DATA_EXPORT[ob.name.split(".")[0]]['color_seg'] = c
            break
        make_obj_emissive(ob,c)

    nodes = bpy.context.scene.world.node_tree.nodes
    links = bpy.context.scene.world.node_tree.links

    c = colorsys.hsv_to_rgb(
        random.uniform(0,255)/255,
        random.uniform(200,255)/255,
        random.uniform(200,255)/255
        )
    c = [c[0],c[1],c[2],1]
    if len(nodes.get("Background").inputs['Color'].links) > 0:
        links.remove(nodes.get("Background").inputs['Color'].links[0])

    nodes.get("Background").inputs['Strength'].default_value = 1
    nodes.get("Background").inputs['Color'].default_value = c

    # make the depth layer:
    bpy.context.scene.use_nodes = True
    tree = bpy.context.scene.node_tree
    links = tree.links

    for n in tree.nodes:
        tree.nodes.remove(n)

    # Create input render layer node.
    render_layers = tree.nodes.new('CompositorNodeRLayers')

    depth_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
    depth_file_output.label = 'Depth Output'
    links.new(render_layers.outputs['Depth'], depth_file_output.inputs[0])
    depth_file_output.format.file_format = "OPEN_EXR"
    depth_file_output.base_path = path
    depth_file_output.file_slots[0].path = f'depth'

    # flow - helped from blenderproc, thank you
    separate_rgba = tree.nodes.new('CompositorNodeSepRGBA')
    links.new(render_layers.outputs['Vector'], separate_rgba.inputs['Image'])

    combine_fwd_flow = tree.nodes.new('CompositorNodeCombRGBA')
    links.new(separate_rgba.outputs['B'], combine_fwd_flow.inputs['R'])
    links.new(separate_rgba.outputs['A'], combine_fwd_flow.inputs['G'])

    flow_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
    flow_file_output.label = 'Flow Output'
    links.new(combine_fwd_flow.outputs['Image'], flow_file_output.inputs[0])
    flow_file_output.format.file_format = "OPEN_EXR"
    flow_file_output.base_path = path
    flow_file_output.file_slots[0].path = f'flow'

    seg_node = tree.nodes.new('CompositorNodeOutputFile')   # seg
    seg_node.format.file_format = 'OPEN_EXR'
    seg_node.file_slots[0].path = f'seg'
    links.new(render_layers.outputs['IndexOB'], seg_node.inputs[0])

    # rgb_node = tree.nodes.new('CompositorNodeOutputFile')   # rgb
    # rgb_node.format.file_format = 'PNG'
    # rgb_node.base_path = path
    # rgb_node.file_slots[0].path = f'rgb'
    # links.new(render_layers.outputs['Image'], rgb_node.inputs[0])

    # rgb_node = tree.nodes.new('CompositorNodeViewer')
    # rgb_node.use_alpha = False
    # links.new(render_layers.outputs['Image'], rgb_node.inputs[0])

    node_viewer = tree.nodes.new('CompositorNodeViewer')
    node_viewer.use_alpha = False
    links.new(render_layers.outputs['Image'], node_viewer.inputs[0])


    # set it back to normal scene
    bpy.context.window.scene = bpy.data.scenes['Scene']

# Function taken from https://github.com/zhenpeiyang/HM3D-ABO/blob/master/my_blender.py
def get_3x4_RT_matrix_from_blender(cam):
    # bcam stands for blender camera
    # R_bcam2cv = Matrix(
    #     ((1, 0,  0),
    #     (0, 1, 0),
    #     (0, 0, 1)))

    # Transpose since the rotation is object rotation,
    # and we want coordinate rotation
    # R_world2bcam = cam.rotation_euler.to_matrix().transposed()
    # T_world2bcam = -1*R_world2bcam @ location
    #
    # Use matrix_world instead to account for all constraints
    location, rotation = cam.matrix_world.decompose()[0:2]
    R_world2bcam = rotation.to_matrix().transposed()

    # Convert camera location to translation vector used in coordinate changes
    # T_world2bcam = -1*R_world2bcam @ cam.location
    # Use location from matrix_world to account for constraints:
    T_world2bcam = -1*R_world2bcam @ location

    # # Build the coordinate transform matrix from world to computer vision camera
    # R_world2cv = R_bcam2cv@R_world2bcam
    # T_world2cv = R_bcam2cv@T_world2bcam

    # put into 3x4 matrix
    RT = mathutils.Matrix((
        R_world2bcam[0][:] + (T_world2bcam[0],),
        R_world2bcam[1][:] + (T_world2bcam[1],),
        R_world2bcam[2][:] + (T_world2bcam[2],)
        ))
    return RT

def get_sensor_size(sensor_fit, sensor_x, sensor_y):
    if sensor_fit == 'VERTICAL':
        return sensor_y
    return sensor_x

# BKE_camera_sensor_fit
def get_sensor_fit(sensor_fit, size_x, size_y):
    if sensor_fit == 'AUTO':
        if size_x >= size_y:
            return 'HORIZONTAL'
        else:
            return 'VERTICAL'
    return sensor_fit

# Build intrinsic camera parameters from Blender camera data
#
# See notes on this in
# blender.stackexchange.com/questions/15102/what-is-blenders-camera-projection-matrix-model
# as well as
# https://blender.stackexchange.com/a/120063/3581
def get_calibration_matrix_K_from_blender(camd):
    if camd.type != 'PERSP':
        raise ValueError('Non-perspective cameras not supported')
    scene = bpy.context.scene
    f_in_mm = camd.lens
    scale = scene.render.resolution_percentage / 100
    resolution_x_in_px = scale * scene.render.resolution_x
    resolution_y_in_px = scale * scene.render.resolution_y
    sensor_size_in_mm = get_sensor_size(camd.sensor_fit, camd.sensor_width, camd.sensor_height)
    sensor_fit = get_sensor_fit(
        camd.sensor_fit,
        scene.render.pixel_aspect_x * resolution_x_in_px,
        scene.render.pixel_aspect_y * resolution_y_in_px
    )
    pixel_aspect_ratio = scene.render.pixel_aspect_y / scene.render.pixel_aspect_x
    if sensor_fit == 'HORIZONTAL':
        view_fac_in_px = resolution_x_in_px
    else:
        view_fac_in_px = pixel_aspect_ratio * resolution_y_in_px
    pixel_size_mm_per_px = sensor_size_in_mm / f_in_mm / view_fac_in_px
    s_u = 1 / pixel_size_mm_per_px
    s_v = 1 / pixel_size_mm_per_px / pixel_aspect_ratio

    # Parameters of intrinsic calibration matrix K
    u_0 = resolution_x_in_px / 2 - camd.shift_x * view_fac_in_px
    v_0 = resolution_y_in_px / 2 + camd.shift_y * view_fac_in_px / pixel_aspect_ratio
    skew = 0 # only use rectangular pixels

    K = Matrix(
        ((s_u, skew, u_0),
        (   0,  s_v, v_0),
        (   0,    0,   1)))

    return K


# function taken from https://blender.stackexchange.com/questions/5210/pointing-the-camera-in-a-particular-direction-programmatically
def look_at(obj, target, roll=0):
    """
    Rotate obj to look at target

    :arg obj: the object to be rotated. Usually the camera
    :arg target: the location (3-tuple or Vector) to be looked at
    :arg roll: The angle of rotation about the axis from obj to target in radians.

    Based on: https://blender.stackexchange.com/a/5220/12947 (ideasman42)
    """
    if not isinstance(target, mathutils.Vector):
        target = mathutils.Vector(target)
    loc = obj.location
    # direction points from the object to the target
    direction = target - loc
    tracker, rotator = (('-Z', 'Y'),'Z') if obj.type=='CAMERA' else (('X', 'Z'),'Y') #because new cameras points down(-Z), usually meshes point (-Y)
    quat = direction.to_track_quat(*tracker)

    # /usr/share/blender/scripts/addons/add_advanced_objects_menu/arrange_on_curve.py
    quat = quat.to_matrix().to_4x4()
    rollMatrix = mathutils.Matrix.Rotation(roll, 4, rotator)

    # remember the current location, since assigning to obj.matrix_world changes it
    loc = loc.to_tuple()
    #obj.matrix_world = quat * rollMatrix
    # in blender 2.8 and above @ is used to multiply matrices
    # using * still works but results in unexpected behaviour!
    obj.matrix_world = quat @ rollMatrix
    obj.location = loc


def export_meta_data_2_json(
    filename = "tmp.json", #this has to include path as well
    height = 500,
    width = 500,
    camera_ob = None,
    camera_struct = None,
    data = None,
    segmentation_mask = None,
    scene_aabb = [],
    path = "",
    i_pos = 0
    ):
    global DATA_EXPORT
    data = DATA_EXPORT

    # import simplejson as json
    import json
    # cam_world_quaternion = visii.quat_cast(cam_matrix)

    cam_intrinsics = get_calibration_matrix_K_from_blender(camera_ob.data)

    if camera_struct is None:
        camera_struct = {
            'at': [0,0,0,],
            'eye': [0,0,0,],
            'up': [0,0,0,]
        }


    rt = get_3x4_RT_matrix_from_blender(camera_ob)
    pos, rt, scale = camera_ob.matrix_world.decompose()
    rt = rt.to_matrix()
    cam2wold = []
    for i in range(3):
        a = []
        for j in range(3):
            a.append(rt[i][j])
        a.append(pos[i])
        cam2wold.append(a)
    cam2wold.append([0,0,0,1])

    cam_world_location = camera_ob.location

    cam_world_quaternion = camera_ob.rotation_euler.to_quaternion()

    dict_out = {
                "camera_data" : {
                    "width" : width,
                    'height' : height,
                    'camera_look_at':
                    {
                        'at': [
                            camera_struct['at'][0],
                            camera_struct['at'][1],
                            camera_struct['at'][2],
                        ],
                        'eye': [
                            camera_struct['eye'][0],
                            camera_struct['eye'][1],
                            camera_struct['eye'][2],
                        ],
                        'up': [
                            camera_struct['up'][0],
                            camera_struct['up'][1],
                            camera_struct['up'][2],
                        ]
                    },
                    'cam2world':cam2wold,
                    'location_world':
                    [
                        cam_world_location[0],
                        cam_world_location[1],
                        cam_world_location[2],
                    ],
                    'intrinsics':{
                        'fx':float(cam_intrinsics[0][0]),
                        'fy':float(cam_intrinsics[1][1]),
                        'cx':float(cam_intrinsics[0][2]),
                        'cy':float(cam_intrinsics[1][2])
                    },
                    # 'scene_min_3d_box':scene_aabb[0],
                    # 'scene_max_3d_box':scene_aabb[1],
                    # 'scene_center_3d_box':scene_aabb[2],
                },
                "objects" : []
            }

    # load the segmentation & find unique pixels

    # if not segmentation_mask is None or os.path.exists(f'{path}/{str(i_pos).zfill(3)}_seg.exr'):
    #     segmentation_mask = bpy.data.images.load(f'{path}/{str(i_pos).zfill(3)}_seg.exr')
    #     segmentation_mask = np.asarray(segmentation_mask.pixels)
    #     segmentation_mask = segmentation_mask.reshape((width,height,4))[:,:,:3]
    #     unique_pixels = np.vstack({tuple(r) for r in segmentation_mask.reshape(-1,3)})
    #     unique_pixels = (unique_pixels*255).astype(int)


    # Segmentation id to export
    import bpy_extras
    scene = bpy.context.scene
    for obj_name in data.keys():
        projected_keypoints = []

        obj = bpy.context.scene.objects[obj_name]

        if not data[obj_name]['cuboid'] is None:
            for keypoint in bpy.context.scene.objects[obj_name].children:
                if not keypoint.type == "EMPTY":
                    continue

                co_2d = bpy_extras.object_utils.world_to_camera_view(
                    bpy.context.scene,
                    camera_ob,
                    keypoint.matrix_world.translation
                )

                # If you want pixel coords
                render_scale = scene.render.resolution_percentage / 100
                render_size = (int(scene.render.resolution_x * render_scale),
                               int(scene.render.resolution_y * render_scale),
                            )
                projected_keypoints.append([co_2d.x * render_size[0],height - co_2d.y * render_size[1]])

            cuboid = data[obj_name]['cuboid']
        else:
            cuboid = None
            projected_keypoints = [[-1,-1]]
        #check if the object is visible
        visibility = -1
        bounding_box = [-1,-1,-1,-1]


        # Using the bouding box keypoints wont give tight 2d bounding box
        # use the segmentation mask instead.
        a = np.array(projected_keypoints)
        minx = min(a[:,0])
        miny = min(a[:,1])
        maxx = max(a[:,0])
        maxy = max(a[:,1])

        # Not working
        # if (minx>0 and minx<width and miny>0 and miny<height ) or\
        #    (maxx>0 and maxx<width and maxy>0 and maxy<height ) or\
        #    (minx>0 and minx<width and maxy>0 and maxy<height ) or\
        #    (maxx>0 and maxx<width and miny>0 and miny<height ):
        #    visibility = 1
        # else:
        #     visibility = 0
        # if not cuboid is None:
        #     color_int = (np.array(data[obj_name]['color_seg'])*255).astype(int)
        #     if not segmentation_mask is None:

        #         if color_int in unique_pixels:
        #             visibility = 1
        #         else:
        #             visibility = 0

        pos, rt, scale = obj.matrix_world.decompose()
        rt = rt.to_matrix()
        trans_matrix_export = []
        for i in range(3):
            a = []
            for j in range(3):
                a.append(rt[i][j])
            a.append(pos[i])
            trans_matrix_export.append(a)
        trans_matrix_export.append([0,0,0,1])

        rt = camera_ob.matrix_world.inverted() @ obj.matrix_world

        trans_matrix_cam_export = []
        for i in range(3):
            a = []
            for j in range(3):
                a.append(rt[i][j])
            a.append(pos[i])
            trans_matrix_cam_export.append(a)
        trans_matrix_cam_export.append([0,0,0,1])


        # Final export
        dict_out['objects'].append({
            # 'class':obj_name.split('_')[1],
            'name':obj.name,
            'provenance':'blender_john',
            # TODO check the location
            'location_world': [
                obj.location[0],
                obj.location[1],
                obj.location[2]
            ],
            'local_to_world_matrix':trans_matrix_export,
            'trans_in_camera':trans_matrix_cam_export,
            'projected_cuboid':projected_keypoints,
            'local_cuboid': cuboid,
            'bounding_box_minx_maxx_miny_maxy':[minx,maxx,miny,maxy],
        })
        # dict_out['objects'][-1]['segmentation_id']=data[obj_name]["color_seg"]
        for key in data[obj_name].keys():
            if not key in dict_out['objects'][-1]:
                dict_out['objects'][-1][key] = data[obj_name][key]
    print(dict_out)
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                a = obj.tolist()
                for i in range(len(a)):
                    a[i] = float(a[i])
                return a
            return json.JSONEncoder.default(self, obj)
    with open(filename, 'w+') as fp:
        json.dump(dict_out, fp, indent=4, sort_keys=True,cls=NumpyEncoder)
    # return bounding_box

def render_single_image(
    frame_set=0, # which scene frame
    look_at_data = None, # data with 'at','eye','up'
    path = 'tmp',
    save_segmentation = True,
    save_depth = True,
    resolution = 500,
    ):
    global DATA_EXPORT, depth_file_output,flow_file_output
    i_pos = frame_set

    bpy.context.window.scene = bpy.data.scenes['segmentation']
    bpy.context.scene.frame_set(frame_set)

    obj_camera = bpy.context.scene.objects['Camera.001']

    if not look_at_data is None:
        obj_camera.location = (
            (look_at_data['eye'][0]),
            (look_at_data['eye'][1]),
            (look_at_data['eye'][2])
            )
        bpy.context.view_layer.update()
        look_at(obj_camera,look_at_data['at'])

        bpy.context.view_layer.update()

    # depth_file_output.file_slots[0].path = f'{path}/{str(i_pos).zfill(3)}_depth'
    # flow_file_output.file_slots[0].path = f'{path}/{str(i_pos).zfill(3)}_flow'
    bpy.context.scene.render.filepath = f'{path}/seg.exr'


    # tree = bpy.context.scene.node_tree
    # depth_file_output.base_path = path
    # flow_file_output.base_path = path
    # rgb_node.base_path = path
    # depth_file_output.file_slots[0].path = f'depth'
    # flow_file_output.file_slots[0].path = f'flow'
    # rgb_node.file_slots[0].path = f'{str(i_pos).zfill(3)}_rgb'
    # bpy.context.scene.render.filepath = f'{path}/{str(i_pos).zfill(3)}_seg.exr'

    bpy.ops.render.render(write_still = True)


    bpy.context.window.scene = bpy.data.scenes['Scene']
    bpy.context.scene.frame_set(frame_set)

    if not look_at_data is None:
        obj_camera = bpy.context.scene.objects['Camera']
        obj_camera.location = (
            (look_at_data['eye'][0]),
            (look_at_data['eye'][1]),
            (look_at_data['eye'][2])
            )
        bpy.context.view_layer.update()

        look_at(obj_camera,look_at_data['at'])

        bpy.context.view_layer.update()

    # change the scene


    export_meta_data_2_json(
        f"{path}/{str(i_pos).zfill(3)}.json",
        width = resolution,
        height = resolution,
        camera_ob = obj_camera,
        data = DATA_EXPORT,
        camera_struct = look_at_data,
        segmentation_mask = f'{path}/{str(i_pos).zfill(3)}_seg.png',
        scene_aabb = [],
        path = path,
        i_pos = i_pos,
    )

    # if no depth or no segmentation to be saved.
    if not save_segmentation:
        os.remove(f'{path}/{str(i_pos).zfill(3)}_seg.exr')
        # threading.Thread(os.remove, f'{path}/{str(i_pos).zfill(3)}_seg.exr').start()
    if not save_depth:
        os.remove(f'{path}/{str(i_pos).zfill(3)}_depth.exr')
        # threading.Thread(os.remove, f'{path}/{str(i_pos).zfill(3)}_depth.exr').start()


    rt = get_3x4_RT_matrix_from_blender(obj_camera)
    pos, rt, scale = obj_camera.matrix_world.decompose()
    rt = rt.to_matrix()
    matrix = []
    for i in range(3):
        a = []
        for j in range(3):
            a.append(rt[i][j])
        a.append(pos[i])
        matrix.append(a)
    matrix.append([0,0,0,1])
    # print(matrix)

    # print(obj_camera.matrix_world.decompose())
    # raise()
    # matrix[0][-1]=obj_camera.location[0]
    # matrix[1][-1]=obj_camera.location[1]
    # matrix[2][-1]=obj_camera.location[2]
    # print(matrix)

    to_add = {\
        "file_path":f'{str(i_pos).zfill(3)}.png',
        "transform_matrix":matrix
    }

    bpy.context.scene.render.filepath = f'{path}/rgb.png'
    bpy.ops.render.render(write_still = True)

    # pdb.set_trace()

    file = glob.glob(f'{path}/*rgb*png')[0]
    color = cv2.imread(file)[...,:3]
    cv2.imwrite(f'{path}/rgb/{i_pos:03d}.png', color.astype(np.uint8))

    seg_file = glob.glob(f'{path}/*seg*.exr')[0]
    seg = cv2.imread(seg_file, -1)[...,0]
    cv2.imwrite(f'{path}/seg/{i_pos:03d}.png', (seg>0).astype(np.uint8)*255)

    depth_file = glob.glob(f'{path}/*depth*.exr')[0]
    depth = cv2.imread(depth_file, -1)[...,0]
    cv2.imwrite(f'{path}/depth/{i_pos:03d}.png', (depth*1000).astype(np.uint16))

    flow_file = glob.glob(f'{path}/*flow*.exr')[0]
    flow = cv2.imread(flow_file, -1)[...,::-1][...,:2]
    flow[...,1] *= -1
    np.save(f'{path}/flow/{i_pos:03d}.npy', flow.astype(np.float32))

    os.system(f'rm -rf {path}/*depth*.exr {path}/*flow*.exr {path}/*seg*.exr {path}/*rgb*.png')
