# Water ripple shaders

The drop, height/velocity update and background refraction are adapted from
[Sirxemic's jquery.ripples](https://github.com/sirxemic/jquery.ripples/blob/e90bd54ee5d2b23d04a208ad1248456c42abb289/src/main.js#L613).
See LICENSE.txt for the upstream MIT terms.

Compile with the Qt Shader Tools version used by Quickshell. On Fedora,
the compiler is /usr/lib64/qt6/bin/qsb:

    for shader in update.frag refract.frag; do
        qsb --glsl "300 es,330" -o "$shader.qsb" "$shader"
    done

Quickshell starts the 144×64 half-float height field on a touch sample,
updates it at roughly 30 Hz while active, and releases it 1.25 seconds
after the last sample. During idle it uses only the cached background.
