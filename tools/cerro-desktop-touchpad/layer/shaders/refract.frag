// Qt port of the background render shader in sirxemic/jquery.ripples (MIT).
#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 delta;
};
layout(binding = 1) uniform sampler2D wallpaper;
layout(binding = 2) uniform sampler2D water;

void main() {
    vec2 uv = qt_TexCoord0;
    float h = texture(water, uv).r;
    float hx = texture(water, uv + vec2(delta.x, 0.0)).r;
    float hy = texture(water, uv + vec2(0.0, delta.y)).r;
    vec3 dx = vec3(delta.x, hx - h, 0.0);
    vec3 dy = vec3(0.0, hy - h, delta.y);
    vec2 offset = -normalize(cross(dy, dx)).xz;
    float specular = pow(max(0.0, dot(offset, normalize(vec2(-0.6, 1.0)))), 4.0);
    vec3 background = texture(wallpaper, clamp(uv + offset * 0.038, 0.0, 1.0)).rgb;
    fragColor = vec4(background + specular * 0.15, 1.0) * qt_Opacity;
}
