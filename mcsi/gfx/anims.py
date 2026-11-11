"""Signature animations played when a server type is picked (GLSL snippet), spliced into shaders.SCENE_FS."""

# server type -> animation id, duration (s), particle burst time and position (relative to the animation center)
ANIM_ID = {"vanilla": 1, "paper": 2, "purpur": 3, "folia": 4, "spigot": 5, "bukkit": 6, "fabric": 7,
           "quilt": 8, "babric": 9, "forge": 10, "neoforge": 11, "mohist": 12, "youer": 13, "arclight": 14,
           "banner": 15, "legacyfabric": 7}
ANIM_DUR = {"paper": 2.1}
DEFAULT_DUR = 2.7
ANIM_BURST = {
    "vanilla": (0.42, (0.0, -0.55, 0.0)),
    "forge": (0.42, (0.15, -0.2, 0.0)),
    "neoforge": (0.42, (0.15, -0.2, 0.0)),
    "mohist": (0.84, (0.0, 0.0, 0.0)),
    "youer": (0.84, (0.0, 0.0, 0.0)),
    "arclight": (0.82, (0.0, 0.0, 0.0)),
    "quilt": (0.52, (0.0, 0.0, 0.0)),
    "babric": (0.56, (0.0, 0.0, 0.0)),
    "purpur": (0.75, (0.0, 0.3, 0.0)),
}
ANIM_CENTER = (0.95, 0.0, 0.0)
ANIM_SCALE = 0.82
ANIM_BURST = {k: (t, tuple(c * ANIM_SCALE for c in off)) for k, (t, off) in ANIM_BURST.items()}

UNIFORMS = """
uniform int   uAnim;       // 0 = none
uniform float uAT;         // 0..1 progress
uniform float uGlassVis;   // visibility of the default glass object 0..1
uniform vec3  uAC;         // animation center
"""

HELPERS = """
vec3 gL = vec3(0.0);   // local coords of the closest part (for materials)
float gK = 0.0;
float gCloth = 0.0;    // 1 for cloth (soft sheen instead of gloss)

float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h) - r; }
float sdEllipsoid(vec3 p, vec3 r) { float k0 = length(p / r); float k1 = length(p / (r * r)); return k0 * (k0 - 1.0) / max(k1, 1e-4); }
float dot2(vec3 v) { return dot(v, v); }
float udTri(vec3 p, vec3 a, vec3 b, vec3 c) {
    vec3 ba = b - a, pa = p - a, cb = c - b, pb = p - b, ac = a - c, pc = p - c;
    vec3 nor = cross(ba, ac);
    return sqrt((sign(dot(cross(ba, nor), pa)) + sign(dot(cross(cb, nor), pb)) + sign(dot(cross(ac, nor), pc)) < 2.0)
        ? min(min(dot2(ba * clamp(dot(ba, pa) / dot2(ba), 0.0, 1.0) - pa),
                  dot2(cb * clamp(dot(cb, pb) / dot2(cb), 0.0, 1.0) - pb)),
                  dot2(ac * clamp(dot(ac, pc) / dot2(ac), 0.0, 1.0) - pc))
        : dot(nor, pa) * dot(nor, pa) / dot2(nor));
}
float seg(float t, float a, float b) { return clamp((t - a) / (b - a), 0.0, 1.0); }
float easeOut(float x) { x = clamp(x, 0.0, 1.0); return 1.0 - (1.0 - x) * (1.0 - x) * (1.0 - x); }
float easeOutBack(float x) { x = clamp(x, 0.0, 1.0); float c1 = 1.70158, c3 = c1 + 1.0;
    return 1.0 + c3 * pow(x - 1.0, 3.0) + c1 * pow(x - 1.0, 2.0); }
float h1(float a, float b) { return fract(sin(a * 127.1 + b * 311.7) * 43758.5453); }

vec3 bez(float t) {   // paper plane flight path
    vec3 a = vec3(-4.4, -2.2, 1.2), b = vec3(-1.4, -1.8, -0.6), c = vec3(1.4, 1.0, 0.0), d = vec3(4.8, 2.8, 1.6);
    float u = 1.0 - t;
    return u * u * u * a + 3.0 * u * u * t * b + 3.0 * u * t * t * c + t * t * t * d;
}
"""

