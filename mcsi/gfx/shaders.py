"""GLSL 3.30 shaders: 3D glass scene, particles, glass panel compositing."""

from .anims import HELPERS, MAP_ANIM, SHADE, UNIFORMS

FULLSCREEN_VS = """
#version 330 core
out vec2 vUv;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vUv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

# ------------------------------------------------------------------ 1. 3D glass scene (raymarching)
SCENE_FS = """
#version 330 core
in vec2 vUv;
out vec4 frag;
uniform vec2  uRes;
uniform float uTime;
uniform vec2  uMouse;      // -1..1
uniform vec3  uC1, uC2, uC3;
uniform float uShapeA, uShapeB, uMorph;
uniform float uEnergy;     // activity 0..1 (rises while installing)
uniform float uProgress;   // install progress 0..1
uniform float uFlash;      // success/failure flash
uniform vec3  uFlashCol;
uniform vec3  uObj;        // object center
uniform float uScale;      // object scale
uniform int   uSteps;
uniform float uSpin;       // accumulated spin angle
""" + UNIFORMS + """
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float sdSphere(vec3 p, float r) { return length(p) - r; }
float sdRoundBox(vec3 p, vec3 b, float r) {
    vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r; }
float sdTorus(vec3 p, vec2 t) { vec2 q = vec2(length(p.xy) - t.x, p.z); return length(q) - t.y; }
float sdOcta(vec3 p, float s) { p = abs(p); return (p.x + p.y + p.z - s) * 0.57735027; }
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }

float shape(vec3 p, float id) {
    if (id < 0.5) {                       // 0: droplet sphere
        float w = 0.035 * sin(p.x * 3.5 + uTime * 1.3) * sin(p.y * 4.0 + uTime * 1.1) * sin(p.z * 4.0);
        return sdSphere(p, 1.0) + w;
    }
    if (id < 1.5) return sdRoundBox(p, vec3(0.66), 0.13);           // 1: Minecraft block
    if (id < 2.5) return sdTorus(p, vec2(0.86, 0.27));              // 2: torus
    if (id < 3.5) return sdOcta(p, 1.18) - 0.05;                    // 3: gem
    // 4: twisted pillar
    float k = 1.4 * sin(uTime * 0.5);
    vec3 q = p; q.xz *= rot(q.y * k);
    return sdRoundBox(q, vec3(0.42, 0.95, 0.42), 0.12);
}

""" + HELPERS + """
float mapGlass(vec3 p) {
    if (uGlassVis < 0.02) return length(p - uObj) + 0.5;
    float sc = uScale * uGlassVis;
    vec3 q = (p - uObj) / sc;
    q.xz *= rot(uSpin + uMouse.x * 0.45);
    q.yz *= rot(0.42 + 0.22 * sin(uTime * 0.37) - uMouse.y * 0.30);
    float a = shape(q, uShapeA);
    float b = shape(q, uShapeB);
    float d = mix(a, b, smoothstep(0.0, 1.0, uMorph)) * sc;
    for (int i = 0; i < 3; i++) {          // orbiting glass beads (smooth-merged)
        float fi = float(i);
        float sp = 0.45 + 0.25 * fi + uEnergy * 1.2;
        vec3 c = uObj + sc * vec3(cos(uTime * sp + fi * 2.1) * 1.75,
                                      sin(uTime * (0.6 + 0.2 * fi) + fi) * 0.9,
                                      sin(uTime * sp + fi * 2.1) * 1.2);
        d = smin(d, sdSphere(p - c, sc * (0.17 + 0.05 * fi)), 0.32 * sc);
    }
    return d;
}
""" + MAP_ANIM + """
vec3 calcNormal(vec3 p) {
    const vec2 e = vec2(0.0015, -0.0015);
    return normalize(e.xyy * mapAll(p + e.xyy).x + e.yyx * mapAll(p + e.yyx).x +
                     e.yxy * mapAll(p + e.yxy).x + e.xxx * mapAll(p + e.xxx).x);
}

