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

#include <projects/gaussianviewer/renderer/GaussianView.hpp>
#include <core/graphics/GUI.hpp>
#include <thread>
#include <boost/asio.hpp>
#include <rasterizer.h>

// Define the types and sizes that make up the contents of each Gaussian 
// in the trained model.
typedef sibr::Vector3f Pos;
struct SHs
{
	float shs[48];
};
struct Scale
{
	float scale[3];
};
struct Rot
{
	float rot[4];
};
struct RichPoint
{
	Pos pos;
	float n[3];
	SHs shs;
	float opacity;
	Scale scale;
	Rot rot;
};

float sigmoid(const float m1)
{
	return 1.0 / (1.0 + exp(-m1));
}

// Load the Gaussians from the given file.
int loadPly(const char* filename,
	std::vector<Pos>& pos,
	std::vector<SHs>& shs,
	std::vector<float>& opacities,
	std::vector<Scale>& scales,
	std::vector<Rot>& rot)
{
	std::ifstream infile(filename, std::ios_base::binary);

	if (!infile.good())
		throw std::runtime_error("File not found!");

	// "Parse" header (it has to be a specific format anyway)
	std::string buff;
	std::getline(infile, buff);
	std::getline(infile, buff);

	std::string dummy;
	std::getline(infile, buff);
	std::stringstream ss(buff);
	int count;
	ss >> dummy >> dummy >> count;

	// Output number of Gaussians contained
	std::cout << count << std::endl;

	while (std::getline(infile, buff))
		if (buff.compare("end_header") == 0)
			break;

	// Read all Gaussians at once (AoS)
	std::vector<RichPoint> points(count);
	infile.read((char*)points.data(), count * sizeof(RichPoint));

	// Resize our SoA data
	pos.resize(count);
	shs.resize(count);
	scales.resize(count);
	rot.resize(count);
	opacities.resize(count);

	// Gaussians are done training, they won't move anymore. Arrange
	// them according to 3D Morton order. This means better cache
	// behavior for reading Gaussians that end up in the same tile 
	// (close in 3D --> close in 2D).
	sibr::Vector3f minn(FLT_MAX, FLT_MAX, FLT_MAX);
	sibr::Vector3f maxx = -minn;
	for (int i = 0; i < count; i++)
	{
		maxx = maxx.cwiseMax(points[i].pos);
		minn = minn.cwiseMin(points[i].pos);
	}
	std::vector<std::pair<uint64_t, int>> mapp(count);
	for (int i = 0; i < count; i++)
	{
		sibr::Vector3f rel = (points[i].pos - minn).array() / (maxx - minn).array();
		sibr::Vector3f scaled = ((float((1 << 21) - 1)) * rel);
		sibr::Vector3i xyz = scaled.cast<int>();

		uint64_t code = 0;
		for (int i = 0; i < 21; i++) {
			code |= ((uint64_t(xyz.x() & (1 << i))) << (2 * i + 0));
			code |= ((uint64_t(xyz.y() & (1 << i))) << (2 * i + 1));
			code |= ((uint64_t(xyz.z() & (1 << i))) << (2 * i + 2));
		}

		mapp[i].first = code;
		mapp[i].second = i;
	}
	auto sorter = [](const std::pair < uint64_t, int>& a, const std::pair < uint64_t, int>& b) {
		return a.first < b.first;
	};
	std::sort(mapp.begin(), mapp.end(), sorter);

	// Move data from AoS to SoA
	for (int k = 0; k < count; k++)
	{
		int i = mapp[k].second;
		pos[k] = points[i].pos;
		rot[k] = points[i].rot;
		// We have exp activation on scale, but it's done by the rasterizer
		scales[k] = points[i].scale;
		// We have sigmoid activation on opacities, not done by rasterizer
		opacities[k] = sigmoid(points[i].opacity);
		shs[k].shs[0] = points[i].shs.shs[0];
		shs[k].shs[1] = points[i].shs.shs[1];
		shs[k].shs[2] = points[i].shs.shs[2];
		for (int j = 1; j < 16; j++)
		{
			shs[k].shs[j * 3 + 0] = points[i].shs.shs[(j - 1) + 3];
			shs[k].shs[j * 3 + 1] = points[i].shs.shs[(j - 1) + 18];
			shs[k].shs[j * 3 + 2] = points[i].shs.shs[(j - 1) + 33];
		}
	}
	return count;
}

namespace sibr
{
	// A simple copy renderer class. Much like the original, but this one
	// reads from a buffer instead of a texture and blits the result to
	// a render target. 
	class BufferCopyRenderer
	{

	public:

		BufferCopyRenderer()
		{
			_shader.init("CopyShader",
				sibr::loadFile(sibr::getShadersDirectory("gaussian") + "/copy.vert"),
				sibr::loadFile(sibr::getShadersDirectory("gaussian") + "/copy.frag"));

			_flip.init(_shader, "flip");
			_width.init(_shader, "width");
			_height.init(_shader, "height");
		}

