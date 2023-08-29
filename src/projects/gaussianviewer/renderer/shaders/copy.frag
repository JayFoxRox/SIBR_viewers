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

#version 450

layout(location = 0) out vec4 out_color;

#ifdef SSBO

layout(std430, binding = 0) buffer colorLayout
{
    float data[];
} source;

#else 

layout(binding = 0) uniform sampler2D source_data; // colorLayout; 

#endif

uniform bool flip = false;
uniform int width = 1000;
uniform int height = 800;

in vec4 texcoord;

void main(void)
{
	int x = int(texcoord.x * width);
	int y;
	
	if(flip)
		y = height - 1 - int(texcoord.y * height);
	else
		y = int(texcoord.y * height);
	
	// `source.data[x]` has become `source_data(x)`
#ifdef SSBO
	float r = source.data[0 * width * height + (y * width + x)];
	float g = source.data[1 * width * height + (y * width + x)];
	float b = source.data[2 * width * height + (y * width + x)];
    vec4 color   = vec4(r, g, b, 1);
#else
	vec3 rgb = texelFetch(source_data, ivec2(x, y), 0).rgb;
	vec4 color   = vec4(rgb, 1);
#endif
    out_color    = color;
}
