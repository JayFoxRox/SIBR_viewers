#
# Convert RealityCapture export to colmap
#

""" @package dataset_tools_preprocess
This script runs a pipeline to create Colmap reconstruction data

Parameters: -h help,
            -path <path to your dataset folder>,
            -colmapPath <colmap path directory which contains colmap.bat / colmap.bin>,
            -quality 

Usage: python rc_to_colmap.py --rc_path <path to your rc dataset, containing bundle.out and images  >
                              --colmap_path <out path to colmap>
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
    parser.add_argument("--colmap_path", type=str, required=True, help = "output path to colmap")

    args = vars(parser.parse_args())

    input_bundle = bundle.Bundle(os.path.join(args["rc_path"] , "bundle.out"))

    #
    # create cameras.txt
    #

    fname = os.path.join(args["colmap_path"], "cameras.txt")
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
    fname = os.path.join(args["colmap_path"], "images.txt")

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
         t = -br * np.matrix([cam.translation[0], cam.translation[1], cam.translation[2]]).transpose()
         
         # sibr save to colmap
         br = br * np.matrix([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
         br = br.transpose()
         sci_rot = R.from_matrix(br)
         sci_quat = sci_rot.as_quat()
         t = -br * t

         outfile.write("{} {} {} {} {} {} {} {} {} {}\n".format(camera_id, sci_quat[3], -sci_quat[0], -sci_quat[1], -sci_quat[2], t[0,0], t[1,0], t[2,0], camera_id, name))
         camera_id = camera_id + 1
      outfile.close()

    """
    with open(fname, 'w') as outfile:
      outfile.write( "# Image list with two lines of data per image:\n" )
      outfile.write( "#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n" )
      outfile.write( "#   POINTS2D[] as (X, Y, POINT3D_ID)\n" )
      for cam in input_bundle.list_of_cameras:
         name = os.path.basename(input_bundle.list_of_input_images[camera_id-1].path)
         # colmap internal
         t = [cam.translation[0], -cam.translation[1], -cam.translation[2]]
         br = np.matrix(cam.rotation)
         br [1, 0] = - br[1, 0]
         br [1, 1] = - br[1, 1]
         br [1, 2] = - br[1, 2]
         br [2, 0] = - br[2, 0]
         br [2, 1] = - br[2, 1]
         br [2, 2] = - br[2, 2]

         sci_rot = R.from_matrix(br.transpose())
         sci_quat = sci_rot.as_quat()

         outfile.write("{} {} {} {} {} {} {} {} {} {}\n".format(camera_id, sci_quat[3], sci_quat[0], sci_quat[1], sci_quat[2], t[0], t[1], t[2], camera_id, name))
         camera_id = camera_id + 1
      outfile.close()
      """
            
#
# create points3D.txt
#
   

if __name__ == "__main__":
    main()
