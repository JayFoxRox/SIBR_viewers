#
# Convert RealityCapture export to colmap
#

""" @package dataset_tools_preprocess
This script runs a pipeline to create Colmap reconstruction data from RealityCApture output

Parameters: -h help,

Usage: python rc_to_colmap.py  (see help)
"""

import bundle
import os, sys, shutil
import json
import argparse
import scipy
import numpy as np
from scipy.spatial.transform import Rotation as R


from utils.paths import getBinariesPath, getColmapPath, getMeshlabPath
from utils.commands import  getProcess, getColmap

def main():
    parser = argparse.ArgumentParser()
    # common arguments
    parser.add_argument("--rc_path", type=str, required=True, help="path to rc dataset, containing bundle.out and images")
    parser.add_argument("--out_path", type=str, required=True, help = "output path ")
    parser.add_argument("--create_colmap", action='store_true', help="create colmap hierarchy")


    args = vars(parser.parse_args())

    input_bundle = bundle.Bundle(os.path.join(args["rc_path"] , "bundle.out"))
    input_bundle.generate_list_of_images_file (os.path.join(args["rc_path"] , "list_images.txt"))

    dst_image_path = os.path.join(args["out_path"], "images")

    # create entire colmap structure
    #
    if args["create_colmap"]:
        dir_name = os.path.join(args["out_path"], "stereo")
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        dst_image_path = os.path.join(dir_name, "images")

        sparse_stereo_dir = dir_name = os.path.join(dir_name, "sparse")
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    else:
        sparse_stereo_dir = args["out_path"]

    if not os.path.exists(dst_image_path):
        os.makedirs(dst_image_path)

    # create cameras.txt
    #

    fname = os.path.join(sparse_stereo_dir, "cameras.txt")
    print("Creating ", fname)
    numcams = len(input_bundle.list_of_input_images)

    camera_id = 1
    with open(fname, 'w') as outfile:
        outfile.write("# Camera list with one line of data per camera:\n")
        outfile.write("#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        outfile.write("# Number of cameras: {}\n".format(numcams))
        for im in input_bundle.list_of_input_images:
           width = im.resolution[0]
           height = im.resolution[1]
           focal_length = input_bundle.list_of_cameras[camera_id-1].focal_length
           outfile.write("{} PINHOLE {} {} {} {} {} {}\n".format(camera_id, width, height, focal_length, focal_length, width/2.0, height/2.0))
           camera_id = camera_id + 1
        outfile.close()

    #
    # create images.txt
    #
    fname = os.path.join(sparse_stereo_dir, "images.txt")

    print("Creating ", fname)
    camera_id = 1
    with open(fname, 'w') as outfile:
      outfile.write( "# Image list with two lines of data per image:\n" )
      outfile.write( "#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n" )
      outfile.write( "#   POINTS2D[] as (X, Y, POINT3D_ID)\n" )
      for cam in input_bundle.list_of_cameras:
         name = os.path.basename(input_bundle.list_of_input_images[camera_id-1].path)
         # to sibr internal
         
         br = np.matrix(cam.rotation).transpose()
         t = -np.matmul(br , np.matrix([cam.translation[0], cam.translation[1], cam.translation[2]]).transpose())
         
         # sibr save to colmap
         br = np.matmul(br, np.matrix([[1, 0, 0], [0, -1, 0], [0, 0, -1]]))
         br = br.transpose()

         sci_rot = R.from_matrix(br)
         sci_quat = sci_rot.as_quat()

         t = -np.matmul(br, t)

         outfile.write("{} {} {} {} {} {} {} {} {} {}\n\n".format(camera_id, -sci_quat[3], -sci_quat[0], -sci_quat[1], -sci_quat[2], t[0,0], t[1,0], t[2,0], camera_id, name))
         camera_id = camera_id + 1
      outfile.close()

#
# create points3D.txt
#
    # copy images
    for fname in os.listdir(args["rc_path"]):
        if fname.endswith(".jpg") or fname.endswith(".JPG") or fname.endswith(".png") or fname.endswith(".PNG") :
            print("Copying ", os.path.join(args["rc_path"], fname), "to ", os.path.join(dst_image_path, os.path.basename(fname)))
            shutil.copyfile(os.path.join(args["rc_path"], fname), os.path.join(dst_image_path, os.path.basename(fname)))

    # copy mesh; fake it
    if args["create_colmap"]:
        # assume meshes above
        rc_mesh_dir = os.path.join(os.path.abspath(os.path.join(args["rc_path"], os.pardir)), "meshes")
        out_mesh_dir = os.path.join(os.path.abspath(os.path.join(args["out_path"], os.pardir)), "capreal")
        print("RC mesh dir: ", rc_mesh_dir)
        print("Out mesh dir: ", out_mesh_dir)
        mesh = os.path.join(rc_mesh_dir, "mesh.obj")
        mtl = os.path.join(rc_mesh_dir, "mesh.mtl")
        texture = os.path.join(rc_mesh_dir, "mesh_u1_v1.png")
        if os.path.exists(mesh):
            if not os.path.exists(out_mesh_dir):
                os.makedirs(out_mesh_dir)
            shutil.copyfile(mesh, os.path.join(out_mesh_dir, "mesh.obj"))
            shutil.copyfile(mtl, os.path.join(out_mesh_dir, "mesh.mtl"))
            shutil.copyfile(texture, os.path.join(out_mesh_dir, "mesh_u1_v1.png"))
            shutil.copyfile(texture, os.path.join(out_mesh_dir, "texture.png"))
   

if __name__ == "__main__":
    main()
