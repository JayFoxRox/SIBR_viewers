# Copyright (C) 2020, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
# 
# This software is free for non-commercial, research and evaluation use 
# under the terms of the LICENSE.md file.
# 
# For inquiries contact sibr@inria.fr and/or George.Drettakis@inria.fr


#!/usr/bin/env python
#! -*- encoding: utf-8 -*-

""" @package dataset_tools_preprocess
This script runs a pipeline to create Colmap reconstruction data assuming that calibrateOnly.py was run before and that a colmap  directory exists

Parameters: -h help,
            -path <path to your dataset folder>,
            -sibrBinariesPath <binaries directory of SIBR>,
            -colmapPath <colmap path directory which contains colmap.bat / colmap.bin>,
            -quality <quality of the reconstruction : 'low', 'medium', 'high', 'extreme'>,

Usage: python MVSafterCalibration.py -path <path to your dataset folder>
                                   -sibrBinariesPath <binaries directory of SIBR>
                                   -colmapPath <colmap path directory which contains colmap.bat / colmap.bin>
                                   -quality <quality of the reconstruction : 'low', 'medium', 'high', 'extreme'>

"""

import os, sys, shutil
import json
import argparse
from utils.paths import getBinariesPath, getColmapPath, getMeshlabPath
from utils.commands import  getProcess, getColmap
from utils.TaskPipeline import TaskPipeline

def main():
    parser = argparse.ArgumentParser()

    # common arguments
    parser.add_argument("--path", type=str, required=True, help="path to your dataset folder")
    parser.add_argument("--sibrBinariesPath", type=str, default=getBinariesPath(), help="binaries directory of SIBR")
    parser.add_argument("--colmapPath", type=str, default=getColmapPath(), help="path to directory colmap.bat / colmap.bin directory")
    parser.add_argument("--meshlabPath", type=str, default=getMeshlabPath(), help="path to meshlabserver directory")
    parser.add_argument("--quality", type=str, default='default', choices=['default', 'low', 'medium', 'average', 'high', 'extreme'],
        help="quality of the reconstruction")
    parser.add_argument("--dry_run", action='store_true', help="run without calling commands")
    parser.add_argument("--with_texture", action='store_true', help="Add texture steps")
    parser.add_argument("--create_sibr_scene", action='store_true', help="Create SIBR scene")
    parser.add_argument("--meshsize", type=str, help="size of the output mesh in K polygons (ie 200 == 200,000 polygons). Values allowed: 200, 250, 300, 350, 400")
    
    #colmap performance arguments
    parser.add_argument("--numGPUs", type=int, default=2, help="number of GPUs allocated to Colmap")

    # Patch match stereo
    parser.add_argument("--PatchMatchStereo.max_image_size", type=int, dest="patchMatchStereo_PatchMatchStereoDotMaxImageSize")
    parser.add_argument("--PatchMatchStereo.window_radius", type=int, dest="patchMatchStereo_PatchMatchStereoDotWindowRadius")
    parser.add_argument("--PatchMatchStereo.window_step", type=int, dest="patchMatchStereo_PatchMatchStereoDotWindowStep")
    parser.add_argument("--PatchMatchStereo.num_samples", type=int, dest="patchMatchStereo_PatchMatchStereoDotNumSamples")
    parser.add_argument("--PatchMatchStereo.num_iterations", type=int, dest="patchMatchStereo_PatchMatchStereoDotNumIterations")
    parser.add_argument("--PatchMatchStereo.geom_consistency", type=int, dest="patchMatchStereo_PatchMatchStereoDotGeomConsistency")

    # Stereo fusion
    parser.add_argument("--StereoFusion.check_num_images", type=int, dest="stereoFusion_CheckNumImages")
    parser.add_argument("--StereoFusion.max_image_size", type=int, dest="stereoFusion_MaxImageSize")

    args = vars(parser.parse_args())

    # Update args with quality values
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "CalibrateOnlyParameters.json"), "r") as qualityParamsFile:
        qualityParams = json.load(qualityParamsFile)

        for key, value in qualityParams.items():
            if not key in args or args[key] is None:
                args[key] = qualityParams[key][args["quality"]] if args["quality"] in qualityParams[key] else qualityParams[key]["default"]

    # Get process steps
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "MVSafterCalibrationSteps.json"), "r") as processStepsFile:
        steps = json.load(processStepsFile)["steps"]


    # Fixing path values
    args["path"] = os.path.abspath(args["path"])
    args["sibrBinariesPath"] = os.path.abspath(args["sibrBinariesPath"])
    args["colmapPath"] = os.path.abspath(args["colmapPath"])

    args["gpusIndices"] = ','.join([str(i) for i in range(args["numGPUs"])])
    new_folder = os.path.abspath(os.path.join(args["path"], "text"))
    print("Creating folder %s..." % new_folder)
    os.makedirs(new_folder, exist_ok=True)

    src = os.path.abspath(os.path.join(args["path"], "colmap"))
    dst = os.path.abspath(os.path.join(args["path"], "colmap_sfmonly"))

    if os.path.exists(dst):
       print("WARNING removing sfmonly !")
       # make 1 copy 
       if not os.path.exists(dst+"_1"):
         print("WARNING copying ! ", dst, " to " , dst+"_1")
         shutil.copytree(src, dst+"_1")
       shutil.rmtree(dst)

    # copy calibration only recon to colmap_sfmonly; will keep all registered images
    shutil.copytree(src, dst)

    # Remove all traces of full calib
    calib0 = os.path.abspath(os.path.join(args["path"], "colmap\\sparse\\0"))
    if os.path.exists(calib0):
       print("WARNING removing sparse/0/ dir !")
       shutil.rmtree(calib0)
    # recreate empty dir
    os.makedirs(calib0, exist_ok=True)

    # create path camera data for each video
    src = os.path.abspath(os.path.join(args["path"], "colmap\\sparse\\")) + "\\images.txt"
    with open(src, 'r') as sourcefile:
        source = sourcefile.read().splitlines()

    src = os.path.abspath(os.path.join(args["path"], "videos\\")) + "\\Video_frames.txt"
    with open(src, 'r') as keyfile:
        keys = keyfile.read().split()

    # write out camera data
    videodir = os.path.abspath(os.path.join(args["path"], "videos"))
    cnt = 0 

    camerasfile = os.path.abspath(os.path.join(args["path"], "colmap\\sparse\\")) + "\\cameras.txt"
    for filename in os.listdir(videodir):
        # find and loop over videos
        if "MP4" in filename:
           currentVideo = "Video%d" % cnt
           dstpath = os.path.join(os.path.abspath(os.path.join(args["path"], "videos\\")) ,  currentVideo )

           print("Creating video camera data ", dstpath)
           os.makedirs(dstpath, exist_ok=True)
           dst = dstpath + "\\images.txt"
           with open(dst, 'w') as outfile:
              for line in source:
                 if line.split():
                    if line.split()[-1] in keys:
