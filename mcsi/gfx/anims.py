"""Signature animations played when a server type is picked (GLSL snippet), spliced into shaders.SCENE_FS."""

# server type -> animation id, duration (s), particle burst time and position (relative to the animation center)
ANIM_ID = {"vanilla": 1, "paper": 2, "purpur": 3, "folia": 4, "spigot": 5, "bukkit": 6, "fabric": 7,
           "quilt": 8, "babric": 9, "forge": 10, "neoforge": 11, "mohist": 12, "youer": 13, "arclight": 14,
           "banner": 15, "legacyfabric": 7,
           # limited-time event loaders (core/events.py)
           "ev_halloween": 30, "ev_christmas": 31, "ev_newyear": 32, "ev_valentine": 33, "ev_aprilfools": 34}
ANIM_DUR = {"paper": 2.1, "ev_halloween": 4.6, "ev_christmas": 5.0, "ev_newyear": 5.0, "ev_valentine": 4.4,
            "ev_aprilfools": 4.6}
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
    # several bursts: a list of (time, offset)
    "ev_halloween": (0.62, (0.0, 0.0, 0.0)),
    "ev_christmas": (0.8, (0.0, 1.05, 0.0)),
    "ev_newyear": [(0.16, (-1.3, 0.9, 0.0)), (0.29, (0.9, 1.25, 0.0)), (0.42, (-0.2, 1.55, 0.0)),
                   (0.55, (1.5, 0.55, 0.0)), (0.68, (-0.9, 1.35, 0.0))],
    "ev_valentine": (0.45, (0.55, 0.45, 0.0)),
    "ev_aprilfools": (0.5, (-0.9, -0.35, 0.0)),
}
# screen flash (time, rgb) for big moments
ANIM_FLASH = {"ev_aprilfools": (0.5, (1.0, 0.75, 0.4))}
ANIM_CENTER = (0.95, 0.0, 0.0)
ANIM_SCALE = 0.82
ANIM_BURST = {k: [(t, tuple(c * ANIM_SCALE for c in off)) for t, off in (v if isinstance(v, list) else [v])]
              for k, v in ANIM_BURST.items()}

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

