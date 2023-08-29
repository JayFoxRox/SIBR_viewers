/*
 * Copyright (C) 2023, Inria
 * GRAPHDECO research group, https://team.inria.fr/graphdeco
 * All rights reserved.
 *
 * This software is free for non-commercial, research and evaluation use 
 * under the terms of the LICENSE.md file.
 *
 * For inquiries contact sibr@inria.fr and/or George.Drettakis@inria.fr
 */



#include "core/graphics/Texture.hpp"
#include "GaussianSurfaceRenderer.hpp"

namespace sibr { 

	GaussianData::GaussianData(int num_gaussians, float* mean_data, float* rot_data, float* scale_data, float* alpha_data, float* color_data)
	{
		_num_gaussians = num_gaussians;
		auto upload = [](GLuint& buffer, int n, int components, float* data) {
#ifdef SSBO
			glCreateBuffers(1, &buffer);
			glNamedBufferStorage(buffer, num_gaussians * components * sizeof(float), data, 0);
#else
			GLenum type = GL_FLOAT;
			GLenum internalformat;
			GLenum format;
			if (components == 1) {
				format = GL_RED;
				internalformat = GL_R32F;
			} else if (components == 2) {
				format = GL_RG;
				internalformat = GL_RG32F;
			} else if (components == 3) {
				format = GL_RGB;
				internalformat = GL_RGB32F;
			} else if (components == 4) {
				format = GL_RGBA;
				internalformat = GL_RGBA32F;
			} else {
				assert(false);
			}

			#define WIDTH 4096
			
			int full_rows = n / WIDTH;
			int remaining_cols = n % WIDTH;

			int total_cols = std::min(n, WIDTH);
			int total_rows = full_rows + (int)(remaining_cols > 0);

			printf("Uploading as %dx%d texture (%d components)\n", total_cols, total_rows, components);

			glGenTextures(1, &buffer);
			glBindTexture(GL_TEXTURE_2D, buffer);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
			CHECK_GL_ERROR;

			glTexImage2D(GL_TEXTURE_2D, 0, internalformat, total_cols, total_rows, 0, format, type, nullptr);
			CHECK_GL_ERROR;


			// Fill the full rows, then the reminder for the last row
			//								  X,	     Y,          Width,    Height,
			glTexSubImage2D(GL_TEXTURE_2D, 0, 0,         0,     total_cols, full_rows, format, type, data);
			glTexSubImage2D(GL_TEXTURE_2D, 0, 0, full_rows, remaining_cols,         1, format, type, data);
#endif
			CHECK_GL_ERROR;
		};

		upload(meanBuffer, num_gaussians, 3, mean_data);
		upload(rotBuffer, num_gaussians, 4, rot_data);
		upload(scaleBuffer, num_gaussians, 3, scale_data);
		upload(alphaBuffer, num_gaussians, 1, alpha_data);
		upload(colorBuffer, num_gaussians * (48 / 4), 4, color_data); // actually 3 components and stride of 48
	}

	void GaussianData::render(int G) const
	{
		auto setBuffer = [](int binding, GLuint buffer) {
#ifdef SSBO
			glBindBufferBase(GL_SHADER_STORAGE_BUFFER, binding, buffer);
#else
			glActiveTexture(GL_TEXTURE0 + binding);
			glBindTexture(GL_TEXTURE_2D, buffer);
#endif
			CHECK_GL_ERROR;
		};

		setBuffer(0, meanBuffer);
		setBuffer(1, rotBuffer);
		setBuffer(2, scaleBuffer);
		setBuffer(3, alphaBuffer);
		setBuffer(4, colorBuffer);

		static GLuint vao = 0;
		if (vao == 0) {
			glGenVertexArrays(1, &vao);
		}
		glBindVertexArray(vao);

		glDrawArraysInstanced(GL_TRIANGLES, 0, 36, G);

		CHECK_GL_ERROR;
	}

	GaussianSurfaceRenderer::GaussianSurfaceRenderer( void )
	{
		_shader.init("GaussianSurface",
			sibr::loadFile(sibr::getShadersDirectory("gaussian") + "/gaussian_surface.vert"),
			sibr::loadFile(sibr::getShadersDirectory("gaussian") + "/gaussian_surface.frag"));

		_paramCamPos.init(_shader, "rayOrigin");
		_paramMVP.init(_shader,"MVP");
		_paramLimit.init(_shader, "alpha_limit");
		_paramStage.init(_shader, "stage");

		glGenTextures(1, &idTexture);
		glBindTexture(GL_TEXTURE_2D, idTexture);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
		glGenTextures(1, &colorTexture);
		glBindTexture(GL_TEXTURE_2D, colorTexture);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
		glGenFramebuffers(1, &fbo);
		glGenRenderbuffers(1, &depthBuffer);

		CHECK_GL_ERROR;

		makeFBO(800, 800);
	}

	void GaussianSurfaceRenderer::makeFBO(int w, int h)
	{
		resX = w;
		resY = h;

		glBindTexture(GL_TEXTURE_2D, idTexture);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, resX, resY, 0, GL_RED_INTEGER, GL_UNSIGNED_INT, 0);

		glBindTexture(GL_TEXTURE_2D, colorTexture);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, resX, resY, 0, GL_RGBA, GL_UNSIGNED_BYTE, 0);
		glBindTexture(GL_TEXTURE_2D, 0);

		glBindRenderbuffer(GL_RENDERBUFFER, depthBuffer);
		glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, resX, resY);

		glBindFramebuffer(GL_FRAMEBUFFER, fbo);
		glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, colorTexture, 0);
		glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, idTexture, 0);
		glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depthBuffer);

		GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
		assert(status == GL_FRAMEBUFFER_COMPLETE);

		CHECK_GL_ERROR;
	}

	int	GaussianSurfaceRenderer::process(int G, const GaussianData& mesh, const Camera& eye, IRenderTarget& target, float limit, sibr::Mesh::RenderMode mode, bool backFaceCulling)
	{
		glBindFramebuffer(GL_FRAMEBUFFER, fbo);

		glClear(GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT);

		if (target.w() != resX || target.h() != resY)
		{
			makeFBO(target.w(), target.h());
		}

		// Solid pass
		GLuint drawBuffers[2];
		drawBuffers[0] = GL_COLOR_ATTACHMENT0;
		drawBuffers[1] = GL_COLOR_ATTACHMENT1;
		glDrawBuffers(2, drawBuffers);

		glEnable(GL_DEPTH_TEST);
		glDisable(GL_BLEND);
		_shader.begin();
		_paramMVP.set(eye.viewproj());
		_paramCamPos.set(eye.position());
		_paramLimit.set(limit);
		_paramStage.set(0);
		mesh.render(G);

		// Simple additive blendnig (no order)
		glDrawBuffers(1, drawBuffers);
		glDepthMask(GL_FALSE);
		glEnable(GL_BLEND);
		glBlendEquation(GL_FUNC_ADD);
		glBlendFunc(GL_SRC_ALPHA, GL_ONE);
		_paramStage.set(1);
		mesh.render(G);

		glDepthMask(GL_TRUE);
		glDisable(GL_BLEND);

		_shader.end();

		glReadBuffer(GL_COLOR_ATTACHMENT0);
		glBlitNamedFramebuffer(
			fbo, target.fbo(),
			0, 0, resX, resY,
			0, 0, resX, resY,
			GL_COLOR_BUFFER_BIT, GL_NEAREST);

		CHECK_GL_ERROR;

		return 0;
	}

} /*namespace sibr*/ 
