
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
This script processes images and creates an RealityCapture (RC) reconstruction, then creates a colmap version using the RC camera registration

Parameters: -h help,
            -path <path to your dataset folder>,

Usage: python processRC.py -path <path to your dataset folder>

"""

import os, sys, shutil
import json
import argparse
from utils.paths import getBinariesPath, getColmapPath, getMeshlabPath
from utils.commands import  getProcess, getColmap, getRCprocess
from utils.TaskPipeline import TaskPipeline
import rc_tools
import selective_colmap_process

os.sys.path.append('../preprocess/')
os.sys.path.append('../preprocess/realityCaptureTools')
os.sys.path.append('../preprocess/fullColmapProcess')
os.sys.path.append('../preprocess/converters')

def main():
    parser = argparse.ArgumentParser()

    # common arguments
    parser.add_argument("--sibrBinariesPath", type=str, default=getBinariesPath(), help="binaries directory of SIBR")
    parser.add_argument("--colmapPath", type=str, default=getColmapPath(), help="path to directory colmap.bat / colmap.bin directory")
    parser.add_argument("--quality", type=str, default='default', choices=['default', 'low', 'medium', 'average', 'high', 'extreme'],
        help="quality of the reconstruction")
    parser.add_argument("--path", type=str, required=True, help="path to your dataset folder")
    parser.add_argument("--dry_run", action='store_true', help="run without calling commands")
    parser.add_argument("--rc_path", type=str, required=False, help="path to rc dataset, containing bundle.out and images")
    parser.add_argument("--out_path", type=str, required=False, help = "output path ")
    parser.add_argument("--video_name", type=str, default='default', required=False, help = "name of video file to load")
    parser.add_argument("--create_colmap", action='store_true', help="create colmap hierarchy")
    parser.add_argument("--from_step", type=str, default='default', help="Run from this step to --to_step (or end if no to_step")
    parser.add_argument("--to_step", type=str, default='default', help="up to but *excluding* this step (from --from_step); must be unique steps")
    parser.add_argument("--no_video", action='store_true', help="No video")
    parser.add_argument("--has_video", action='store_true', help="Has video")

    # RC arguments
    parser.add_argument("--config_folder", type=str, default='default', help="folder containing configuration files; usually cwd")
    parser.add_argument("--model_name", type=str, default='default', help="Internal name of RC model")
    parser.add_argument("--one_over_fps", type=str, default='default', help="Sampling rate for the video")

    # needed to avoid parsing issue for passing arguments to next command (TODO)
    parser.add_argument("--video_filename", type=str, default='default', help="full path of video file (internal argument; do not set)")
    parser.add_argument("--mesh_obj_filename", type=str, default='default', help="full path of obj mesh file (internal argument; do not set)")
    parser.add_argument("--mesh_xyz_filename", type=str, default='default', help="full path of xyz point cloud file (internal argument; do not set)")
    parser.add_argument("--mesh_ply_filename", type=str, default='default', help="full path of ply mesh file (internal argument; do not set)")

    # colmap
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

    from_step = args["from_step"]
    to_step = args["to_step"]

    # Update args with quality values
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "ColmapQualityParameters.json"), "r") as qualityParamsFile:
        qualityParams = json.load(qualityParamsFile)

        for key, value in qualityParams.items():
            if not key in args or args[key] is None:
                args[key] = qualityParams[key][args["quality"]] if args["quality"] in qualityParams[key] else qualityParams[key]["default"]

    # Get process steps
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "processRCSteps.json"), "r") as processStepsFile:
        steps = json.load(processStepsFile)["steps"]

    # Fixing path values
    args["path"] = os.path.abspath(args["path"])
    args["sibrBinariesPath"] = os.path.abspath(args["sibrBinariesPath"])
    args["colmapPath"] = os.path.abspath(args["colmapPath"])
    args["gpusIndices"] = ','.join([str(i) for i in range(args["numGPUs"])])
    if args["no_video"]:
        args["has_video"] = False
    else:
        # on by default
        args["has_video"] = True

    args["mesh_obj_filename"] = os.path.join(args["path"], os.path.join("rcScene", os.path.join("meshes", "mesh.obj")))
    args["mesh_xyz_filename"] = os.path.join(args["path"], os.path.join("rcScene", os.path.join("meshes", "point_cloud.xyz")))
    args["mesh_ply_filename"] = os.path.join(args["path"], os.path.join("sibr", os.path.join("capreal", "mesh.ply")))
    # fixed in preprocess
    args["video_filename"] = os.path.join(args["path"], os.path.join("raw", os.path.join("videos", "XXX.mp4")))
    if args["config_folder"] == 'default':
        args["config_folder"] = "."
    if args["one_over_fps"] == 'default':
        args["one_over_fps"] = "0.02"


    programs = {
        "colmap": {
            "path": getColmap(args["colmapPath"])
        },
        "RC": {
            "path": getRCprocess()
        }
    }

    # TODO: move to generic taskpipeline code; 
    if( from_step != 'default' ):
        # check if to_step exists
        # select steps
        newsteps = []
        adding_steps = False
        for s in steps:
            if s['name'] == from_step :
                adding_steps = True
            if s['name'] == to_step :
                break
            if adding_steps :
                newsteps.append(s)

        steps = newsteps

    pipeline = TaskPipeline(args, steps, programs)

    pipeline.runProcessSteps()
    
    print("selectiveColmapProcess has finished successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
