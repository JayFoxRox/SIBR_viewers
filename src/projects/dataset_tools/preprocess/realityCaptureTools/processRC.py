
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
from utils.commands import  getProcess, getColmap
from utils.TaskPipeline import TaskPipeline
import rc_tools

def main():
    parser = argparse.ArgumentParser()

    # common arguments
    parser.add_argument("--path", type=str, required=True, help="path to your dataset folder")
    parser.add_argument("--dry_run", action='store_true', help="run without calling commands")
    parser.add_argument("--rc_path", type=str, required=False, help="path to rc dataset, containing bundle.out and images")
    parser.add_argument("--out_path", type=str, required=False, help = "output path ")
    parser.add_argument("--create_colmap", action='store_true', help="create colmap hierarchy")
    parser.add_argument("--from_step", type=str, default='default', help="Run from this step to --to_step")
    parser.add_argument("--to_step", type=str, default='default', help="up to but *excluding* this step (from --from_step); must be unique steps")

    args = vars(parser.parse_args())

    from_step = args["from_step"]
    to_step = args["to_step"]

    # Get process steps
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "processRCSteps.json"), "r") as processStepsFile:
        steps = json.load(processStepsFile)["steps"]

    # Fixing path values
    args["path"] = os.path.abspath(args["path"])

    programs = {
        "runRC": {
            "path": ".\\runRC.bat"
        }
    }

    # TODO: move to generic taskpipeline code; 
    if( from_step != 'default' ):
        # check if to_step exists
        if( to_step != 'default' ):
            # select steps
            newsteps = []
            adding_steps = False
            for s in steps:
                if( s['name'] == from_step ):
                    adding_steps = True
                # special case for last step that should be added
                if( s['name'] == to_step and s['name'] != "rc_to_colmap_path_cameras" ):
                    break
                if adding_steps :
                    newsteps.append(s)
            steps = newsteps
        else:
            print("--from_step given without --to_step; ignoring")

    pipeline = TaskPipeline(args, steps, programs)

    pipeline.runProcessSteps()
    
    print("selectiveColmapProcess has finished successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
