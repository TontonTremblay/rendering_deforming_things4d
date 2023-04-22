# Rendering [Deforming Things 4D](https://github.com/rabbityl/DeformingThings4D) in Blender

This repo generates meta data, such as flow, depth and rgb for animations taken from [deforming things 4D](https://github.com/rabbityl/DeformingThings4D). You need to download blender first and make sure you know where its path is. At the root of this repo you can call `python src/render_john_mac.py`. The code is driven by two things, the path to blender which you can pass as an argument and a config file, which you can also pass as argument. 

In the config file make sure you put absolute paths. Otherwise the code wont work. Check the `configs/abe_CoverToStand.yaml`. The script will output everything into your `output_path`. There are couple things to look forward to, the script outputs the blend scene as `scene.blend` you can check for errors or for a prefered camera pose there. Check the pose and change it in the yaml file. The script also outputs the bones position in the camera space, check the file `pose_bones.json`. 


# TODO
- Add soft body simulation to the animation (https://www.youtube.com/watch?v=mc4so2VyyPE)
- Add non-square images resolution
- Add an image of the rendering / animation this produces. 