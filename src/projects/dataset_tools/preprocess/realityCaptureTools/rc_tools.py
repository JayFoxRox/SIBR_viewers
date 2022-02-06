#
# RealityCapture tools
#
import os
import os.path
import sys
import argparse
import shutil
import sqlite3
import read_write_model as rwm


import cv2
print(cv2.__version__)


""" @package dataset_tools_preprocess
Library for RealityCapture treatment


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

def preprocess_for_rc(path, videoName=""):
    # create train/test split (every 10 images for now)
    TEST_SKIP = 10

    imagespath = os.path.abspath(os.path.join(path, "images"))
    videopath = os.path.abspath(os.path.join(path, "videos"))
    testpath = os.path.abspath(os.path.join(path, "test"))
    trainpath = os.path.abspath(os.path.join(path, "test"))
    gtvideo_path = os.path.abspath(os.path.join(path, "video_path"))

    cnt = 0
    train_path =os.path.join(path, "train")
    if not os.path.exists(train_path):
        os.makedirs(train_path)
    test_path = os.path.join(path, "test")
    if not os.path.exists(test_path):
        os.makedirs(test_path)


    print("Test/Train ", test_path,  "\n", train_path)

    for filename in os.listdir(imagespath):
        ext = os.path.splitext(filename)[1]
        if ext == ".JPG" or ext == ".jpg" or ext == ".PNG" or ext == ".jpg" :
            image = os.path.join(imagespath, filename) 
            print("IM ", image)
            if not(cnt % TEST_SKIP ):
                filename = "test_"+filename
                fname = os.path.join(test_path, filename)
                print("Copying ", image, " to ", fname , " in test")
                shutil.copyfile(image, fname)
            else:
                filename = "train_"+filename
                fname = os.path.join(test_path, filename)
                fname = os.path.join(train_path, filename)
                print("Copying ", image, " to ", fname , " in train")
                shutil.copyfile(image, fname)

        cnt = cnt + 1

    # extract video name -- if not given, take first
    if videoName == "":
        for filename in os.listdir(videopath):
            if ("MP4" in filename) or ("mp4" in filename):
                videoName = filename

    # copy to "video.mp4"
    vname = os.path.join(videopath, videoName)
    if os.path.exists(vname):
        print("Copying video ", vname, " to ",  os.path.join(videopath, "video.mp4"))
        shutil.copyfile(vname, os.path.join(videopath, "video.mp4"))


def rc_to_colmap(rc_path, out_path, create_colmap=False, target_width=-1):

    input_bundle = bundle.Bundle(os.path.join(rc_path , "bundle.out"))
    input_bundle.generate_list_of_images_file (os.path.join(rc_path , "list_images.txt"))

    dst_image_path = os.path.join(out_path, "images")

    # create entire colmap structure
    #
    if create_colmap:
        dir_name = os.path.join(out_path, "stereo")
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        dst_image_path = os.path.join(dir_name, "images")

        sparse_stereo_dir = dir_name = os.path.join(dir_name, "sparse")
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    else:
        sparse_stereo_dir = out_path

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

            # resize images if required
            if target_width != -1:
                orig_width = width
                width = float(target_width)
                scale = float(target_width) / orig_width 
                aspect = height / orig_width
                height = width * aspect
                focal_length = scale * focal_length
               
            outfile.write("{} PINHOLE {} {} {} {} {} {}\n".format(camera_id, int(width), int(height), focal_length, focal_length, width/2.0, height/2.0))
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
    for fname in os.listdir(rc_path):
        if fname.endswith(".jpg") or fname.endswith(".JPG") or fname.endswith(".png") or fname.endswith(".PNG") :
            src_image_fname = os.path.join(rc_path, fname)
            dst_image_fname = os.path.join(dst_image_path, os.path.basename(fname))
            print("Copying ", src_image_fname, "to ", dst_image_fname)

            # resize if necessary
            if target_width != -1:
                im = cv2.imread(src_image_fname, cv2.IMREAD_UNCHANGED)
                orig_width = im.shape[1]
                orig_height = im.shape[0]
                width = float(target_width)
                scale = float(target_width)/ orig_width 
                aspect = orig_height / orig_width
                height = width * aspect
                dim = (int(width), int(height))
                im = cv2.resize(im, dim, interpolation = cv2.INTER_AREA)
                cv2.imwrite(dst_image_fname, im)
            else:
                shutil.copyfile(src_image_fname, dst_image_fname)

    # copy mesh; fake it
    if create_colmap:
        # assume meshes above
        rc_mesh_dir = os.path.join(os.path.abspath(os.path.join(rc_path, os.pardir)), "meshes")
        out_mesh_dir = os.path.join(os.path.abspath(os.path.join(out_path, os.pardir)), "capreal")
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
   

