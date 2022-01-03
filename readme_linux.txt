1. First load the required libraries by running the mods file
2. Make the library using the following command cmake .. -DBUILD_IBR_SCENE_SCALE_MATERIALS_UTILS=ON -DBUILD_IBR_OPTIX=ON in cmake directory. Make sure you have scene_scale_materials_utils project and optix wrapper in src/projects directory.
3. Run make install to install the apps.