MAP_ANIM = """
vec2 mapAnimLocal(vec3 q);
vec2 mapAnim(vec3 p) {
    float t = uAT;
    vec3 q = p - uAC;
    vec2 r = vec2(1e3, 0.0);
    if (uAnim == 2) {                                   // Paper: paper plane
        vec3 pos = bez(t);
        vec3 fwd = normalize(bez(min(t + 0.01, 1.0)) - bez(max(t - 0.01, 0.0)));
        vec3 rgt = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
        vec3 up = cross(fwd, rgt);
        float roll = sin(t * 7.0) * 0.55;
        vec3 rg2 = rgt * cos(roll) + up * sin(roll);
        vec3 up2 = up * cos(roll) - rgt * sin(roll);
        vec3 w = p - pos;
        float bnd = length(w) - 1.2;
        if (bnd > 0.4) return vec2(bnd, 0.0);
        vec3 l = vec3(dot(w, fwd), dot(w, up2), dot(w, rg2)) * 1.1;
        vec3 N = vec3(0.95, 0.0, 0.0), C = vec3(-0.6, 0.0, 0.0);
        vec3 L = vec3(-0.6, 0.12, -0.62), R = vec3(-0.6, 0.12, 0.62), K = vec3(-0.6, -0.24, 0.0);
        float d = min(min(udTri(l, N, C, L), udTri(l, N, C, R)), udTri(l, N, C, K)) - 0.012;
        gL = l;
        return vec2(d / 1.1, 2.0);
    }
    const float AS = 0.82;                             // animation scale
    vec2 rr = mapAnimLocal(q / AS);
    return vec2(rr.x * AS, rr.y);
}

vec2 mapAnimLocal(vec3 q) {
    float t = uAT;
    vec2 r = vec2(1e3, 0.0);
    float bnd = length(q) - 3.2;
    if (bnd > 0.6) return vec2(bnd, 0.0);

    if (uAnim == 1) {                                   // Vanilla: grass block drops and bounces
        float drop = seg(t, 0.0, 0.42);
        float y = 3.4 * (1.0 - drop * drop);
        float bt = seg(t, 0.42, 0.9);
        y += abs(sin(bt * 9.42)) * 0.45 * (1.0 - bt);
        float s = 1.0 - seg(t, 0.88, 1.0);
        if (s < 0.01) return r;
        vec3 l = q - vec3(0.0, y - 0.15, 0.0);
        l.xz *= rot(t * 5.0 + 0.6);
        l.yz *= rot(0.3);
        l /= s;
        gL = l;
        r = vec2((sdBox(l, vec3(0.52)) - 0.03) * s, 1.0);
    } else if (uAnim == 3) {                            // Purpur: three blocks rise and stack
        float sh = 1.0 - seg(t, 0.9, 1.0);
        if (sh < 0.01) return r;
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            float k = easeOutBack(seg(t, 0.04 + fi * 0.16, 0.42 + fi * 0.16));
            vec3 l = q - vec3(0.0, mix(-3.8, -0.95 + fi * 0.64, k), 0.0);
            l.xz *= rot((1.0 - k) * 4.0 + 0.6);
            l.yz *= rot(0.22);
            float d = (sdBox(l / sh, vec3(0.3)) - 0.015) * sh;
            if (d < r.x) { r = vec2(d, 3.0); gL = l / sh; gK = fi; }
        }
    } else if (uAnim == 4) {                            // Folia: leaves swirl in a whirlwind
        for (int i = 0; i < 7; i++) {
            float fi = float(i);
            float k = seg(t, fi * 0.04, 0.78 + fi * 0.03);
            float sh = smoothstep(0.0, 0.1, k) * (1.0 - seg(t, 0.9, 1.0));
            if (sh < 0.01) continue;
            float a = fi * 0.9 + k * 5.0;
            float rr = 0.25 + k * 1.7;
            vec3 c = vec3(cos(a) * rr, 1.3 - k * 2.6 + sin(k * 9.0 + fi) * 0.18, sin(a) * rr * 0.6);
            vec3 l = q - c;
            l.xz *= rot(a + k * 3.0);
            l.xy *= rot(0.6 * sin(k * 8.0 + fi));
            float d = sdEllipsoid(l / sh, vec3(0.34, 0.025, 0.17)) * sh;
            if (d < r.x) { r = vec2(d, 4.0); gL = l / sh; }
        }
    } else if (uAnim == 5) {                            // Spigot: water stream from a tap
        float pop = easeOutBack(seg(t, 0.0, 0.18)) * (1.0 - seg(t, 0.9, 1.0));
        if (pop < 0.01) return r;
        vec3 l = (q - vec3(0.0, -0.05, 0.0)) / pop;
        float pipe = sdCapsule(l, vec3(-1.3, 1.0, 0.0), vec3(0.0, 1.0, 0.0), 0.13);
        float spout = sdCapsule(l, vec3(0.0, 1.0, 0.0), vec3(0.0, 0.72, 0.0), 0.11);
        vec3 hl = l - vec3(-0.35, 1.25, 0.0);
        hl.xz *= rot(seg(t, 0.08, 0.24) * 1.57);
        float handle = min(sdBox(hl, vec3(0.26, 0.03, 0.04)) - 0.02,
                           sdCapsule(l, vec3(-0.35, 1.0, 0.0), vec3(-0.35, 1.25, 0.0), 0.04));
        r = vec2(min(min(pipe, spout), handle) * pop, 5.0);
        float w0 = seg(t, 0.2, 0.4), w1 = seg(t, 0.75, 0.9);
        if (w0 > 0.0 && w1 < 1.0) {
            float wob = 0.012 * sin(l.y * 18.0 - uTime * 25.0);
            float ws = sdCapsule(l, vec3(0.0, mix(0.7, -1.3, w1), 0.0), vec3(0.0, mix(0.7, -1.3, w0), 0.0), 0.055 + wob);
            if (ws * pop < r.x) r = vec2(ws * pop, 6.0);
        }
        float sp = seg(t, 0.4, 0.92);
        if (sp > 0.0 && sp < 1.0) {
            vec3 sl = l - vec3(0.0, -1.3, 0.0);
            float ring = length(vec2(length(sl.xz) - sp * 1.0, sl.y)) - 0.035 * (1.0 - sp);
            if (ring * pop < r.x) r = vec2(ring * pop, 6.0);
        }
        gL = l;
    } else if (uAnim == 6) {                            // CraftBukkit: lava poured into a bucket
        float pop = easeOutBack(seg(t, 0.0, 0.15)) * (1.0 - seg(t, 0.92, 1.0));
        if (pop < 0.01) return r;
        vec3 l = (q - vec3(0.0, -0.2, 0.0)) / pop;
        vec3 bq = l - vec3(0.0, -0.85, 0.0);
        bq.yz *= rot(0.5);
        float rad = 0.47 + 0.08 * clamp((bq.y + 0.42) / 0.84, 0.0, 1.0);
        float outer = max(length(bq.xz) - rad, abs(bq.y) - 0.42);
        float inner = max(length(bq.xz) - (rad - 0.05), -(bq.y + 0.36));
        float shell = max(outer, -inner) * 0.9;
        vec3 hq = bq - vec3(0.0, 0.42, 0.0);
        float handle = max(length(vec2(length(hq.xy) - 0.56, hq.z)) - 0.025, -hq.y);
        r = vec2(min(shell, handle) * pop, 9.0);
        float fill = seg(t, 0.28, 0.85);
        float level = mix(-0.36, 0.30, fill);
        if (fill > 0.0) {
            float lava = max(length(bq.xz) - (rad - 0.06), max(bq.y - level, -bq.y - 0.36));
            if (lava * pop < r.x) r = vec2(lava * pop, 7.0);
        }
        float bsz = 0.34 * (1.0 - seg(t, 0.2, 0.85) * 0.85);
        vec3 sb = l - vec3(0.0, 1.45, 0.0);
        sb.xz *= rot(uTime * 0.6);
        float src = sdBox(sb, vec3(bsz)) - 0.03;
        if (src * pop < r.x) r = vec2(src * pop, 7.0);
        float s0 = seg(t, 0.12, 0.3), s1 = seg(t, 0.78, 0.92);
        float topY = 1.45 - bsz, botY = -0.85 + level * 0.9;
        if (s0 > 0.0 && s1 < 1.0) {
            float wob = 0.015 * sin(l.y * 14.0 - uTime * 18.0);
            float st = sdCapsule(l, vec3(0.0, mix(topY, botY, s1), 0.0), vec3(0.0, mix(topY, botY, s0), 0.0), 0.075 + wob);
            if (st * pop < r.x) r = vec2(st * pop, 7.0);
        }
        gL = l;
    } else if (uAnim == 7) {                            // Fabric: cloth flutters in
        float inx = easeOut(seg(t, 0.0, 0.4)), outx = seg(t, 0.8, 1.0);
        vec3 l = q - vec3(mix(-4.2, 0.0, inx) + outx * outx * 5.0, 0.1 + outx * 1.5, 0.0);
        l.xy *= rot(0.15 - outx * 0.6);
        float b2 = length(l) - 1.6;
        if (b2 > 0.6) return vec2(b2, 0.0);
        vec3 w = l;
        w.z -= 0.2 * sin(l.x * 3.2 - uTime * 7.0) * (l.x + 1.1) * 0.5 + 0.08 * sin(l.y * 4.5 + uTime * 5.0);
        gL = w;
        r = vec2((sdBox(w, vec3(1.05, 0.68, 0.012)) - 0.004) * 0.55, 8.0);
    } else if (uAnim == 8) {                            // Quilt: patches gather into a quilt
        float o = seg(t, 0.86, 1.0);
        for (int i = 0; i < 9; i++) {
            float fi = float(i);
            vec3 tgt = vec3(mod(fi, 3.0) - 1.0, floor(fi / 3.0) - 1.0, 0.0) * 0.47;
            vec3 dir = normalize(vec3(h1(fi, 1.0) - 0.5, h1(fi, 2.0) - 0.5, h1(fi, 3.0) * 0.5) + 1e-3);
            float k = easeOutBack(seg(t, fi * 0.035, 0.42 + fi * 0.035));
            vec3 c = mix(dir * 4.5, tgt, k) + vec3(0.0, -o * o * 4.0, 0.0);
            vec3 l = q - c;
            l.xy *= rot((1.0 - k) * 5.0 + fi);
            l.yz *= rot(0.25 * (1.0 - k) + 0.2);
            float d = sdBox(l, vec3(0.215, 0.215, 0.03)) - 0.012;
            if (d < r.x) { r = vec2(d, 20.0 + fi); gL = l; }
        }
    } else if (uAnim == 9) {                            // Babric: small cubes assemble into a block
        float o = 1.0 - seg(t, 0.88, 1.0);
        if (o < 0.01) return r;
        vec3 qq = q;
        qq.xz *= rot(t * 1.6);
        qq.yz *= rot(0.3);
        for (int i = 0; i < 8; i++) {
            float fi = float(i);
            vec3 tgt = (vec3(mod(fi, 2.0), mod(floor(fi / 2.0), 2.0), floor(fi / 4.0)) - 0.5) * 0.54;
            vec3 dir = normalize(vec3(h1(fi, 7.0) - 0.5, h1(fi, 8.0) - 0.5, h1(fi, 9.0) - 0.5) + 1e-3);
            float k = easeOutBack(seg(t, fi * 0.05, 0.45 + fi * 0.05));
            vec3 l = qq - mix(dir * 3.5, tgt, k);
            l.xz *= rot((1.0 - k) * 6.0);
            l.xy *= rot((1.0 - k) * 4.0);
            float d = (sdBox(l / o, vec3(0.26)) - 0.01) * o;
            if (d < r.x) { r = vec2(d, 10.0); gL = l / o + tgt; }
        }
        // once assembled, a Fabric cloth band wraps the block
        float band = seg(t, 0.55, 0.72) * o;
        if (band > 0.01) {
            vec3 bl = qq;
            float strip = sdBox(bl, vec3(0.565, 0.075, 0.565)) - 0.006;
            strip = max(strip, -sdBox(bl, vec3(0.545, 0.3, 0.545)));
            strip = max(strip, max(abs(bl.x), abs(bl.z)) - 0.565 * mix(0.2, 1.0, band));
            if (strip < r.x) { r = vec2(strip, 16.0); gL = bl; }
        }
    } else if (uAnim == 10 || uAnim == 11) {            // Forge / NeoForge: hammer strikes the anvil
        float pop = easeOutBack(seg(t, 0.0, 0.15)) * (1.0 - seg(t, 0.92, 1.0));
        if (pop < 0.01) return r;
        vec3 l = q / pop - vec3(0.0, -0.55, 0.0);
        l.xz *= rot(0.5);
        float anv = sdBox(l - vec3(0.0, -0.45, 0.0), vec3(0.5, 0.11, 0.32)) - 0.02;
        anv = min(anv, sdBox(l - vec3(0.0, -0.16, 0.0), vec3(0.2, 0.2, 0.16)) - 0.02);
        anv = min(anv, sdBox(l - vec3(-0.05, 0.17, 0.0), vec3(0.62, 0.13, 0.28)) - 0.03);
        anv = min(anv, sdCapsule(l, vec3(0.55, 0.2, 0.0), vec3(1.0, 0.24, 0.0), 0.09));
        r = vec2(anv * pop, 11.0);
        float a;
        if (t < 0.3) a = mix(0.2, 1.35, easeOut(t / 0.3));
        else if (t < 0.42) { float u = (t - 0.3) / 0.12; a = mix(1.35, 0.0, u * u); }
        else a = 0.28 * sin(seg(t, 0.42, 0.6) * 3.14159) * (1.0 - seg(t, 0.42, 0.6));
        vec3 hp = l - vec3(-0.95, 0.53, 0.0);
        hp.xy = rot(a) * hp.xy;
        float handle = sdCapsule(hp, vec3(0.0), vec3(1.0, 0.0, 0.0), 0.04);
        float head = sdBox(hp - vec3(1.0, 0.0, 0.0), vec3(0.13, 0.22, 0.15)) - 0.02;
        float hm = min(handle, head);
        if (hm * pop < r.x) r = vec2(hm * pop, (uAnim == 11 && head < handle) ? 12.0 : 11.0);
        if (uAnim == 11) {
            float sw = seg(t, 0.42, 0.85);
            if (sw > 0.0 && sw < 1.0) {
                vec3 sq = l - vec3(0.0, 0.31, 0.0);
                float ring = length(vec2(length(sq.xz) - sw * 2.4, sq.y)) - 0.04 * (1.0 - sw);
                if (ring * pop < r.x) r = vec2(ring * pop, 12.0);
            }
        }
        gL = l;
    } else if (uAnim == 12 || uAnim == 13) {            // Mohist / Youer: two orbs merge
        float pop = easeOutBack(seg(t, 0.0, 0.15));
        float boom = seg(t, 0.82, 1.0);
        float sep = mix(1.8, 0.0, easeOut(seg(t, 0.1, 0.62)));
        float ang = t * 9.0;
        vec3 pa = vec3(cos(ang), 0.25 * sin(ang * 0.5), sin(ang)) * sep * 0.5;
        float ra = 0.42 * pop * (1.0 + boom * 0.8) * (1.0 - boom);
        if (ra < 0.005) return r;
        float d = smin(length(q - pa) - ra, length(q + pa) - ra, 0.45 * max(pop, 0.1));
        r = vec2(d, 13.0);
        gL = q;
        gK = dot(q, normalize(pa + vec3(1e-4)));
    } else if (uAnim == 14) {                           // Arclight: lightning between two orbs
        float pop = easeOutBack(seg(t, 0.0, 0.15)) * (1.0 - seg(t, 0.9, 1.0));
        if (pop < 0.01) return r;
        vec3 A = vec3(-1.15, 0.0, 0.0), B = vec3(1.15, 0.0, 0.0);
        r = vec2(min(length(q - A), length(q - B)) - 0.24 * pop, 5.0);
        if (t > 0.15 && t < 0.85) {
            float seed = floor(uTime * 22.0);
            vec3 prev = A;
            float bolt = 1e3;
            for (int i = 1; i <= 7; i++) {
                float fi = float(i);
                vec3 nx = mix(A, B, fi / 7.0);
                if (i < 7) nx += vec3(0.0, h1(fi, seed) - 0.5, h1(fi, seed + 3.0) - 0.5) * 0.55;
                bolt = min(bolt, sdCapsule(q, prev, nx, 0.024));
                prev = nx;
            }
            if (bolt < r.x) r = vec2(bolt, 14.0);
        }
        gL = q;
    } else if (uAnim == 15) {                           // Banner: a flag rises and waves
        float rise = easeOutBack(seg(t, 0.0, 0.35));
        float o = seg(t, 0.88, 1.0);
        vec3 l = q - vec3(0.0, mix(-3.6, -0.4, rise) - o * o * 4.0, 0.0);
        float pole = sdCapsule(l, vec3(-0.75, -1.5, 0.0), vec3(-0.75, 1.35, 0.0), 0.045);
        pole = min(pole, sdCapsule(l, vec3(-0.75, 1.3, 0.0), vec3(0.45, 1.3, 0.0), 0.035));
        r = vec2(pole, 5.0);
        vec3 w = l - vec3(-0.15, 0.5, 0.0);
        float sway = (1.3 - l.y) * 0.5;
        w.z -= 0.16 * sin(w.x * 3.0 - uTime * 5.0) * sway + 0.05 * sin(w.y * 5.0 + uTime * 3.0);
        float cl = (sdBox(w, vec3(0.55, 0.78, 0.012)) - 0.004) * 0.6;
        if (cl < r.x) { r = vec2(cl, 15.0); gL = w; }
    }
    return r;
}

vec2 mapAll(vec3 p) {
    vec2 g = vec2(mapGlass(p), 0.0);
    if (uAnim > 0) {
        vec2 a = mapAnim(p);
        if (a.x < g.x) g = a;
    }
    return g;
}
"""

