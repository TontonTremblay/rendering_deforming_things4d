import os,subprocess
import argparse
import sys

with open("/tmp/path.txt", "w") as file:
    file.write(str(sys.path))

code_dir = os.path.dirname(os.path.realpath(__file__))
parser = argparse.ArgumentParser(description='Renders glbs')
parser.add_argument(
    '--blender_root',
    type=str,
    default='/mnt/9a72c439-d0a7-45e8-8d20-d7a235d02763/blender-2.93.9-linux-x64/blender',
    help='path to blender executable'
)
parser.add_argument(
    '--config',
    type=str,
    default=f'{code_dir}/../configs/AJ_SoccerPass.yaml',
    help='path to config'
)

opt = parser.parse_args()

# add full path to config
opt.config = os.path.abspath(opt.config)

code_dir = os.path.dirname(os.path.realpath(__file__))
render_cmd = f'{opt.blender_root} -b -P "{code_dir}/render_animation.py" -- --config {opt.config}'
# render_cmd = render_cmd + ' > tmp.out'

print(render_cmd)
subprocess.call(render_cmd, shell=True)


