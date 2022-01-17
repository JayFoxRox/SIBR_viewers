import os
import os.path
import sys
import argparse

import cv2
print(cv2.__version__)

def extract_images(pathIn, pathOut, videoName, maxNumFrames = -1, resize=False):
    count = 0
    vidcap = cv2.VideoCapture(pathIn)
    fps = round(vidcap.get(cv2.CAP_PROP_FPS))
    total_frames = vidcap.get(7)
    print("FPS = ", fps)
    success,image = vidcap.read()
    success = True
    print("Extracting ", total_frames/2, " Frames" )
    fileNames = []
    newFolder = pathOut + "\\%s" % (videoName)
    if not os.path.exists(newFolder):
      print( "Creating: ", newFolder)
      os.makedirs(newFolder, exist_ok=True)

    for frame in range(round(total_frames/2)):
        # every 2nd frame
        vidcap.set(cv2.CAP_PROP_POS_MSEC,(frame*2))
        success,image = vidcap.read()
        if not success:
           break
        resized = image
        if resize :
            print('Original Dimensions : ',image.shape)
            scale_percent = 52 # percent of original size
            width = int(image.shape[1] * scale_percent / 100)
            height = int(image.shape[0] * scale_percent / 100)
            dim = (width, height)
            resized = cv2.resize(image, dim, interpolation = cv2.INTER_AREA)

        print( "Writing: ", pathOut + "\\%s\\frame%04d.png" % (videoName, count))     
        fileNames.append(pathOut + "\\%s\\frame%04d.png" % (videoName, count))     
        cv2.imwrite( pathOut + "\\%s\\frame%04d.png" % (videoName, count), resized)     # save frame as PNG file
 
        if maxNumFrames == count:
           break;

        count = count + 1
    return fileNames


def fix_cameras(path):
	return True

def extract_video_frames(pathIn, pathOut):
    cnt = 0
    fileNames = []
    for filename in os.listdir(pathIn):
      with open(os.path.join(pathIn, filename), 'r') as f:
          print("Extracting Video from File: ", f.name)
#          fileNames  = fileNames + extract_images(f.name, pathOut, "Video%d" % cnt, maxNumFrames=30, resize=True)
          fileNames  = fileNames + extract_images(f.name, pathOut, "Video%d" % cnt, resize=True)
#          extract_images(f.name, pathOut, videoName="Video%d" % cnt)
          cnt = cnt+1

    with open(os.path.dirname(pathIn) + "\\videos\\Video_Frames.txt", 'w') as f:
       for item in fileNames:
          f.write("%s\n" % os.path.basename(item))
       f.close()