float dot2v(vec2 v) { return dot(v, v); }
float sdBox2(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
float sdEqTri(vec2 p, float r) {
    const float k = 1.7320508;
    p.x = abs(p.x) - r; p.y = p.y + r / k;
    if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
    p.x -= clamp(p.x, -2.0 * r, 0.0);
    return -length(p) * sign(p.y);
}
float sdCappedCone(vec3 p, float h, float r1, float r2) {   // y in [-h, h], radius r1 at the bottom, r2 at the top
    vec2 q = vec2(length(p.xz), p.y);
    vec2 k1 = vec2(r2, h), k2 = vec2(r2 - r1, 2.0 * h);
    vec2 ca = vec2(q.x - min(q.x, (q.y < 0.0) ? r1 : r2), abs(q.y) - h);
    vec2 cb = q - k1 + k2 * clamp(dot(k1 - q, k2) / dot2v(k2), 0.0, 1.0);
    float s = (cb.x < 0.0 && ca.y < 0.0) ? -1.0 : 1.0;
    return s * sqrt(min(dot2v(ca), dot2v(cb)));
}
float sdHeart(vec2 p) {                                     // tip at (0,0), top at y ~ 1.1
    p.x = abs(p.x);
    if (p.y + p.x > 1.0) return sqrt(dot2v(p - vec2(0.25, 0.75))) - 0.35355339;
    return sqrt(min(dot2v(p - vec2(0.0, 1.0)), dot2v(p - 0.5 * max(p.x + p.y, 0.0)))) * sign(p.x - p.y);
}
float sdStar5(vec2 p, float r, float rf) {
    const vec2 k1 = vec2(0.809016994375, -0.587785252292);
    const vec2 k2 = vec2(-k1.x, k1.y);
    p.x = abs(p.x);
    p -= 2.0 * max(dot(k1, p), 0.0) * k1;
    p -= 2.0 * max(dot(k2, p), 0.0) * k2;
    p.x = abs(p.x);
    p.y -= r;
    vec2 ba = rf * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
    float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
    return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}
float extrude(float d2, float z, float hz) { vec2 w = vec2(d2, abs(z) - hz); return min(max(w.x, w.y), 0.0) + length(max(w, 0.0)); }
// height of a dropped object bouncing on the ground (gravity + restitution); tau in seconds
float bounceH(float tau, float h0) {
    const float g = 24.0;
    float tf = sqrt(2.0 * h0 / g);
    if (tau < tf) return h0 - 0.5 * g * tau * tau;
    tau -= tf;
    float v = g * tf * 0.42;
    for (int i = 0; i < 4; i++) {
        float tb = 2.0 * v / g;
        if (tau < tb) return v * tau - 0.5 * g * tau * tau;
        tau -= tb;
        v *= 0.42;
    }
    return 0.0;
}

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
    } else if (uAnim == 30) {                           // Halloween: a pumpkin block grows while spinning
        float s = (0.12 + 0.88 * easeOutBack(seg(t, 0.0, 0.62))) * (1.0 - seg(t, 0.9, 1.0));
        if (s < 0.01) return r;
        vec3 l = (q - vec3(0.0, -0.15, 0.0)) / s;
        l.xz *= rot((1.0 - easeOut(seg(t, 0.0, 0.82))) * 12.566 - 0.45);
        l.yz *= rot(-0.18);
        float body = sdBox(l, vec3(0.85));
        float stem = sdBox(l - vec3(0.0, 0.85 + 0.16, 0.0), vec3(0.106, 0.16, 0.106));
        r = vec2(body * s, 40.0); gL = l;
        if (stem * s < r.x) r = vec2(stem * s, 41.0);
    } else if (uAnim == 31) {                           // Christmas: a tree builds itself, ornaments drop in
        float o = 1.0 - seg(t, 0.93, 1.0);
        if (o < 0.01) return r;
        vec3 l = (q - vec3(0.0, -0.15, 0.0)) / o;
        l.xz *= rot(t * 2.6);
        float tr = easeOut(seg(t, 0.0, 0.14));
        if (tr > 0.0) {
            float h = 0.3 * tr;
            float d = sdBox(l - vec3(0.0, -1.5 + h, 0.0), vec3(0.15, h, 0.15)) - 0.02;
            r = vec2(d * o, 44.0); gL = l;
        }
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            float k = easeOutBack(seg(t, 0.14 + fi * 0.1, 0.32 + fi * 0.1));
            if (k <= 0.0) continue;
            float base = -1.0 + fi * 0.62;
            float hh = 0.42 - fi * 0.04;
            vec3 c = l - vec3(0.0, base + hh + (1.0 - k) * 3.5, 0.0);
            c.xz *= rot((1.0 - k) * 4.0);
            float rad = 1.0 - fi * 0.25;
            float ang = atan(c.z, c.x);
            float d = sdCappedCone(c, hh, rad, 0.08) * 0.8 + 0.035 * sin(ang * 11.0) * smoothstep(0.3, -hh, c.y);
            if (d * o < r.x) { r = vec2(d * o, 43.0); gL = c; }
        }
        for (int i = 0; i < 8; i++) {                     // ornaments: dropped, they bounce onto the branches
            float fi = float(i);
            float start = 0.48 + fi * 0.035;
            if (t < start) continue;
            float layer = mod(fi, 3.0);
            float a = fi * 2.4;
            float yb = -1.0 + layer * 0.62 + 0.12;
            float rr = (1.0 - layer * 0.25) * 0.88 + 0.07;
            vec3 tgt = vec3(cos(a) * rr, yb, sin(a) * rr);
            float h = bounceH((t - start) * 5.0, 2.6);
            float d = length(l - tgt - vec3(0.0, h, 0.0)) - 0.1;
            if (d * o < r.x) { r = vec2(d * o, 45.0); gK = fi; gL = l; }
        }
        float st = easeOutBack(seg(t, 0.78, 0.88));
        if (st > 0.0) {
            vec3 sp = l - vec3(0.0, 0.92, 0.0);
            sp.xz *= rot(-t * 2.6 + uTime * 2.0);
            float d = (extrude(sdStar5(sp.xy / st, 0.3, 0.42) * st, sp.z, 0.05 * st) - 0.012);
            if (d * o < r.x) { r = vec2(d * o, 46.0); gL = sp; }
        }
    } else if (uAnim == 32) {                           // New year: rockets fly up into the sky and burst
        vec3 l = q;
        float xs[5] = float[5](-1.3, 0.9, -0.2, 1.5, -0.9);
        float ys[5] = float[5](0.9, 1.25, 1.55, 0.55, 1.35);
        for (int i = 0; i < 5; i++) {
            float fi = float(i);
            float t0 = 0.02 + fi * 0.13;
            float up = seg(t, t0, t0 + 0.14);
            vec3 start = vec3(xs[i] * 0.6, -2.7, 0.0);
            vec3 apex = vec3(xs[i], ys[i], 0.3 * sin(fi * 2.0));
            if (up > 0.0 && up < 1.0) {
                vec3 pos = mix(start, apex, easeOut(up)) + vec3(0.05 * sin(up * 30.0 + fi), 0.0, 0.0);
                vec3 dir = normalize(apex - start);
                float d = sdCapsule(l, pos - dir * 0.3, pos, 0.055);
                if (d < r.x) { r = vec2(d, 48.0); gL = l - pos; }
                float sp = length(l - (pos - dir * 0.4)) - 0.065;          // exhaust flame
                if (sp < r.x) r = vec2(sp, 53.0);
            } else if (up <= 0.0) {
                r.x = min(r.x, length(l - start) - 0.4);
            }
            float ex = seg(t, t0 + 0.14, t0 + 0.36);
            if (ex > 0.0 && ex < 1.0) {
                vec3 c = apex - vec3(0.0, ex * ex * 0.7, 0.0);
                float rad = 1.0 * easeOut(ex);
                float bd = length(l - c) - rad;
                if (bd < 0.3) {
                    for (int k = 0; k < 16; k++) {
                        float fk = float(k);
                        vec3 dir = normalize(vec3(h1(fk, fi + 1.0) - 0.5, h1(fk, fi + 7.0) - 0.5, h1(fk, fi + 13.0) - 0.5));
                        float d = length(l - c - dir * rad) - 0.085 * (1.0 - ex * 0.85);
                        if (d < r.x) { r = vec2(d, 49.0); gK = fi * 3.0 + fk * 0.13; }
                    }
                } else {
                    r.x = min(r.x, bd - 0.2);                             // keep the ray march step bounded
                }
            }
        }
    } else if (uAnim == 33) {                           // Valentine: a heart chocolate gets bitten and vanishes
        float pop = easeOutBack(seg(t, 0.0, 0.22));
        float out_ = seg(t, 0.82, 1.0);
        float s = pop * (1.0 - out_ * out_);
        if (s < 0.01) return r;
        vec3 l = (q - vec3(0.0, -out_ * 1.2, 0.0)) / s;
        l.xz *= rot((1.0 - easeOut(seg(t, 0.0, 0.4))) * 9.42 + 0.25 * sin(uTime * 1.3));
        float squash = 1.0 + 0.12 * sin(seg(t, 0.44, 0.6) * 18.0) * (1.0 - seg(t, 0.44, 0.6));
        l.y *= squash;
        float d2 = sdHeart(l.xy / 1.25 + vec2(0.0, 0.55)) * 1.25;
        float d = extrude(d2, l.z, 0.16) - 0.04;
        float bite = easeOut(seg(t, 0.43, 0.47));
        float inside = 0.0;
        if (bite > 0.0) {
            float b = 1e3;
            for (int k = 0; k < 3; k++) {
                float fk = float(k) - 1.0;
                b = min(b, length(l - vec3(0.72 + 0.1 * fk, 0.42 - 0.2 * fk, 0.0)) - 0.24 * bite);
            }
            inside = step(-0.02, -b);
            d = max(d, -b);
        }
        r = vec2(d * s * 0.85, 50.0); gL = l; gK = step(-0.012, -abs(d)) * inside;
        for (int k = 0; k < 6; k++) {                     // crumbs fall from the bite
            float fk = float(k);
            float tau = (t - 0.45 - fk * 0.01) * 4.4;
            if (tau <= 0.0 || tau > 1.6) continue;
            vec3 v0 = vec3(0.6 + h1(fk, 2.0) * 0.9, 0.8 + h1(fk, 3.0) * 0.8, (h1(fk, 4.0) - 0.5) * 1.2);
            vec3 c = vec3(0.75, 0.45, 0.0) + v0 * tau - vec3(0.0, 2.6 * tau * tau, 0.0);
            vec3 cl = l - c;
            cl.xy *= rot(tau * 6.0 + fk);
            float cd = sdBox(cl, vec3(0.05 + 0.02 * h1(fk, 9.0)));
            if (cd * s < r.x) { r = vec2(cd * s, 50.0); gL = cl; gK = 1.0; }
        }
    } else if (uAnim == 34) {                           // April fools: TNT blows the little blocky guy away
        float pop = easeOutBack(seg(t, 0.0, 0.12)) * (1.0 - seg(t, 0.93, 1.0));
        if (pop < 0.01) return r;
        vec3 tl = (q - vec3(-0.9, -0.35, 0.0));
        float boom = step(0.5, t);
        if (boom < 0.5) {
            float swell = 1.0 + 0.12 * seg(t, 0.3, 0.5) * (0.5 + 0.5 * sin(t * t * 260.0));
            vec3 b = tl / (pop * swell);
            b.xz *= rot(0.55);
            b.yz *= rot(0.18);
            float d = (sdBox(b, vec3(0.42)) - 0.02) * pop * swell;
            float flash = step(0.2, t) * step(0.0, sin(t * t * 300.0));
            r = vec2(d, 52.0); gL = b; gK = flash;
            vec3 fu = tl - vec3(0.0, 0.45 * pop, 0.0);
            float fuse = sdCapsule(fu, vec3(0.0), vec3(0.04, 0.16, 0.0), 0.025);
            if (fuse < r.x) { r = vec2(fuse, 44.0); gL = fu; }
            float spark = length(fu - vec3(0.04, 0.2, 0.0)) - 0.05 * (0.8 + 0.4 * sin(uTime * 40.0));
            if (spark < r.x) r = vec2(spark, 53.0);
        }
        // the little blocky guy (an original mascot): stands, then is launched up and away, tumbling
        // ...then drops back from the sky onto its spot and bounces (it is fine)
        float fly = (t < 0.76) ? max(0.0, (t - 0.5) * 4.6) : 0.0;
        vec3 home = vec3(0.9, -0.35, 0.0);
        vec3 gp = home + vec3(0.6, 4.4, 2.0) * fly - vec3(0.0, 1.6 * fly * fly, 0.0);
        if (t >= 0.76) gp = home + vec3(0.0, bounceH((t - 0.76) * 4.6, 3.2), 0.0);
        vec3 g = (q - gp) / pop;
        g.xy *= rot(-fly * 9.0);
        g.xz *= rot(-0.5 + fly * 4.0 + (t >= 0.76 ? sin(uTime * 3.0) * 0.3 : 0.0));
        if (length(g) < 1.4) {
            float head = sdBox(g - vec3(0.0, 0.42, 0.0), vec3(0.2)) - 0.03;
            float visor = sdBox(g - vec3(0.0, 0.44, -0.2), vec3(0.15, 0.06, 0.03));
            float body = sdBox(g - vec3(0.0, 0.02, 0.0), vec3(0.17, 0.2, 0.11)) - 0.02;
            float wave = (t < 0.5) ? sin(uTime * 10.0) * 0.4 : 1.2;
            vec3 al = g - vec3(0.28, 0.16, 0.0); al.xy *= rot(-wave);
            vec3 ar = g - vec3(-0.28, 0.16, 0.0); ar.xy *= rot(fly > 0.0 ? 1.2 : 0.1);
            float arms = min(sdBox(al - vec3(0.0, -0.14, 0.0), vec3(0.07, 0.17, 0.07)),
                             sdBox(ar - vec3(0.0, -0.14, 0.0), vec3(0.07, 0.17, 0.07)));
            float legs = min(sdBox(g - vec3(0.09, -0.36, 0.0), vec3(0.075, 0.17, 0.08)),
                             sdBox(g - vec3(-0.09, -0.36, 0.0), vec3(0.075, 0.17, 0.08)));
            float best = head; float part = 0.0;
            if (visor < best) { best = visor; part = 1.0; }
            if (body < best) { best = body; part = 2.0; }
            if (min(arms, legs) < best) { best = min(arms, legs); part = 3.0; }
            if (best * pop < r.x) { r = vec2(best * pop, 54.0); gK = part; gL = g; }
        } else {
            r.x = min(r.x, (length(g) - 1.0) * pop);      // keep the ray march step bounded when nothing else is near
        }
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

// ---- 16x16 pixel textures for the event blocks (original designs) ----
ivec2 cubePix(vec3 l, float h, out int face) {     // face: 0 front (-z), 1 sides/back, 2 top, 3 bottom
    vec3 a = abs(l);
    vec2 uv;
    if (a.y >= a.x && a.y >= a.z) { face = l.y > 0.0 ? 2 : 3; uv = l.xz; }
    else if (a.z >= a.x) { face = l.z < 0.0 ? 0 : 1; uv = vec2(l.z < 0.0 ? l.x : -l.x, -l.y); }
    else { face = 1; uv = vec2(l.x > 0.0 ? l.z : -l.z, -l.y); }
    return ivec2(clamp(floor((uv / h * 0.5 + 0.5) * 16.0), 0.0, 15.0));
}
float pixNoise(ivec2 p, float s) { return h1(float(p.x) + s * 31.0, float(p.y) * 1.7 + s); }

vec3 pumpkinTex(vec3 l, out float emis) {
    int face;
    ivec2 p = cubePix(l, 0.85, face);
    float n = pixNoise(p, float(face));
    emis = 0.0;
    vec3 base = vec3(0.93, 0.47, 0.08), dark = vec3(0.66, 0.26, 0.04);
    vec3 c;
    if (face >= 2) {                                    // top / bottom: darker ring, stem spot
        float rr = length(vec2(p) - 7.5);
        c = mix(base, dark, step(rr, 3.0) * 0.6 + step(6.8, rr) * 0.35);
        if (face == 2 && rr < 1.6) c = vec3(0.32, 0.45, 0.12);
        if (face == 3) c *= 0.7;
    } else {                                            // sides: vertical ribs every 5 pixels
        c = (p.x % 5 == 0) ? dark : base;
        if (p.y == 0 || p.y == 15) c *= 0.82;
    }
    c *= 0.88 + 0.24 * n;
    if (face == 0) {                                    // carved face: triangle eyes, nose, toothy grin
        int x = p.x, y = p.y;
        int ex = (x < 8) ? x - 4 : x - 11;
        bool eye = y >= 3 && y <= 5 && abs(ex) <= (y - 3);
        bool nose = y == 8 && (x == 7 || x == 8);
        bool mouth = (y == 10 && x >= 2 && x <= 13 && x != 5 && x != 10)
                  || (y == 11 && x >= 3 && x <= 12)
                  || (y == 12 && x >= 5 && x <= 10 && x != 7 && x != 8);
        if (eye || nose || mouth) {
            emis = 1.3 * (0.8 + 0.2 * sin(uTime * 13.0) * sin(uTime * 7.3));
            c = mix(vec3(1.0, 0.6, 0.1), vec3(1.0, 0.88, 0.42), step(0.55, n));
        }
    }
    return c;
}

vec3 tntTex(vec3 l, float flash, out float emis) {
    int face;
    ivec2 p = cubePix(l, 0.42, face);
    float n = pixNoise(p, float(face) + 5.0);
    vec3 c;
    if (face >= 2) {                                    // top / bottom: round ends of the sticks
        ivec2 q = p % 4;
        c = (q.x == 0 || q.y == 0) ? vec3(0.42, 0.06, 0.05) : vec3(0.85, 0.15, 0.12);
        if (q.x == 2 && q.y == 2) c = vec3(0.95, 0.86, 0.7);
        if (face == 3) c *= 0.6;
    } else {                                            // sides: sticks, straps and a hazard band
        c = ((p.x / 4) % 2 == 0) ? vec3(0.86, 0.14, 0.11) : vec3(0.72, 0.09, 0.08);
        if (p.x % 4 == 3) c *= 0.75;
        if (p.y == 1 || p.y == 14) c = vec3(0.42, 0.29, 0.16);
        if (p.y == 5 || p.y == 10) c = vec3(0.12);
        if (p.y >= 6 && p.y <= 9) c = ((p.x + p.y) % 4 < 2) ? vec3(0.98, 0.8, 0.1) : vec3(0.07);
    }
    c *= 0.9 + 0.2 * n;
    emis = flash * 1.4;
    return mix(c, vec3(1.0), flash * 0.7);
}

vec3 eventMat(float m, vec3 l, out float metal, out float emis) {
    metal = 0.0; emis = 0.0; gCloth = 0.0;
    if (m < 40.5) return pumpkinTex(l, emis);           // pumpkin block (16x16 texture)
    if (m < 41.5) return mix(vec3(0.32, 0.46, 0.13), vec3(0.22, 0.33, 0.1), mod(floor(l.y * 9.4), 2.0));  // stem
    if (m < 42.5) { emis = 3.0; return vec3(1.0, 0.72, 0.28); }
    if (m < 43.5) {                                     // pine needles
        float n = h1(floor(l.x * 22.0) + floor(l.z * 22.0) * 7.0, floor(l.y * 22.0));
        return mix(vec3(0.04, 0.30, 0.12), vec3(0.12, 0.52, 0.22), n);
    }
    if (m < 44.5) return vec3(0.36, 0.22, 0.12);                          // wood (trunk, fuse)
    if (m < 45.5) {                                     // glossy ornaments
        metal = 0.75;
        vec3 pal[4] = vec3[4](vec3(0.95, 0.15, 0.15), vec3(1.0, 0.8, 0.2), vec3(0.25, 0.55, 1.0), vec3(0.85, 0.3, 0.9));
        return pal[int(mod(gK, 4.0))];
    }
    if (m < 46.5) { emis = 0.9; metal = 0.6; return vec3(1.0, 0.78, 0.2); }   // star
    if (m < 47.5) {                                     // firework box: red with gold bands
        float band = step(0.82, fract(l.y * 3.2 + 0.1)) + step(0.9, fract(l.x * 2.0 + l.z * 2.0)) * 0.6;
        return mix(vec3(0.78, 0.08, 0.10), vec3(0.98, 0.76, 0.22), clamp(band, 0.0, 1.0));
    }
    if (m < 48.5) { return mix(vec3(0.92), vec3(0.9, 0.2, 0.2), step(0.5, fract(l.y * 8.0))); }   // rocket
    if (m < 49.5) { emis = 0.7; return clamp(0.3 + 0.9 * cos(6.2831 * (gK * 0.37 + vec3(0.0, 0.33, 0.67))), 0.05, 1.0); }  // sparks
    if (m < 50.5) {                                     // chocolate (grid of squares; lighter where bitten)
        if (gK > 0.5) return vec3(0.42, 0.24, 0.12);
        vec2 g = abs(fract(l.xy * 2.4) - 0.5);
        float groove = smoothstep(0.44, 0.5, max(g.x, g.y)) * step(0.12, abs(l.z));
        metal = 0.15;
        return vec3(0.31, 0.16, 0.08) * (1.0 - groove * 0.5);
    }
    if (m < 52.5) return tntTex(l, gK, emis);           // TNT block (16x16 texture, gK = flash)
    if (m < 53.5) { emis = 4.0; return vec3(1.0, 0.8, 0.3); }             // fuse spark
    // little blocky guy: gK = part (0 head, 1 visor, 2 body, 3 limbs)
    if (gK < 0.5) return vec3(0.18, 0.78, 0.70);
    if (gK < 1.5) { emis = 0.9; return vec3(0.25, 0.9, 1.0); }
    if (gK < 2.5) return vec3(0.16, 0.22, 0.40);
    return vec3(0.12, 0.62, 0.56);
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
    if (m > 39.5) return eventMat(m, l, metal, emis);
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
    if (m > 41.5 && m < 42.5) return vec3(1.0, 0.55, 0.12);           // pumpkin candle
    if (m > 45.5 && m < 46.5) return vec3(1.0, 0.8, 0.3) * 0.25;      // star
    if (m > 48.5 && m < 49.5) return 0.18 * clamp(0.3 + 0.9 * cos(6.2831 * (gK * 0.37 + vec3(0.0, 0.33, 0.67))), 0.05, 1.0);
    if (m > 52.5 && m < 53.5) return vec3(1.0, 0.6, 0.2);             // fuse
    return vec3(0.0);
}
"""