		void process(uint bufferID, IRenderTarget& dst, int width, int height, bool disableTest = true)
		{
			if (disableTest)
				glDisable(GL_DEPTH_TEST);
			else
				glEnable(GL_DEPTH_TEST);

			_shader.begin();
			_flip.send();
			_width.send();
			_height.send();

			dst.clear();
			dst.bind();

			glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, bufferID);

			sibr::RenderUtility::renderScreenQuad();

			dst.unbind();
			_shader.end();
		}

		/** \return option to flip the texture when copying. */
		bool& flip() { return _flip.get(); }
		int& width() { return _width.get(); }
		int& height() { return _height.get(); }

	private:

		GLShader			_shader; 
		GLuniform<bool>		_flip = false; ///< Flip the texture when copying.
		GLuniform<int>		_width = 1000;
		GLuniform<int>		_height = 800;
	};
}

std::function<char* (size_t N)> resizeFunctional(void** ptr, size_t& S) {
	auto lambda = [ptr, &S](size_t N) {
		if (N > S)
		{
			if (*ptr)
				cudaFree(*ptr);
			cudaMalloc(ptr, N);
			S = N;
		}
		return reinterpret_cast<char*>(*ptr);
	};
	return lambda;
}

sibr::GaussianView::GaussianView(const sibr::BasicIBRScene::Ptr & ibrScene, uint render_w, uint render_h, const char* file) :
	_scene(ibrScene),
	sibr::ViewBase(render_w, render_h)
{
	_pointbasedrenderer.reset(new PointBasedRenderer());
	_copyRenderer = new BufferCopyRenderer();
	_copyRenderer->flip() = true;
	_copyRenderer->width() = render_w;
	_copyRenderer->height() = render_h;

	std::vector<uint> imgs_ulr;
	const auto & cams = ibrScene->cameras()->inputCameras();
	for(size_t cid = 0; cid < cams.size(); ++cid) {
		if(cams[cid]->isActive()) {
			imgs_ulr.push_back(uint(cid));
		}
	}
	_scene->cameras()->debugFlagCameraAsUsed(imgs_ulr);

	// Load the PLY data (AoS) to the GPU (SoA)
	std::vector<Pos> pos;
	std::vector<Rot> rot;
	std::vector<Scale> scale;
	std::vector<float> opacity;
	std::vector<SHs> shs;
	count = loadPly(file, pos, shs, opacity, scale, rot);

	int P = count;

	// Allocate and fill the GPU data
	cudaMalloc((void**)&pos_cuda, sizeof(Pos) * P);
	cudaMemcpy(pos_cuda, pos.data(), sizeof(Pos) * P, cudaMemcpyHostToDevice);
	cudaMalloc((void**)&rot_cuda, sizeof(Rot) * P);
	cudaMemcpy(rot_cuda, rot.data(), sizeof(Rot) * P, cudaMemcpyHostToDevice);
	cudaMalloc((void**)&shs_cuda, sizeof(SHs) * P);
	cudaMemcpy(shs_cuda, shs.data(), sizeof(SHs) * P, cudaMemcpyHostToDevice);
	cudaMalloc((void**)&opacity_cuda, sizeof(float) * P);
	cudaMemcpy(opacity_cuda, opacity.data(), sizeof(float) * P, cudaMemcpyHostToDevice);
	cudaMalloc((void**)&scale_cuda, sizeof(Scale) * P);
	cudaMemcpy(scale_cuda, scale.data(), sizeof(Scale) * P, cudaMemcpyHostToDevice);

	// Create space for view parameters
	cudaMalloc((void**)&view_cuda, sizeof(sibr::Matrix4f));
	cudaMalloc((void**)&proj_cuda, sizeof(sibr::Matrix4f));
	cudaMalloc((void**)&cam_pos_cuda, 3 * sizeof(float));
	cudaMalloc((void**)&background_cuda, 3 * sizeof(float));
	cudaMemset(background_cuda, 0, 3 * sizeof(float));

	gData = new GaussianData(P,
		(float*)pos.data(),
		(float*)rot.data(),
		(float*)scale.data(),
		opacity.data(),
		(float*)shs.data());

	_gaussianRenderer = new GaussianSurfaceRenderer();

	// Create GL buffer ready for CUDA/GL interop
	glCreateBuffers(1, &imageBuffer);
	glNamedBufferStorage(imageBuffer, render_w * render_h * 3 * sizeof(float), nullptr, GL_DYNAMIC_STORAGE_BIT);
	cudaGraphicsGLRegisterBuffer(&imageBufferCuda, imageBuffer, cudaGraphicsRegisterFlagsWriteDiscard);

	geomBufferFunc = resizeFunctional(&geomPtr, allocdGeom);
	binningBufferFunc = resizeFunctional(&binningPtr, allocdBinning);
	imgBufferFunc = resizeFunctional(&imgPtr, allocdImg);
}