#                      print("Writing ", line, " to " , outfile )
                      outfile.write(line + "\n")
           outfile.close()
           shutil.copyfile(camerasfile, dstpath +"\\cameras.txt")
        cnt = cnt + 1

    # move all the video images so they are not taken into account in further processing
    imagedir = args["path"] + "\\images"
    image_directory = os.listdir(imagedir)

    videodir = args["path"] + "\\videos"
    video_directory = os.listdir(videodir)

    # move video images
    cnt = 0
    for videoname in video_directory: 
      if os.path.isdir(os.path.join(videodir, videoname)):
         dstpath = os.path.join(os.path.abspath(os.path.join(args["path"], "images\\")) , videoname)
         print("Creating ", dstpath)
         os.makedirs(dstpath, exist_ok=True)
         for fname in image_directory: 
           print("Search ", videoname , " in " , fname )
           if videoname in fname:
             if not os.path.exists(os.path.join(dstpath,fname)):
                shutil.move(os.path.join(imagedir,fname), os.path.join(dstpath,fname))
                print('moving ', os.path.join(imagedir,fname), " to " , os.path.join(dstpath,fname))

    exit()

    programs = {
        "colmap": {
            "path": getColmap(args["colmapPath"])
        },
    }

    pipeline = TaskPipeline(args, steps, programs)

    pipeline.runProcessSteps()
    
    print("calibrateOnly has finished successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