SHADE = """
// box surface point -> 16x16 pixel coords on the face and face id (0 = side, 1 = top/bottom)
vec2 boxPixel(vec3 l, float hs, out float topFace) {
    vec3 a = abs(l);
    vec2 uv;
    topFace = 0.0;
    if (a.y >= a.x && a.y >= a.z) { uv = l.xz; topFace = 1.0; }
    else if (a.x >= a.z) uv = l.zy;
    else uv = l.xy;
    return floor(clamp((uv / (2.0 * hs) + 0.5), 0.0, 0.9999) * 16.0);
}

vec3 purpurTex(vec3 l, float idx) {
    float top;
    vec2 px = boxPixel(l, 0.3, top);
    float n = h1(px.x + px.y * 17.0, idx + top * 3.0);
    vec3 base = vec3(0.663, 0.490, 0.663), light = vec3(0.780, 0.608, 0.780), dark = vec3(0.494, 0.333, 0.494);
    vec3 c;
    if (idx > 1.5) {                                    // top: purpur pillar
        if (top > 0.5) {                                // top face: concentric squares
            vec2 d = abs(px - 7.5);
            float ring = max(d.x, d.y);
            c = (mod(floor(ring), 3.0) < 1.0) ? dark : ((mod(floor(ring), 3.0) < 2.0) ? base : light);
        } else {                                        // sides: vertical grooves
            float col = mod(px.x, 4.0);
            c = col < 0.5 ? dark : (col < 1.5 ? light : base);
            if (px.y < 0.5 || px.y > 14.5) c = dark;
        }
    } else {                                            // purpur block: 4x4 tiles, lit top-left / dark bottom-right
        vec2 t = mod(px, 4.0);
        c = base;
        if (t.x < 0.5 || t.y > 2.5) c = light;
        if (t.x > 2.5 || t.y < 0.5) c = dark;
    }
    return c * 1.1 * (0.92 + 0.16 * n);
}

vec3 weave(vec2 uv, vec3 warpCol, vec3 weftCol, float freq) {
    vec2 g = uv * freq;
    vec2 c = floor(g), f = fract(g);
    float over = step(mod(c.x + c.y, 4.0), 1.5);       // 2/2 twill (diagonal weave)
    float warp = sin(f.x * 3.14159), weft = sin(f.y * 3.14159);
    float th = mix(weft, warp, over);
    vec3 col = mix(weftCol * (0.9 + 0.2 * h1(c.y, 5.0)), warpCol * (0.9 + 0.2 * h1(c.x, 9.0)), over);
    float fiber = h1(floor(g.x * 6.0) + floor(g.y * 6.0) * 31.0, 2.0);
    float mott = 0.5 + 0.25 * sin(uv.x * 3.1 + uv.y * 1.7) + 0.25 * sin(uv.x * 7.3 - uv.y * 5.9);   // dye mottling
    float slub = 0.5 + 0.5 * sin(c.x * 0.37 + sin(c.y * 0.11) * 3.0);                         // uneven yarn thickness
    return col * (0.80 + 0.20 * th) * (0.95 + 0.07 * fiber) * (0.92 + 0.10 * mott) * (0.97 + 0.05 * slub);
}

vec3 clothEdge(vec3 col, vec2 uv, vec2 halfSize) {
    float d = min(halfSize.x - abs(uv.x), halfSize.y - abs(uv.y));
    col *= mix(0.80, 1.0, smoothstep(0.03, 0.06, d));           // folded, stitched hem
    float along = abs(uv.x) > abs(uv.y) * (halfSize.x / halfSize.y) ? uv.y : uv.x;
    float dash = step(0.4, fract(along * 11.0));
    col = mix(col, col * 0.45, smoothstep(0.013, 0.004, abs(d - 0.075)) * dash);   // stitch line
    return col;
}

vec3 matCol(float m, vec3 l, out float metal, out float emis) {
    metal = 0.0; emis = 0.0; gCloth = 0.0;
    if (m < 1.5) {                                      // grass/dirt (pixel pattern)
        vec3 px = floor(l * 8.0); float h = h1(px.x + px.z * 7.0, px.y);
        float top = step(0.36 - h * 0.12, l.y);
        return mix(vec3(0.52, 0.36, 0.22) * (0.8 + 0.35 * h), vec3(0.33, 0.66, 0.22) * (0.85 + 0.3 * h), top);
    }
    if (m < 2.5) return vec3(0.97, 0.98, 1.0) * (0.9 + 0.1 * step(0.0, l.y));
    if (m < 3.5) return purpurTex(l, gK);
    if (m < 4.5) { float vein = smoothstep(0.02, 0.0, abs(l.z)) * 0.4; return vec3(0.22, 0.72, 0.38) * (1.0 + vein); }
    if (m < 5.5) { metal = 1.0; return vec3(0.86, 0.88, 0.92); }
    if (m < 6.5) { metal = 0.6; emis = 0.3; return vec3(0.35, 0.65, 1.0); }
    if (m < 7.5) { emis = 2.2;
        float n = 0.5 + 0.5 * sin(l.x * 6.0 + uTime * 2.0) * sin(l.y * 7.0 - uTime * 3.0) * sin(l.z * 5.0 + uTime);
        return mix(vec3(1.0, 0.22, 0.02), vec3(1.0, 0.8, 0.2), n); }
    if (m < 8.5) {                                      // Fabric: linen twill cloth
        gCloth = 1.0;
        vec3 warp = mix(vec3(0.87, 0.81, 0.68), uC1, 0.08), weft = vec3(0.72, 0.64, 0.50);
        return clothEdge(weave(l.xy, warp, weft, 24.0), l.xy, vec2(1.05, 0.68)); }
    if (m < 9.5) { metal = 0.55; return vec3(0.62, 0.64, 0.68); }
    if (m < 10.5) {                                     // beta-era grass block (old bright green + dirt)
        vec3 px = floor(l * 8.0); float h = h1(px.x + px.z * 5.0, px.y);
        float top = step(0.42 - h * 0.08, l.y);
        return mix(vec3(0.55, 0.40, 0.26) * (0.75 + 0.4 * h), vec3(0.42, 0.78, 0.25) * (0.8 + 0.35 * h), top); }
    if (m < 11.5) { metal = 0.7; return vec3(0.3, 0.31, 0.35); }
    if (m < 12.5) { emis = 2.0; return mix(uC1, uC2, 0.5 + 0.5 * sin(uTime * 4.0)); }
    if (m < 13.5) {
        vec3 a = (uAnim == 13) ? vec3(0.65, 0.4, 1.0) : vec3(1.0, 0.5, 0.15);
        vec3 b = (uAnim == 13) ? vec3(0.2, 0.95, 0.8) : vec3(0.2, 0.75, 1.0);
        emis = 0.4; return mix(a, b, smoothstep(-0.3, 0.3, gK)); }
    if (m < 14.5) { emis = 4.0; return vec3(1.0, 0.95, 0.65); }
    if (m < 15.5) {                                     // flag cloth
        gCloth = 1.0;
        float st = smoothstep(0.06, 0.03, abs(abs(l.x) + abs(l.y - 0.05) - 0.35));
        vec3 c = weave(l.xy, mix(uC1 * 0.85, vec3(0.97), st), mix(uC1 * 0.7, vec3(0.9), st), 20.0);
        return clothEdge(c, l.xy, vec2(0.55, 0.78)); }
    if (m < 16.5) {                                     // Fabric cloth band (cream + stitching)
        float stitch = smoothstep(0.012, 0.0, abs(abs(l.y) - 0.045)) * step(0.5, fract((l.x + l.z) * 14.0));
        gCloth = 1.0;
        return mix(weave(l.xz + l.y, vec3(0.87, 0.81, 0.68), vec3(0.74, 0.66, 0.52), 26.0), vec3(0.45, 0.38, 0.28), stitch); }
    float id = m - 20.0;                                // quilt patch
    vec3 pal = 0.55 + 0.45 * cos(6.2831 * (id * 0.137 + vec3(0.0, 0.33, 0.67)));
    return pal * (1.0 - step(0.19, max(abs(l.x), abs(l.y))) * 0.25);
}

vec3 shadeAnim(vec3 p, vec3 n, vec3 rd, float m) {
    float metal, emis;
    vec3 base = matCol(m, gL, metal, emis);
    vec3 L = normalize(vec3(0.5, 0.8, -0.6));
    float dif = max(dot(n, L), 0.0);
    vec3 col = base * (dif * 0.9 + 0.22) + base * env(n) * 0.45;
    vec3 rr = reflect(rd, n);
    float fre = pow(1.0 - max(dot(-rd, n), 0.0), 4.0);
    if (gCloth > 0.5) {
        float wrap = max(dot(n, L) * 0.5 + 0.5, 0.0);                 // cloth: soft wrap lighting
        col = base * (wrap * 0.85 + 0.18) + base * env(n) * 0.35;
        col += base * fre * 0.45;                                    // subtle sheen at cloth edges
        col += base * abs(dot(n, rd)) * 0.05;
    } else {
        col = mix(col, env(rr) * mix(vec3(1.0), base, metal), clamp(metal * 0.8 + fre * 0.3, 0.0, 1.0));
        col += vec3(1.0) * pow(max(dot(n, normalize(L - rd)), 0.0), 48.0) * (0.3 + metal * 0.8) * (m > 2.5 && m < 3.5 ? 0.35 : 1.0);
    }
    col += base * emis;
    return col;
}

vec3 emissiveGlow(float m) {
    if (m > 6.5 && m < 7.5) return vec3(1.0, 0.35, 0.05);
    if (m > 11.5 && m < 12.5) return uC1;
    if (m > 13.5 && m < 14.5) return vec3(1.0, 0.9, 0.6);
    return vec3(0.0);
}
"""