void sibr::GaussianView::setScene(const sibr::BasicIBRScene::Ptr & newScene)
{
	_scene = newScene;

	// Tell the scene we are a priori using all active cameras.
	std::vector<uint> imgs_ulr;
	const auto & cams = newScene->cameras()->inputCameras();
	for (size_t cid = 0; cid < cams.size(); ++cid) {
		if (cams[cid]->isActive()) {
			imgs_ulr.push_back(uint(cid));
		}
	}
	_scene->cameras()->debugFlagCameraAsUsed(imgs_ulr);
}

void sibr::GaussianView::onRenderIBR(sibr::IRenderTarget & dst, const sibr::Camera & eye)
{
	if (currMode == "Ellipsoids")
	{
		_gaussianRenderer->process(count, *gData, eye, dst, 0.2);
	}
	else if (currMode == "SfM Points")
	{
		_pointbasedrenderer->process(_scene->proxies()->proxy(), eye, dst);
	}
	else
	{
		// Convert view and projection to target coordinate system
		auto view_mat = eye.view();
		auto proj_mat = eye.viewproj();
		view_mat.row(1) *= -1;
		view_mat.row(2) *= -1;
		proj_mat.row(1) *= -1;

		// Compute additional view parameters
		float tan_fovy = tan(eye.fovy() * 0.5f);
		float tan_fovx = tan_fovy * eye.aspect();

		// Copy frame-dependent data to GPU
		cudaMemcpy(view_cuda, view_mat.data(), sizeof(sibr::Matrix4f), cudaMemcpyHostToDevice);
		cudaMemcpy(proj_cuda, proj_mat.data(), sizeof(sibr::Matrix4f), cudaMemcpyHostToDevice);
		cudaMemcpy(cam_pos_cuda, &eye.position(), sizeof(float) * 3, cudaMemcpyHostToDevice);

		// Map OpenGL buffer resource for use with CUDA
		float* image_cuda;
		size_t bytes;
		cudaGraphicsMapResources(1, &imageBufferCuda);
		cudaGraphicsResourceGetMappedPointer((void**)&image_cuda, &bytes, imageBufferCuda);

		// Rasterize
		CudaRasterizer::Rasterizer::forward(
			geomBufferFunc,
			binningBufferFunc,
			imgBufferFunc,
			count, 3, 16,
			background_cuda,
			_resolution.x(), _resolution.y(),
			pos_cuda,
			shs_cuda,
			nullptr,
			opacity_cuda,
			scale_cuda,
			_scalingModifier,
			rot_cuda,
			nullptr,
			view_cuda,
			proj_cuda,
			cam_pos_cuda,
			tan_fovx,
			tan_fovy,
			false,
			image_cuda
		);

		// Unmap OpenGL resource for use with OpenGL
		cudaGraphicsUnmapResources(1, &imageBufferCuda);
		// Copy image contents to framebuffer
		_copyRenderer->process(imageBuffer, dst, _resolution.x(), _resolution.y());
	}
}

void sibr::GaussianView::onUpdate(Input & input)
{
}

void sibr::GaussianView::onGUI()
{
	// Generate and update UI elements
	const std::string guiName = "3D Gaussians";
	if (ImGui::Begin(guiName.c_str())) 
	{
		if (ImGui::BeginCombo("Render Mode", currMode.c_str()))
		{
			if (ImGui::Selectable("Splats"))
				currMode = "Splats";
			if (ImGui::Selectable("SfM Points"))
				currMode = "SfM Points";
			if (ImGui::Selectable("Ellipsoids"))
				currMode = "Ellipsoids";
			ImGui::EndCombo();
		}
	}
	if (currMode == "Splats")
	{
		ImGui::SliderFloat("Scaling Modifier", &_scalingModifier, 0.001f, 1.0f);
	}
	ImGui::End();
}

sibr::GaussianView::~GaussianView()
{
	// Cleanup
	cudaFree(pos_cuda);
	cudaFree(rot_cuda);
	cudaFree(scale_cuda);
	cudaFree(opacity_cuda);
	cudaFree(shs_cuda);

	cudaFree(view_cuda);
	cudaFree(proj_cuda);
	cudaFree(cam_pos_cuda);
	cudaFree(background_cuda);

	cudaGraphicsUnregisterResource(imageBufferCuda);
	glDeleteBuffers(1, &imageBuffer);

	if (geomPtr)
		cudaFree(geomPtr);
	if (binningPtr)
		cudaFree(binningPtr);
	if (imgPtr)
		cudaFree(imgPtr);

	delete _copyRenderer;
}
