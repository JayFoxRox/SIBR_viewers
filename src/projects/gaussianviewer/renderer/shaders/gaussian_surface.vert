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


#version 430

uniform mat4 MVP;
uniform float alpha_limit;
uniform int stage;

#ifdef SSBO
layout (std430, binding = 0) buffer BoxCenters {
    float centers[];
};
layout (std430, binding = 1) buffer Rotations {
    vec4 rots[];
};
layout (std430, binding = 2) buffer Scales {
    float scales[];
};
layout (std430, binding = 3) buffer Alphas {
    float alphas[];
};
layout (std430, binding = 4) buffer Colors {
    float colors[];
};

vec3 center(int boxID) { return vec3(centers[3 * boxID + 0], centers[3 * boxID + 1], centers[3 * boxID + 2]) }
vec4 rot(int boxID) { return rots(boxID); }
vec3 scale(int boxID) { return vec3(scales[3 * boxID + 0], scales[3 * boxID + 1], scales[3 * boxID + 2]); }
float alpha(int boxID) { return alphas[boxID]; }
vec3 color(int boxID) { return vec3(colors[boxID * 48 + 0], colors[boxID * 48 + 1], colors[boxID * 48 + 2]); }

#else

layout (binding = 0) uniform sampler2D centers;
layout (binding = 1) uniform sampler2D rots;
layout (binding = 2) uniform sampler2D scales;
layout (binding = 3) uniform sampler2D alphas;
layout (binding = 4) uniform sampler2D colors;

#define COORD2(boxID) ivec2(boxID % 4096, boxID / 4096)

vec3 center(int boxID) { return texelFetch(centers, COORD2(boxID), 0).rgb; }
vec4 rot(int boxID) { return texelFetch(rots, COORD2(boxID), 0).rgba; }
vec3 scale(int boxID) { return texelFetch(scales, COORD2(boxID), 0).rgb; }
float alpha(int boxID) { return texelFetch(alphas, COORD2(boxID), 0).r; }
vec3 color(int boxID) { return texelFetch(colors, COORD2(boxID), 0).rgb; }

#endif

mat3 quatToMat3(vec4 q) {
  float qx = q.y;
  float qy = q.z;
  float qz = q.w;
  float qw = q.x;

  float qxx = qx * qx;
  float qyy = qy * qy;
  float qzz = qz * qz;
  float qxz = qx * qz;
  float qxy = qx * qy;
  float qyw = qy * qw;
  float qzw = qz * qw;
  float qyz = qy * qz;
  float qxw = qx * qw;

  return mat3(
    vec3(1.0 - 2.0 * (qyy + qzz), 2.0 * (qxy - qzw), 2.0 * (qxz + qyw)),
    vec3(2.0 * (qxy + qzw), 1.0 - 2.0 * (qxx + qzz), 2.0 * (qyz - qxw)),
    vec3(2.0 * (qxz - qyw), 2.0 * (qyz + qxw), 1.0 - 2.0 * (qxx + qyy))
  );
}

const vec3 boxVertices[8] = vec3[8](
    vec3(-1, -1, -1),
    vec3(-1, -1,  1),
    vec3(-1,  1, -1),
    vec3(-1,  1,  1),
    vec3( 1, -1, -1),
    vec3( 1, -1,  1),
    vec3( 1,  1, -1),
    vec3( 1,  1,  1)
);

const int boxIndices[36] = int[36](
    0, 1, 2, 1, 3, 2,
    4, 6, 5, 5, 6, 7,
    0, 2, 4, 4, 2, 6,
    1, 5, 3, 5, 7, 3,
    0, 4, 1, 4, 5, 1,
    2, 3, 6, 3, 7, 6
);

out vec3 worldPos;
out vec3 ellipsoidCenter;
out vec3 ellipsoidScale;
out mat3 ellipsoidRotation;
out vec3 colorVert;
out float alphaVert;
flat out int boxID;

void main() {
	boxID = gl_InstanceID;
    ellipsoidCenter = center(boxID);
    float a = alpha(boxID);
	alphaVert = a;
	ellipsoidScale = scale(boxID);
	ellipsoidScale = 2 * ellipsoidScale;

	vec4 q = rot(boxID);
	ellipsoidRotation = transpose(quatToMat3(q));

    int vertexIndex = boxIndices[gl_VertexID];
    worldPos = ellipsoidRotation * (ellipsoidScale * boxVertices[vertexIndex]);
    worldPos += ellipsoidCenter;

	colorVert = color(boxID) * 0.2 + 0.5;
	
	if((stage == 0 && a < alpha_limit) || (stage == 1 && a >= alpha_limit))
	 	gl_Position = vec4(0,0,0,0);
	else
    	gl_Position = MVP * vec4(worldPos, 1);
}