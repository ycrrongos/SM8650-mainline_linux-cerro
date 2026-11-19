// Qt port of the drop and update shaders in sirxemic/jquery.ripples (MIT).
#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 dropCenter;
    float dropStrength;
    vec2 delta;
};
layout(binding = 1) uniform sampler2D stateTexture;

void main() {
    vec2 coord = qt_TexCoord0;
    vec4 info = texture(stateTexture, coord);
    vec2 dx = vec2(delta.x, 0.0);
    vec2 dy = vec2(0.0, delta.y);
    float average = (texture(stateTexture, coord - dx).r
                   + texture(stateTexture, coord - dy).r
                   + texture(stateTexture, coord + dx).r
                   + texture(stateTexture, coord + dy).r) * 0.25;
    info.g += (average - info.r) * 2.0;
    info.g *= 0.985;
    info.r += info.g;

    // Keep the drop round on a landscape render target.
    float drop = max(0.0, 1.0 - length((dropCenter - coord) * vec2(delta.y / delta.x, 1.0)) / 0.038);
    drop = 0.5 - cos(drop * 3.141592653589793) * 0.5;
    info.r += drop * dropStrength;
    fragColor = vec4(info.rg, 0.0, 1.0);
}
