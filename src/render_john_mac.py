import os
import argparse
import sys

with open("path.txt", "w") as file:
    file.write(str(sys.path))

parser = argparse.ArgumentParser(description='Renders glbs')
parser.add_argument(
    '--blender_root', 
    type=str, 
    default='/Applications/Blender_34.app/Contents/MacOS/Blender',
    help='path to blender executable'
)
parser.add_argument(
    '--config', 
    type=str, 
    default='configs/abe_CoverToStand.yaml',
    help='path to config'
)
    
opt = parser.parse_args()

# add full path to config
opt.config = os.path.abspath(opt.config)


render_cmd = f'{opt.blender_root} -b -P "src/render_animation.py" -- --config {opt.config}'
# render_cmd = render_cmd + ' > tmp.out'

print(render_cmd)
os.system(render_cmd)


