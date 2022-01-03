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


#version 420

layout(location = 0) out vec4 out_color;
layout(location = 1) out vec4 out_normal;
layout(location = 2) out vec4 out_normalC;

in vec3 vertex_coord;
in vec3 vertex_normal;
in vec3 vertex_normal_cam;

void main(void) {
	out_color = vec4(vertex_coord, gl_FragCoord.z);
    out_normal = vec4(vertex_normal, 1.0);
    out_normalC = vec4(vertex_normal_cam, 1.0);
}
