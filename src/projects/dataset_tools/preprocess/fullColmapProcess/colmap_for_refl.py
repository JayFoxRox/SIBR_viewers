import os
import os.path
import sys
import argparse

import cv2
print(cv2.__version__)

def extractImages(pathIn, pathOut, videoName, maxNumFrames = -1, resize=False):
    count = 0
    vidcap = cv2.VideoCapture(pathIn)
    fps = round(vidcap.get(cv2.CAP_PROP_FPS))
    total_frames = vidcap.get(7)
    print("FPS = ", fps)
    success,image = vidcap.read()
    success = True
    print("Extracting ", total_frames/2, " Frames" )
    fileNames = []
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

        print( "Writing: ", pathOut + "\\%s_frame%04d.png" % (videoName, count))     
        fileNames.append(pathOut + "\\%s_frame%04d.png" % (videoName, count))     
        cv2.imwrite( pathOut + "\\%s_frame%04d.png" % (videoName, count), resized)     # save frame as JPEG file
 
        if maxNumFrames == count:
           break;

        count = count + 1
    return fileNames


if __name__=="__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--pathIn", help="path to video")
    a.add_argument("--pathOut", help="path to images")
    args = a.parse_args()
    print(args)

    cnt = 0
    fileNames = []
    for filename in os.listdir(args.pathIn):
      with open(os.path.join(args.pathIn, filename), 'r') as f:
          print("Extracting Video from File: ", f.name)
          fileNames  = fileNames + extractImages(f.name, args.pathOut, "Video%d" % cnt, maxNumFrames=30, resize=True)
#          extractImages(f.name, args.pathOut, videoName="Video%d" % cnt)
          cnt = cnt+1

    with open(os.path.dirname(args.pathIn) + "\\videos\\Video_Frames.txt", 'w') as f:
       for item in fileNames:
          f.write("%s\n" % os.path.basename(item))
       f.close()

