::CapturingReality

:: switch off console output
::@echo off
@echo on

call SetVariables.bat

:: variable storing path to images for creating model
set Images="%RootFolder%\images"
set TestImages="%RootFolder%\test"
set TrainImages="%RootFolder%\train"
set PathImages="%RootFolder%\train"

:: set a new name for calculated model
set ModelName="RCTest"

:: set the path, where model is going to be saved, and its name
set ModelObj="%RootFolder%\meshes\mesh.obj"
set ModelXYZ="%RootFolder%\meshes\point_cloud.xyz"

:: variable storing path to images for texturing model
set Project="%RootFolder%\rcproj\mesh.rcproj"

:: run RealityCapture
:: test and fix video import when RC working again
::        -importVideo %Video% %RootFolder%\video_frames\ %FPS% ^

echo %@Images%

%RealityCaptureExe% -importLicense %RootFolder%\rc.rclicense ^
        -addFolder %TrainImages% ^
        -addFolder %TestImages% ^
        -align ^
        -selectMaximalComponent ^
        -selectAllImages ^
        -enableAlignment false ^
        -selectImage *test_* ^
        -enableAlignment true ^
        -exportRegistration %RootFolder%\test_cameras\bundle.out %ConfigFolder%\registrationConfig.xml ^
        -selectAllImages ^
        -enableAlignment false ^
        -selectImage *frame* ^
        -enableAlignment true ^
        -exportRegistration %RootFolder%\path_cameras\bundle.out %ConfigFolder%\registrationConfig.xml ^
        -selectAllImages ^
        -enableAlignment false ^
        -selectImage *train_* ^
        -enableAlignment true ^
        -exportRegistration %RootFolder%\cameras\bundle.out %ConfigFolder%\registrationConfig.xml ^
        -setReconstructionRegionAuto ^
        -scaleReconstructionRegion 1.4 1.4 2.5 center factor ^
        -calculateNormalModel ^
        -selectMarginalTriangles ^
        -removeSelectedTriangles ^
        -calculateTexture ^
        -save %Project% ^
        -renameSelectedModel %ModelName% ^
        -exportModel %ModelName% %ModelObj% ^
        -exportModel %ModelName% %ModelXYZ% ^
        -quit
       
        




