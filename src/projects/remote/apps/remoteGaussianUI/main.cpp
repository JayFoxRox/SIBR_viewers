/*
 * Copyright (C) 2020, Inria
 * GRAPHDECO research group, https://team.inria.fr/graphdeco
 * All rights reserved.
 *
 * This software is free for non-commercial, research and evaluation use 
 * under the terms of the LICENSE.md file.
 *
 * For inquiries contact sibr@inria.fr and/or George.Drettakis@inria.fr
 */


#include <fstream>

#include <core/graphics/Window.hpp>
#include <core/view/MultiViewManager.hpp>
#include <core/system/String.hpp>
#include "projects/remote/renderer/RemotePointView.hpp" 

#include <core/renderer/DepthRenderer.hpp>
#include <core/raycaster/Raycaster.hpp>
#include <core/view/SceneDebugView.hpp>

#define PROGRAM_NAME "SIBR Remote Gaussian Viewer"
using namespace sibr;

const char* usage = ""
"Usage: " PROGRAM_NAME " -path <dataset-path>"    	                                "\n"
;

int main(int ac, char** av) {

	// Parse Command-line Args
	CommandLineArgs::parseMainArgs(ac, av);
	RemoteAppArgs myArgs;
	myArgs.displayHelpIfRequired();

	const bool doVSync = !myArgs.vsync;
	// rendering size
	uint rendering_width = myArgs.rendering_size.get()[0];
	uint rendering_height = myArgs.rendering_size.get()[1];
	
	// window size
	uint win_width = rendering_width; // myArgs.win_width;
	uint win_height = rendering_height; // myArgs.win_height;

	// Window setup
	sibr::Window		window(PROGRAM_NAME, sibr::Vector2i(50, 50), myArgs, getResourcesDirectory() + "/remote/" + PROGRAM_NAME + ".ini");

	BasicIBRScene::Ptr		scene(new BasicIBRScene(myArgs, true));

	// Setup the scene: load the proxy, create the texture arrays.
	const uint flags = SIBR_GPU_LINEAR_SAMPLING | SIBR_FLIP_TEXTURE;

	// Fix rendering aspect ratio if user provided rendering size
	uint scene_width = scene->cameras()->inputCameras()[0]->w();
	uint scene_height = scene->cameras()->inputCameras()[0]->h();
	float scene_aspect_ratio = scene_width * 1.0f / scene_height;
	float rendering_aspect_ratio = rendering_width * 1.0f / rendering_height;

	if ((rendering_width > 0) && !myArgs.force_aspect_ratio ) {
		if (abs(scene_aspect_ratio - rendering_aspect_ratio) > 0.001f) {
			if (scene_width > scene_height) {
				rendering_height = rendering_width / scene_aspect_ratio;
			}
			else {
				rendering_width = rendering_height * scene_aspect_ratio;
			}
		}
	}

	// check rendering size
	rendering_width = (rendering_width <= 0) ? scene->cameras()->inputCameras()[0]->w() : rendering_width;
	rendering_height = (rendering_height <= 0) ? scene->cameras()->inputCameras()[0]->h() : rendering_height;
	Vector2u usedResolution(rendering_width, rendering_height);
	std::cerr << " USED RES " << usedResolution << " scene w h " << scene_width << " : " << scene_height <<  
		 " NAME " << scene->cameras()->inputCameras()[0]->name() << std::endl;

	const unsigned int sceneResWidth = usedResolution.x();
	const unsigned int sceneResHeight = usedResolution.y();

	RemotePointView::Ptr	pointBasedView(new RemotePointView(scene, sceneResWidth, sceneResHeight));

	// Raycaster.
	std::shared_ptr<sibr::Raycaster> raycaster = std::make_shared<sibr::Raycaster>();
	raycaster->init();
	raycaster->addMesh(scene->proxies()->proxy());

	// Camera handler for main view.
	sibr::InteractiveCameraHandler::Ptr generalCamera(new InteractiveCameraHandler());
	generalCamera->setup(scene->cameras()->inputCameras(), Viewport(0, 0, (float)usedResolution.x(), (float)usedResolution.y()), raycaster);

	// Add views to mvm.
	MultiViewManager        multiViewManager(window, false);
	
	multiViewManager.addIBRSubView("Point view", pointBasedView, usedResolution, ImGuiWindowFlags_NoResize); //  ImGuiWindowFlags_ResizeFromAnySide);
	multiViewManager.addCameraForView("Point view", generalCamera);

	// Top view
	const std::shared_ptr<sibr::SceneDebugView> topView(new sibr::SceneDebugView(scene, generalCamera, myArgs));
	multiViewManager.addSubView("Top view", topView, usedResolution);
	topView->active(false);

	CHECK_GL_ERROR;

	// save images
	generalCamera->getCameraRecorder().setViewPath(pointBasedView, myArgs.dataset_path.get());
	if (myArgs.pathFile.get() !=  "" ) {
		generalCamera->getCameraRecorder().loadPath(myArgs.pathFile.get(), usedResolution.x(), usedResolution.y());
		generalCamera->getCameraRecorder().recordOfflinePath(myArgs.outPath, multiViewManager.getIBRSubView("Point view"), "");
		if( !myArgs.noExit )
			exit(0);
	}

	// Main looooooop.
	while (window.isOpened()) {

		sibr::Input::poll();
		window.makeContextCurrent();
		if (sibr::Input::global().key().isPressed(sibr::Key::Escape)) {
			window.close();
		}

		multiViewManager.onUpdate(sibr::Input::global());
		multiViewManager.onRender(window);

		window.swapBuffer();
		CHECK_GL_ERROR;
	}

	return EXIT_SUCCESS;
}