vec3 env(vec3 rd) {
    float y = rd.y * 0.5 + 0.5;
    vec3 col = mix(vec3(0.030, 0.034, 0.080), vec3(0.075, 0.090, 0.190), y);
    float t = uTime * 0.06;
    // three big colored lights in front (background) -> it glows and the glass refracts these colors
    vec3 l1 = normalize(vec3(-0.65 + 0.25 * sin(t), 0.40 + 0.15 * cos(t * 0.7), 0.75));
    vec3 l2 = normalize(vec3(0.70 + 0.2 * cos(t * 1.3), -0.15 + 0.2 * sin(t * 0.9), 0.70));
    vec3 l3 = normalize(vec3(0.05 + 0.3 * sin(t * 0.5), -0.75, 0.60));
    float d1 = max(dot(rd, l1), 0.0), d2 = max(dot(rd, l2), 0.0), d3 = max(dot(rd, l3), 0.0);
    col += uC1 * (pow(d1, 3.0) * 0.75 + pow(d1, 18.0) * 1.8);
    col += uC2 * (pow(d2, 3.0) * 0.60 + pow(d2, 22.0) * 1.5);
    col += uC3 * (pow(d3, 3.0) * 0.55 + pow(d3, 14.0) * 1.1);
    col += (uC3 * 0.10 + uC1 * 0.06) * smoothstep(0.2, -0.6, rd.z);   // keep the back hemisphere from going too dark
    // lights behind the camera (seen only in reflections)
    col += uC2 * pow(max(dot(rd, normalize(vec3(-0.5, 0.3, -0.8))), 0.0), 4.0) * 0.9;
    col += uC1 * pow(max(dot(rd, normalize(vec3(0.6, -0.4, -0.7))), 0.0), 4.0) * 0.7;
    // softbox light (bright band in reflections)
    vec3 sb = normalize(vec3(0.35, 0.85, -0.45));
    col += vec3(1.0) * smoothstep(0.975, 0.995, dot(rd, sb)) * 2.2;
    vec3 sb2 = normalize(vec3(-0.8, 0.2, 0.55));
    col += vec3(0.9, 0.95, 1.0) * smoothstep(0.985, 0.998, dot(rd, sb2)) * 1.4;
    // progress ring light (spins while installing)
    float ang = atan(rd.x, rd.y) / 6.2831853 + 0.5;
    float ring = smoothstep(0.08, 0.0, abs(rd.z + 0.88)) * step(ang, uProgress) * uEnergy;
    col += uC1 * ring * 1.6;
    col += uFlashCol * uFlash * 0.7;
    return col;
}
""" + SHADE + """
vec3 trailGlow(vec3 ro, vec3 rd) {      // the 'whoosh' light trail behind the paper plane
    if (uAnim != 2) return vec3(0.0);
    float g = 0.0;
    for (int i = 0; i < 18; i++) {
        float fi = float(i);
        float ti = uAT - fi * 0.018;
        if (ti < 0.0) break;
        vec3 c = bez(ti);
        float along = dot(c - ro, rd);
        float perp = length(c - (ro + rd * along));
        g += exp(-perp * perp * 90.0) * (1.0 - fi / 18.0) * 0.12;
    }
    return vec3(0.8, 0.95, 1.0) * g * (1.0 - seg(uAT, 0.85, 1.0));
}

vec3 render(vec3 ro, vec3 rd) {
    float t = 0.0;
    bool hit = false;
    vec2 res = vec2(1e3, 0.0);
    vec3 glow = vec3(0.0);
    for (int i = 0; i < 160; i++) {
        if (i >= uSteps) break;
        res = mapAll(ro + rd * t);
        if (res.y > 0.5) glow += emissiveGlow(res.y) * 0.004 / (0.003 + res.x * res.x * 30.0);
        if (res.x < 0.0012) { hit = true; break; }
        t += res.x * 0.9;
        if (t > 18.0) break;
    }
    glow = min(glow, vec3(2.5)) + trailGlow(ro, rd);
    vec3 bg = env(rd);
    if (!hit) return bg + glow;
    vec3 p = ro + rd * t;
    vec3 n = calcNormal(p);
    if (res.y > 0.5) {
        mapAnim(p);                       // recompute local coords (gL) for materials
        return shadeAnim(p, n, rd, res.y) + glow;
    }
    float ndv = max(dot(-rd, n), 0.0);
    float fres = 0.06 + 0.94 * pow(1.0 - ndv, 4.0);
    vec3 refl = env(reflect(rd, n));
    // refract inward -> march to the exit point (thickness)
    vec3 r = refract(rd, n, 1.0 / 1.45);
    float ti = 0.03;
    for (int j = 0; j < 40; j++) {
        float d = -mapGlass(p + r * ti);
        if (d < 0.0015) break;
        ti += max(d, 0.015);
        if (ti > 6.0) break;
    }
    vec3 pe = p + r * ti;
    vec3 ne = -calcNormal(pe);
    vec3 trans;
    for (int c = 0; c < 3; c++) {          // different IOR per RGB channel for dispersion
        float ior = 1.40 + 0.035 * float(c);
        vec3 r2 = refract(r, ne, ior);
        if (dot(r2, r2) < 0.001) r2 = reflect(r, ne);
        trans[c] = env(r2)[c];
    }
    vec3 absorb = exp(-ti * 0.35 * (vec3(1.0) - (uC1 * 0.6 + 0.35)));
    vec3 col = mix(trans * absorb, refl, fres);
    vec3 L = normalize(vec3(0.5, 0.8, -0.6));
    vec3 H = normalize(L - rd);
    col += vec3(1.0) * pow(max(dot(n, H), 0.0), 120.0) * 2.2;
    col += uC2 * pow(max(dot(n, normalize(vec3(-0.6, -0.3, -0.7) - rd)), 0.0), 40.0) * 0.8;
    col += 0.10 * fres * (0.5 + 0.5 * cos(6.2831 * (ndv * 1.8 + vec3(0.0, 0.33, 0.67))));  // thin-film iridescence
    return col + glow;
}

void main() {
    vec2 uv = (vUv * uRes - 0.5 * uRes) / uRes.y;
    vec3 ro = vec3(uMouse.x * 0.25, uMouse.y * 0.15, -5.2);
    vec3 rd = normalize(vec3(uv, 1.55));
    vec3 col = render(ro, rd);
    // soft nebula
    float neb = 0.0;
    vec2 q = uv * 2.0 + vec2(uTime * 0.01, 0.0);
    neb += 0.5 * sin(q.x * 1.7 + sin(q.y * 1.3 + uTime * 0.05));
    neb += 0.5 * sin(q.y * 2.1 + sin(q.x * 1.1 - uTime * 0.04));
    col += (uC3 * 0.035 + uC1 * 0.02) * (neb * 0.5 + 0.5);
    frag = vec4(col, 1.0);
}
"""

# ------------------------------------------------------------------ 2. Particles (procedural from gl_VertexID)
PARTICLE_VS = """
#version 330 core
uniform float uTime, uEnergy, uBurst, uDir, uPx;
uniform vec2  uRes, uMouse, uCenter;
uniform vec3  uC1, uC2;
out vec4 vCol;
float h(float n) { return fract(sin(n * 127.1 + 1.7) * 43758.5453); }
void main() {
    float id = float(gl_VertexID);
    float r1 = h(id), r2 = h(id + 11.3), r3 = h(id + 37.7), r4 = h(id + 71.1), r5 = h(id + 93.9);
    float depth = r3;                                   // 0 = far, 1 = near
    float spd = (0.015 + 0.04 * r5) * (1.0 + uEnergy * 7.0);
    float y = fract(r2 + uTime * spd * uDir) * 2.4 - 1.2;
    if (uDir < 0.0) y = -y;
    float x = (r1 * 2.0 - 1.0) * 1.15 + 0.06 * sin(uTime * (0.3 + r4) + r4 * 6.28);
    vec2 pos = vec2(x, y) + uMouse * 0.04 * (depth + 0.2);
    float alpha = 0.25 + 0.6 * depth;
    // burst from the center on success
    if (uBurst > 0.0) {
        vec2 dir = normalize(vec2(r1 - 0.5, r2 - 0.5) + 1e-4);
        float k = uBurst;
        vec2 bp = uCenter + dir * k * (0.4 + 1.6 * r5) * vec2(uRes.y / uRes.x, 1.0) * 1.6;
        float sel = step(0.35, r4);
        pos = mix(pos, bp, sel * (1.0 - k * k));
        alpha *= mix(1.0, 1.0 + 2.0 * (1.0 - k), sel);
    }
    float tw = 0.65 + 0.35 * sin(uTime * (2.0 + 3.0 * r4) + id);
    float size = (1.2 + 3.6 * depth * depth) * (1.0 + 0.6 * uEnergy);
    if (r5 > 0.965) { size *= 6.0; alpha *= 0.18; }    // blurry bokeh particles
    vCol = vec4(mix(uC1, uC2, r4) * (0.7 + 0.6 * r2), alpha * tw);
    gl_PointSize = size * uPx;
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""

PARTICLE_FS = """
#version 330 core
in vec4 vCol;
out vec4 frag;
void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.0, d);
    a = a * a;
    frag = vec4(vCol.rgb * a * vCol.a, 0.0);
}
"""

# ------------------------------------------------------------------ 3. Glass panel compositing
COMPOSITE_FS = """
#version 330 core
in vec2 vUv;
out vec4 frag;
uniform sampler2D uScene;
uniform vec2  uRes;          // screen pixels
uniform vec2  uSceneRes;     // scene texture pixels
uniform int   uN;
uniform vec4  uRect[16];     // x, y (from bottom), w, h  (pixels)
uniform float uRad[16];
uniform float uTime;
uniform vec2  uMouse;
uniform vec3  uC1;
uniform float uBlur;         // blur amount (mip level)
uniform float uReveal;       // clear the glass during animations 0..1

float sdRR(vec2 p, vec4 r, float rad) {
    vec2 c = r.xy + r.zw * 0.5;
    vec2 q = abs(p - c) - r.zw * 0.5 + rad;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - rad;
}
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

vec3 blurAt(vec2 px, float lod) {
    vec3 acc = vec3(0.0);
    float rad = 1.1 * exp2(lod) * (uRes.x / uSceneRes.x);
    float a0 = hash(px) * 6.2831;
    for (int i = 0; i < 8; i++) {
        float a = a0 + float(i) * 0.785398;
        vec2 o = vec2(cos(a), sin(a)) * rad * (0.6 + 0.4 * float(i & 1));
        acc += textureLod(uScene, (px + o) / uRes, lod).rgb;
    }
    return acc / 8.0;
}

void main() {
    vec2 px = gl_FragCoord.xy;
    vec3 base = texture(uScene, vUv).rgb;
    int inside = 0;
    float dEdge = -1e9;
    int k = -1;
    float shadow = 0.0;
    for (int i = 0; i < 16; i++) {
        if (i >= uN) break;
        float d = sdRR(px, uRect[i], uRad[i]);
        if (d < 0.0) {
            inside++;
            if (d > dEdge) { dEdge = d; k = i; }
        } else {
            float ds = sdRR(px + vec2(0.0, 7.0), uRect[i], uRad[i]);   // drop shadow
            shadow = max(shadow, exp(-max(ds, 0.0) / 16.0) * 0.45);
        }
    }
    vec3 col;
    if (inside == 0) {
        col = base * (1.0 - shadow);
    } else {
        // edge slope -> lens-like refracting rim
        vec2 e = vec2(1.0, 0.0);
        vec2 g = vec2(sdRR(px + e.xy, uRect[k], uRad[k]) - sdRR(px - e.xy, uRect[k], uRad[k]),
                      sdRR(px + e.yx, uRect[k], uRad[k]) - sdRR(px - e.yx, uRect[k], uRad[k]));
        g = normalize(g + 1e-5);
        float bevel = 22.0;
        float t = clamp(-dEdge / bevel, 0.0, 1.0);
        float edge = 1.0 - t;
        float lens = edge * edge;
        vec2 off = -g * lens * 26.0;
        off += vec2(sin(px.y * 0.012 + uTime * 0.6), cos(px.x * 0.010 + uTime * 0.5)) * 1.2;
        float lod = (uBlur + float(inside - 1) * 0.35) * (1.0 - 0.8 * uReveal);
        // chromatic aberration: sample RGB at slightly different offsets
        vec3 c;
        c.r = blurAt(px + off * 1.06, lod).r;
        c.g = blurAt(px + off, lod).g;
        c.b = blurAt(px + off * 0.94, lod).b;
        c = mix(c, vec3(0.025, 0.032, 0.075), (0.46 + 0.10 * float(inside - 1)) * (0.55 + 0.45 * t) * (1.0 - 0.55 * uReveal));
        c += vec3(0.020, 0.024, 0.040) * float(inside);
        // rim light: light from the mouse side hits the top/left edge
        vec2 L = normalize(vec2(-0.45, 0.85) + vec2(-uMouse.x, uMouse.y) * 0.35);
        float rim = pow(max(dot(g, L), 0.0), 3.0) * pow(edge, 7.0);
        c += vec3(1.0) * rim * 0.55;
        c += uC1 * pow(max(dot(g, -L), 0.0), 3.0) * pow(edge, 9.0) * 0.35;
        // thin inner highlight
        c += vec3(1.0) * smoothstep(1.6, 0.0, abs(dEdge + 1.2)) * 0.10;
        // slowly sweeping sheen band
        float band = (px.x + px.y * 0.6) / uRes.x - fract(uTime * 0.035) * 2.4 + 0.6;
        c += vec3(1.0) * smoothstep(0.06, 0.0, abs(band)) * 0.035;
        col = c;
    }
    vec2 v = vUv - 0.5;
    col *= 1.0 - dot(v, v) * 0.55;                                  // vignette
    col += (hash(px + fract(uTime) * 91.0) - 0.5) * 0.012;          // film grain
    col = col / (1.0 + col * 0.25);                                 // tone mapping
    frag = vec4(pow(max(col, 0.0), vec3(0.95)), 1.0);
}
"""
