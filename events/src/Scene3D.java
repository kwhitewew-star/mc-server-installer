// Software 3D renderer for the event loaders: ray-marched signed distance fields, drawn on the CPU with
// plain Java (no OpenGL, no libraries), at a low resolution scaled up for a chunky pixel look.
// The scenes mirror the installer's OpenGL event animations.

import java.awt.image.BufferedImage;
import java.util.stream.IntStream;

final class Scene3D {
    final String event;
    final int w, h;
    final int[] px;
    final double[] accent;          // sky tint

    Scene3D(String event, int w, int h) {
        this.event = event;
        this.w = w;
        this.h = h;
        this.px = new int[w * h];
        switch (event) {
            case "christmas": accent = rgb(0x22c55e); break;
            case "newyear": accent = rgb(0x6366f1); break;
            case "valentine": accent = rgb(0xec4899); break;
            case "aprilfools": accent = rgb(0xef4444); break;
            case "ufo": accent = rgb(0xa3e635); break;
            default: accent = rgb(0xf97316);
        }
    }

    static double[] rgb(int c) {
        return new double[]{((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0};
    }

    /** Render frame t (0..1) at animation time sec (seconds, for flicker) into img. */
    void render(double t, double sec, BufferedImage img) {
        IntStream.range(0, h).parallel().forEach(y -> {
            Ctx c = new Ctx(event, t, sec);
            for (int x = 0; x < w; x++) px[y * w + x] = c.shade(x, y, w, h, accent);
        });
        img.setRGB(0, 0, w, h, px, 0, w);
    }

    // =====================================================================================
    static final class Ctx {
        final String ev;
        final double t, sec;
        int mat;                 // material of the last map() result
        double k;                // extra material value (part id, flash, colour index...)
        double lx, ly, lz;       // local coordinates for textures
        boolean bitten;

        Ctx(String ev, double t, double sec) {
            this.ev = ev;
            this.t = t;
            this.sec = sec;
        }

        // ---------------------------------------------------------------- helpers
        static double clamp(double v, double a, double b) { return v < a ? a : (v > b ? b : v); }
        static double seg(double t, double a, double b) { return clamp((t - a) / (b - a), 0, 1); }
        static double easeOut(double x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }
        static double easeOutBack(double x) {
            x = clamp(x, 0, 1);
            double c1 = 1.70158, c3 = c1 + 1;
            return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
        }
        static double h1(double a, double b) { double s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return s - Math.floor(s); }
        static double len(double x, double y, double z) { return Math.sqrt(x * x + y * y + z * z); }
        static double len2(double x, double y) { return Math.sqrt(x * x + y * y); }
        static double box(double x, double y, double z, double bx, double by, double bz) {
            double qx = Math.abs(x) - bx, qy = Math.abs(y) - by, qz = Math.abs(z) - bz;
            return len(Math.max(qx, 0), Math.max(qy, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, Math.max(qy, qz)), 0);
        }
        static double box2(double x, double y, double bx, double by) {
            double qx = Math.abs(x) - bx, qy = Math.abs(y) - by;
            return len2(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0);
        }
        static double capsule(double px, double py, double pz, double ax, double ay, double az,
                              double bx, double by, double bz, double r) {
            double pax = px - ax, pay = py - ay, paz = pz - az, bax = bx - ax, bay = by - ay, baz = bz - az;
            double hh = clamp((pax * bax + pay * bay + paz * baz) / (bax * bax + bay * bay + baz * baz), 0, 1);
            return len(pax - bax * hh, pay - bay * hh, paz - baz * hh) - r;
        }
        static double cappedCone(double px, double py, double pz, double hh, double r1, double r2) {
            double qx = len2(px, pz), qy = py;
            double k1x = r2, k1y = hh, k2x = r2 - r1, k2y = 2 * hh;
            double cax = qx - Math.min(qx, qy < 0 ? r1 : r2), cay = Math.abs(qy) - hh;
            double tt = clamp(((k1x - qx) * k2x + (k1y - qy) * k2y) / (k2x * k2x + k2y * k2y), 0, 1);
            double cbx = qx - k1x + k2x * tt, cby = qy - k1y + k2y * tt;
            double s = (cbx < 0 && cay < 0) ? -1 : 1;
            return s * Math.sqrt(Math.min(cax * cax + cay * cay, cbx * cbx + cby * cby));
        }
        static double heart(double x, double y) {
            x = Math.abs(x);
            if (y + x > 1) return len2(x - 0.25, y - 0.75) - 0.35355339;
            double m = 0.5 * Math.max(x + y, 0);
            return Math.sqrt(Math.min((x) * (x) + (y - 1) * (y - 1), (x - m) * (x - m) + (y - m) * (y - m))) * Math.signum(x - y);
        }
        static double star5(double x, double y, double r, double rf) {
            double k1x = 0.809016994375, k1y = -0.587785252292, k2x = -k1x, k2y = k1y;
            x = Math.abs(x);
            double d = Math.max(k1x * x + k1y * y, 0); x -= 2 * d * k1x; y -= 2 * d * k1y;
            d = Math.max(k2x * x + k2y * y, 0); x -= 2 * d * k2x; y -= 2 * d * k2y;
            x = Math.abs(x);
            y -= r;
            double bax = rf * -k1y, bay = rf * k1x - 1;
            double hh = clamp((x * bax + y * bay) / (bax * bax + bay * bay), 0, r);
            return len2(x - bax * hh, y - bay * hh) * Math.signum(y * bax - x * bay);
        }
        static double extrude(double d2, double z, double hz) {
            double wx = d2, wy = Math.abs(z) - hz;
            return Math.min(Math.max(wx, wy), 0) + len2(Math.max(wx, 0), Math.max(wy, 0));
        }
        static double bounceH(double tau, double h0) {
            double g = 24, tf = Math.sqrt(2 * h0 / g);
            if (tau < tf) return h0 - 0.5 * g * tau * tau;
            tau -= tf;
            double v = g * tf * 0.42;
            for (int i = 0; i < 4; i++) {
                double tb = 2 * v / g;
                if (tau < tb) return v * tau - 0.5 * g * tau * tau;
                tau -= tb;
                v *= 0.42;
            }
            return 0;
        }

        // ---------------------------------------------------------------- scenes
        double map(double x, double y, double z) {
            mat = 0;
            switch (ev) {
                case "christmas": return christmas(x, y, z);
                case "newyear": return newyear(x, y, z);
                case "valentine": return valentine(x, y, z);
                case "aprilfools": return aprilfools(x, y, z);
                case "ufo": return ufo(x, y, z);
                default: return halloween(x, y, z);
            }
        }

        double halloween(double x, double y, double z) {
            double s = (0.12 + 0.88 * easeOutBack(seg(t, 0, 0.62))) * (1 - seg(t, 0.92, 1));
            if (s < 0.01) return 1e3;
            double lx = x / s, ly = (y + 0.1) / s, lz = z / s;
            double a = (1 - easeOut(seg(t, 0, 0.82))) * 12.566 - 0.45;
            double c = Math.cos(a), sn = Math.sin(a);
            double rx = c * lx - sn * lz, rz = sn * lx + c * lz;
            double b = -0.18, cb = Math.cos(b), sb = Math.sin(b);
            double ry = cb * ly - sb * rz;
            rz = sb * ly + cb * rz;
            double body = box(rx, ry, rz, 0.85, 0.85, 0.85);
            double stem = box(rx, ry - 1.01, rz, 0.106, 0.16, 0.106);
            this.lx = rx; this.ly = ry; this.lz = rz;
            if (stem < body) { mat = 41; return stem * s; }
            mat = 40;
            return body * s;
        }

        double christmas(double x, double y, double z) {
            double o = 1 - seg(t, 0.93, 1);
            if (o < 0.01) return 1e3;
            double lx0 = x / o, ly = (y + 0.15) / o, lz0 = z / o;
            double a = t * 2.6, c = Math.cos(a), sn = Math.sin(a);
            double lx = c * lx0 - sn * lz0, lz = sn * lx0 + c * lz0;
            double best = 1e3;
            double tr = easeOut(seg(t, 0, 0.14));
            if (tr > 0) {
                double hh = 0.3 * tr;
                double d = box(lx, ly + 1.5 - hh, lz, 0.15, hh, 0.15) - 0.02;
                if (d < best) { best = d; mat = 44; }
            }
            for (int i = 0; i < 3; i++) {
                double k = easeOutBack(seg(t, 0.14 + i * 0.1, 0.32 + i * 0.1));
                if (k <= 0) continue;
                double base = -1.0 + i * 0.62, hh = 0.42 - i * 0.04, rad = 1.0 - i * 0.25;
                double cy = ly - (base + hh + (1 - k) * 3.5);
                double d = cappedCone(lx, cy, lz, hh, rad, 0.08) * 0.8;
                if (d < best) { best = d; mat = 43; this.lx = lx; this.ly = cy; this.lz = lz; }
            }
            for (int i = 0; i < 8; i++) {
                double start = 0.48 + i * 0.035;
                if (t < start) continue;
                double layer = i % 3, ang = i * 2.4;
                double yb = -1.0 + layer * 0.62 + 0.12, rr = (1 - layer * 0.25) * 0.88 + 0.07;
                double hgt = bounceH((t - start) * 5.0, 2.6);
                double d = len(lx - Math.cos(ang) * rr, ly - yb - hgt, lz - Math.sin(ang) * rr) - 0.1;
                if (d < best) { best = d; mat = 45; k = i; }
            }
            double st = easeOutBack(seg(t, 0.78, 0.88));
            if (st > 0) {
                double sy = ly - 0.92;
                double d = extrude(star5(x / o / st, sy / st, 0.3, 0.42) * st, z / o, 0.05 * st) - 0.012;
                if (d < best) { best = d; mat = 46; }
            }
            return best * o;
        }

        double newyear(double x, double y, double z) {
            double[] xs = {-1.3, 0.9, -0.2, 1.5, -0.9}, ys = {0.9, 1.25, 1.55, 0.55, 1.35};
            double best = 1e3;
            for (int i = 0; i < 5; i++) {
                double t0 = 0.02 + i * 0.13;
                double up = seg(t, t0, t0 + 0.14);
                double sx = xs[i] * 0.6, sy = -2.7, ax = xs[i], ay = ys[i], az = 0.3 * Math.sin(i * 2.0);
                if (up > 0 && up < 1) {
                    double e = easeOut(up);
                    double pxx = sx + (ax - sx) * e + 0.05 * Math.sin(up * 30 + i), py = sy + (ay - sy) * e, pz = az * e;
                    double dx = ax - sx, dy = ay - sy, dz = az, dl = len(dx, dy, dz);
                    dx /= dl; dy /= dl; dz /= dl;
                    double d = capsule(x, y, z, pxx - dx * 0.3, py - dy * 0.3, pz - dz * 0.3, pxx, py, pz, 0.055);
                    if (d < best) { best = d; mat = 48; ly = y - py; }
                    double f = len(x - (pxx - dx * 0.4), y - (py - dy * 0.4), z - (pz - dz * 0.4)) - 0.065;
                    if (f < best) { best = f; mat = 53; }
                } else if (up <= 0) {
                    double bnd = len(x - sx, y - sy, z) - 0.4;
                    if (bnd < best) { best = bnd; mat = 0; }
                }
                double ex = seg(t, t0 + 0.14, t0 + 0.36);
                if (ex > 0 && ex < 1) {
                    double cx = ax, cy = ay - ex * ex * 0.7, cz = az, rad = easeOut(ex);
                    double bd = len(x - cx, y - cy, z - cz) - rad;
                    if (bd < 0.3) {
                        for (int s = 0; s < 16; s++) {
                            double ux = h1(s, i + 1) - 0.5, uy = h1(s, i + 7) - 0.5, uz = h1(s, i + 13) - 0.5;
                            double ul = len(ux, uy, uz);
                            double d = len(x - cx - ux / ul * rad, y - cy - uy / ul * rad, z - cz - uz / ul * rad)
                                    - 0.085 * (1 - ex * 0.85);
                            if (d < best) { best = d; mat = 49; k = i * 3 + s * 0.13; }
                        }
                    } else if (bd - 0.2 < best) {
                        best = bd - 0.2; mat = 0;
                    }
                }
            }
            return best;
        }

        double valentine(double x, double y, double z) {
            double pop = easeOutBack(seg(t, 0, 0.22)), out = seg(t, 0.82, 1);
            double s = pop * (1 - out * out);
            if (s < 0.01) return 1e3;
            double lx0 = x / s, ly = (y + out * 1.2) / s, lz0 = z / s;
            double a = (1 - easeOut(seg(t, 0, 0.4))) * 9.42 + 0.25 * Math.sin(sec * 1.3);
            double c = Math.cos(a), sn = Math.sin(a);
            double lx = c * lx0 - sn * lz0, lz = sn * lx0 + c * lz0;
            double sq = seg(t, 0.44, 0.6);
            ly *= 1 + 0.12 * Math.sin(sq * 18) * (1 - sq);
            double d = extrude(heart(lx / 1.25, ly / 1.25 + 0.55) * 1.25, lz, 0.16) - 0.04;
            double bite = easeOut(seg(t, 0.43, 0.47));
            bitten = false;
            if (bite > 0) {
                double bmin = 1e3;
                for (int i = -1; i <= 1; i++)
                    bmin = Math.min(bmin, len(lx - 0.72 - 0.1 * i, ly - 0.42 + 0.2 * i, lz) - 0.24 * bite);
                if (-bmin > d - 0.02) bitten = true;
                d = Math.max(d, -bmin);
            }
            double best = d * 0.85;
            mat = 50; k = bitten ? 1 : 0; this.lx = lx; this.ly = ly; this.lz = lz;
            for (int i = 0; i < 6; i++) {
                double tau = (t - 0.45 - i * 0.01) * 4.4;
                if (tau <= 0 || tau > 1.6) continue;
                double cx = 0.75 + (0.6 + h1(i, 2) * 0.9) * tau, cy = (0.8 + h1(i, 3) * 0.8) * tau - 2.6 * tau * tau,
                        cz = (h1(i, 4) - 0.5) * 1.2 * tau;
                double dd = box(lx - cx, ly - cy, lz - cz, 0.06, 0.06, 0.06);
                if (dd < best) { best = dd; mat = 50; k = 1; }
            }
            return best * s;
        }

        double aprilfools(double x, double y, double z) {
            double pop = easeOutBack(seg(t, 0, 0.12)) * (1 - seg(t, 0.93, 1));
            if (pop < 0.01) return 1e3;
            double best = 1e3;
            if (t < 0.5) {
                double sw = 1 + 0.12 * seg(t, 0.3, 0.5) * (0.5 + 0.5 * Math.sin(t * t * 260));
                double bx = (x + 0.9) / (pop * sw), by = (y + 0.35) / (pop * sw), bz = z / (pop * sw);
                double a = 0.55, c = Math.cos(a), sn = Math.sin(a);
                double rx = c * bx - sn * bz, rz = sn * bx + c * bz;
                double d = box(rx, by, rz, 0.42, 0.42, 0.42) * pop * sw;
                double flash = (t > 0.2 && Math.sin(t * t * 300) > 0) ? 1 : 0;
                if (d < best) { best = d; mat = 52; k = flash; lx = rx; ly = by; lz = rz; }
                double f = len(x + 0.86, y - 0.12 * pop - 0.06, z) - 0.05;
                if (f < best) { best = f; mat = 53; }
            }
            double fly = t < 0.76 ? Math.max(0, (t - 0.5) * 4.6) : 0;
            double gx = 0.9 + 0.6 * fly, gy = -0.35 + 4.4 * fly - 1.6 * fly * fly, gz = 2.0 * fly;
            if (t >= 0.76) { gx = 0.9; gy = -0.35 + bounceH((t - 0.76) * 4.6, 3.2); gz = 0; }
            double qx = (x - gx) / pop, qy = (y - gy) / pop, qz = (z - gz) / pop;
            double a1 = -fly * 9, c1 = Math.cos(a1), s1 = Math.sin(a1);
            double rx = c1 * qx - s1 * qy, ry = s1 * qx + c1 * qy;
            double a2 = -0.5 + fly * 4 + (t >= 0.76 ? Math.sin(sec * 3) * 0.3 : 0), c2 = Math.cos(a2), s2 = Math.sin(a2);
            double rx2 = c2 * rx - s2 * qz, rz = s2 * rx + c2 * qz;
            double gl = len(rx2, ry, rz);
            if (gl < 1.4) {
                double head = box(rx2, ry - 0.42, rz, 0.2, 0.2, 0.2) - 0.03;
                double visor = box(rx2, ry - 0.44, rz + 0.2, 0.15, 0.06, 0.03);
                double body = box(rx2, ry - 0.02, rz, 0.17, 0.2, 0.11) - 0.02;
                double limbs = Math.min(Math.min(box(rx2 - 0.28, ry + 0.0, rz, 0.07, 0.17, 0.07),
                        box(rx2 + 0.28, ry + 0.0, rz, 0.07, 0.17, 0.07)),
                        Math.min(box(rx2 - 0.09, ry + 0.36, rz, 0.075, 0.17, 0.08), box(rx2 + 0.09, ry + 0.36, rz, 0.075, 0.17, 0.08)));
                double d = head; int part = 0;
                if (visor < d) { d = visor; part = 1; }
                if (body < d) { d = body; part = 2; }
                if (limbs < d) { d = limbs; part = 3; }
                if (d * pop < best) { best = d * pop; mat = 54; k = part; }
            } else {
                if ((gl - 1.0) * pop < best) { best = (gl - 1.0) * pop; mat = 0; }
            }
            // explosion sparks
            double ex = seg(t, 0.5, 0.7);
            if (ex > 0 && ex < 1) {
                double rad = 1.6 * easeOut(ex);
                double bd = len(x + 0.9, y + 0.35, z) - rad;
                if (bd < 0.3) {
                    for (int s = 0; s < 18; s++) {
                        double ux = h1(s, 21) - 0.5, uy = h1(s, 27) - 0.5, uz = h1(s, 33) - 0.5, ul = len(ux, uy, uz);
                        double d = len(x + 0.9 - ux / ul * rad, y + 0.35 - uy / ul * rad, z - uz / ul * rad) - 0.12 * (1 - ex);
                        if (d < best) { best = d; mat = 49; k = s * 0.07 + 0.1; }
                    }
                } else if (bd - 0.2 < best) { best = bd - 0.2; mat = 0; }
            }
            return best;
        }

        double ufo(double x, double y, double z) {
            // the saucer flies in, beams up three blocks, chews, spits them back and flies off
            double ux, uy = 1.2;
            if (t < 0.15) ux = -4 + 4 * easeOut(t / 0.15);
            else if (t > 0.85) ux = (t - 0.85) / 0.15 * 5;
            else ux = Math.sin(t * 40) * (t > 0.5 && t < 0.6 ? 0.08 : 0.02);
            double tilt = (t > 0.15 && t < 0.85) ? Math.sin(t * 25) * 0.08 : (t <= 0.15 ? -0.25 : 0.3);
            double qx = x - ux, qy = y - uy, qz = z;
            double c = Math.cos(tilt), sn = Math.sin(tilt);
            double rx = c * qx - sn * qy, ry = sn * qx + c * qy;
            double best;
            double disc = len2(len2(rx, qz) * 0.55, ry * 2.2) - 0.55;           // flattened saucer
            double k0 = len(rx / 1.15, ry * 3.0, qz / 1.15), k1 = len(rx / 1.3225, ry * 9.0, qz / 1.3225);
            disc = k0 * (k0 - 1.0) / Math.max(k1, 1e-6);
            double dome = len(rx, ry - 0.18, qz) - 0.42;
            best = disc; mat = 60;
            if (dome < best) { best = dome; mat = 61; }
            for (int i = 0; i < 6; i++) {
                double a = i / 6.0 * Math.PI * 2 + sec * 2;
                double d = len(rx - Math.cos(a) * 0.95, ry + 0.02, qz - Math.sin(a) * 0.95) - 0.07;
                if (d < best) { best = d; mat = 62; k = i; }
            }
            // three blocks: rest on the ground, get pulled up, then dropped back
            double[] bxs = {-0.9, 0.0, 0.9};
            for (int i = 0; i < 3; i++) {
                double take = easeOut(seg(t, 0.22 + i * 0.06, 0.4 + i * 0.06));
                double give = seg(t, 0.62 + i * 0.04, 0.8 + i * 0.04);
                double hgt;
                double baseY = -1.4;
                if (give > 0) hgt = (1 - give) * 2.4 + bounceH(Math.max(0, give - 0.6) * 1.0, 0.0);
                else hgt = take * 2.4;
                if (take >= 1 && give <= 0) continue;              // inside the UFO
                double sx = bxs[i] * (1 - take * (1 - give)), s = 1 - 0.7 * take * (1 - give);
                double spin = take * (1 - give) * 6;
                double cs = Math.cos(spin), ss = Math.sin(spin);
                double lx = x - sx, ly = y - (baseY + hgt), lz = z;
                double rx2 = cs * lx - ss * lz, rz2 = ss * lx + cs * lz;
                double d = box(rx2 / s, ly / s, rz2 / s, 0.25, 0.25, 0.25) * s;
                if (d < best) { best = d; mat = 63; k = i; this.lx = rx2 / s; this.ly = ly / s; this.lz = rz2 / s; }
            }
            return best;
        }

        // ---------------------------------------------------------------- materials
        static int cubePix(double v, double hh) { return (int) clamp(Math.floor((v / hh * 0.5 + 0.5) * 16), 0, 15); }

        /** base colour (r,g,b) + emission, written into out[0..3] */
        void material(double nx, double ny, double nz, double[] out) {
            double r = 0.8, g = 0.8, b = 0.8, e = 0;
            switch (mat) {
                case 40: {                                      // pumpkin block, 16x16 texture
                    double ax = Math.abs(lx), ay = Math.abs(ly), az = Math.abs(lz);
                    int face, px, py;
                    if (ay >= ax && ay >= az) { face = ly > 0 ? 2 : 3; px = cubePix(lx, 0.85); py = cubePix(lz, 0.85); }
                    else if (az >= ax) { face = lz < 0 ? 0 : 1; px = cubePix(lz < 0 ? lx : -lx, 0.85); py = cubePix(-ly, 0.85); }
                    else { face = 1; px = cubePix(lx > 0 ? lz : -lz, 0.85); py = cubePix(-ly, 0.85); }
                    double n = h1(px + face * 31, py * 1.7 + face);
                    double[] base = {0.93, 0.47, 0.08}, dark = {0.66, 0.26, 0.04};
                    double[] cc;
                    if (face >= 2) {
                        double rr = len2(px - 7.5, py - 7.5);
                        double m = (rr <= 3 ? 0.6 : 0) + (rr >= 6.8 ? 0.35 : 0);
                        cc = new double[]{base[0] + (dark[0] - base[0]) * m, base[1] + (dark[1] - base[1]) * m, base[2] + (dark[2] - base[2]) * m};
                        if (face == 2 && rr < 1.6) cc = new double[]{0.32, 0.45, 0.12};
                        if (face == 3) { cc[0] *= 0.7; cc[1] *= 0.7; cc[2] *= 0.7; }
                    } else {
                        cc = (px % 5 == 0) ? dark.clone() : base.clone();
                        if (py == 0 || py == 15) { cc[0] *= 0.82; cc[1] *= 0.82; cc[2] *= 0.82; }
                    }
                    double f = 0.88 + 0.24 * n;
                    r = cc[0] * f; g = cc[1] * f; b = cc[2] * f;
                    if (face == 0) {
                        int ex = px < 8 ? px - 4 : px - 11;
                        boolean eye = py >= 3 && py <= 5 && Math.abs(ex) <= py - 3;
                        boolean nose = py == 8 && (px == 7 || px == 8);
                        boolean mouth = (py == 10 && px >= 2 && px <= 13 && px != 5 && px != 10)
                                || (py == 11 && px >= 3 && px <= 12)
                                || (py == 12 && px >= 5 && px <= 10 && px != 7 && px != 8);
                        if (eye || nose || mouth) {
                            e = 1.3 * (0.8 + 0.2 * Math.sin(sec * 13) * Math.sin(sec * 7.3));
                            r = 1.0; g = n > 0.55 ? 0.88 : 0.6; b = n > 0.55 ? 0.42 : 0.1;
                        }
                    }
                    break;
                }
                case 41: { boolean alt = ((int) Math.floor(ly * 9.4)) % 2 == 0; r = alt ? 0.32 : 0.22; g = alt ? 0.46 : 0.33; b = alt ? 0.13 : 0.1; break; }
                case 43: { double n = h1(Math.floor(lx * 22) + Math.floor(lz * 22) * 7, Math.floor(ly * 22)); r = 0.04 + 0.08 * n; g = 0.3 + 0.22 * n; b = 0.12 + 0.1 * n; break; }
                case 44: r = 0.36; g = 0.22; b = 0.12; break;
                case 45: { int i = (int) k % 4; double[][] p = {{0.95, 0.15, 0.15}, {1, 0.8, 0.2}, {0.25, 0.55, 1}, {0.85, 0.3, 0.9}}; r = p[i][0]; g = p[i][1]; b = p[i][2]; break; }
                case 46: r = 1; g = 0.78; b = 0.2; e = 0.9; break;
                case 48: { boolean s = ((int) Math.floor(ly * 8 + 100)) % 2 == 0; r = s ? 0.92 : 0.9; g = s ? 0.92 : 0.2; b = s ? 0.92 : 0.2; break; }
                case 49: {
                    r = clamp(0.3 + 0.9 * Math.cos(6.2831 * (k * 0.37)), 0.05, 1);
                    g = clamp(0.3 + 0.9 * Math.cos(6.2831 * (k * 0.37 + 0.33)), 0.05, 1);
                    b = clamp(0.3 + 0.9 * Math.cos(6.2831 * (k * 0.37 + 0.67)), 0.05, 1);
                    e = 1.2; break;
                }
                case 50: {
                    if (k > 0.5) { r = 0.42; g = 0.24; b = 0.12; break; }
                    double gx = Math.abs((lx * 2.4) - Math.floor(lx * 2.4) - 0.5), gy = Math.abs((ly * 2.4) - Math.floor(ly * 2.4) - 0.5);
                    double groove = (Math.max(gx, gy) > 0.44 && Math.abs(lz) > 0.12) ? 0.5 : 0;
                    r = 0.31 * (1 - groove); g = 0.16 * (1 - groove); b = 0.08 * (1 - groove); break;
                }
                case 52: {                                      // TNT block, 16x16 texture
                    double ax = Math.abs(lx), ay = Math.abs(ly), az = Math.abs(lz);
                    int face, px, py;
                    if (ay >= ax && ay >= az) { face = ly > 0 ? 2 : 3; px = cubePix(lx, 0.42); py = cubePix(lz, 0.42); }
                    else if (az >= ax) { face = 0; px = cubePix(lz < 0 ? lx : -lx, 0.42); py = cubePix(-ly, 0.42); }
                    else { face = 1; px = cubePix(lx > 0 ? lz : -lz, 0.42); py = cubePix(-ly, 0.42); }
                    double n = h1(px + (face + 5) * 31, py * 1.7 + face + 5);
                    if (face >= 2) {
                        int qx = px % 4, qy = py % 4;
                        boolean rim = qx == 0 || qy == 0;
                        r = rim ? 0.42 : 0.85; g = rim ? 0.06 : 0.15; b = rim ? 0.05 : 0.12;
                        if (qx == 2 && qy == 2) { r = 0.95; g = 0.86; b = 0.7; }
                        if (face == 3) { r *= 0.6; g *= 0.6; b *= 0.6; }
                    } else {
                        boolean even = (px / 4) % 2 == 0;
                        r = even ? 0.86 : 0.72; g = even ? 0.14 : 0.09; b = even ? 0.11 : 0.08;
                        if (px % 4 == 3) { r *= 0.75; g *= 0.75; b *= 0.75; }
                        if (py == 1 || py == 14) { r = 0.42; g = 0.29; b = 0.16; }
                        if (py == 5 || py == 10) { r = g = b = 0.12; }
                        if (py >= 6 && py <= 9) { boolean yl = (px + py) % 4 < 2; r = yl ? 0.98 : 0.07; g = yl ? 0.8 : 0.07; b = yl ? 0.1 : 0.07; }
                    }
                    double f = 0.9 + 0.2 * n;
                    r = r * f + (1 - r * f) * k * 0.7; g = g * f + (1 - g * f) * k * 0.7; b = b * f + (1 - b * f) * k * 0.7;
                    e = k * 1.4;
                    break;
                }
                case 53: r = 1; g = 0.8; b = 0.3; e = 3; break;
                case 54: {
                    if (k < 0.5) { r = 0.18; g = 0.78; b = 0.7; }
                    else if (k < 1.5) { r = 0.25; g = 0.9; b = 1; e = 0.9; }
                    else if (k < 2.5) { r = 0.16; g = 0.22; b = 0.4; }
                    else { r = 0.12; g = 0.62; b = 0.56; }
                    break;
                }
                case 60: r = 0.72; g = 0.76; b = 0.82; break;                          // saucer
                case 61: r = 0.45; g = 0.8; b = 0.95; e = 0.25; break;                 // dome
                case 62: { boolean on = ((int) (sec * 8 + k)) % 3 == 0; r = 1; g = on ? 0.9 : 0.45; b = on ? 0.3 : 0.7; e = 1.5; break; }
                case 63: {                                      // stolen blocks: grass-ish, stone-ish, wood-ish
                    int px = cubePix(Math.abs(nz) > 0.5 ? lx : lz, 0.25), py = cubePix(-ly, 0.25);
                    double n = h1(px + k * 17, py * 1.3 + k);
                    double[][] pal = {{0.35, 0.65, 0.25}, {0.55, 0.56, 0.6}, {0.62, 0.45, 0.25}};
                    int i = (int) k % 3;
                    double f = 0.8 + 0.35 * n;
                    r = pal[i][0] * f; g = pal[i][1] * f; b = pal[i][2] * f;
                    break;
                }
                case 64: { double ck = ((int) Math.floor(lxW * 2) + (int) Math.floor(lzW * 2)) % 2 == 0 ? 1 : 0.85; r = 0.16 * ck; g = 0.2 * ck; b = 0.16 * ck; break; }
                default: break;
            }
            out[0] = r; out[1] = g; out[2] = b; out[3] = e;
        }

        double lxW, lzW;    // world x/z of the hit (ground checker)

        // ---------------------------------------------------------------- shading
        int shade(int ix, int iy, int w, int h, double[] acc) {
            double u = (ix + 0.5) / w * 2 - 1, v = 1 - (iy + 0.5) / h * 2;
            double aspect = (double) w / h;
            // camera at (0, 0.2, -5.5) looking at (0, 0, 0)
            double rdx = u * aspect * 0.42, rdy = v * 0.42 - 0.03, rdz = 1;
            double rl = len(rdx, rdy, rdz);
            rdx /= rl; rdy /= rl; rdz /= rl;
            double ox = 0, oy = 0.2, oz = -5.5;
            double dist = 0;
            boolean hit = false;
            double glr = 0, glg = 0, glb = 0;
            for (int i = 0; i < 90; i++) {
                double d = map(ox + rdx * dist, oy + rdy * dist, oz + rdz * dist);
                if (mat == 49 || mat == 53 || mat == 46 || mat == 62) {
                    double gw = 0.008 / (0.02 + d * d * 6);
                    if (mat == 49) {            // firework sparks glow in their own colour
                        glr += gw * clamp(0.3 + 0.9 * Math.cos(6.2831 * (k * 0.37)), 0.05, 1);
                        glg += gw * clamp(0.3 + 0.9 * Math.cos(6.2831 * (k * 0.37 + 0.33)), 0.05, 1);
                        glb += gw * clamp(0.3 + 0.9 * Math.cos(6.2831 * (k * 0.37 + 0.67)), 0.05, 1);
                    } else { glr += gw; glg += gw * 0.75; glb += gw * 0.45; }
                }
                if (d < 0.0015 * (1 + dist)) { hit = true; break; }
                dist += d * 0.9;
                if (dist > 14) break;
            }
            // sky: accent-tinted gradient with a few stars
            double sk = 0.5 + 0.5 * v;
            double r = 0.02 + acc[0] * 0.25 * sk + 0.03, g = 0.03 + acc[1] * 0.25 * sk + 0.03, b = 0.08 + acc[2] * 0.25 * sk + 0.06;
            double star = h1(Math.floor(u * 90), Math.floor(v * 60));
            if (star > 0.994) { double tw = 0.5 + 0.5 * Math.sin(sec * 3 + star * 50); r += 0.5 * tw; g += 0.5 * tw; b += 0.55 * tw; }
            if (!hit && "ufo".equals(ev) && rdy < 0) {          // the ground (a plane, intersected directly)
                double tg = (-1.67 - oy) / rdy;
                double gx = ox + rdx * tg, gz = oz + rdz * tg;
                double ck = (((int) Math.floor(gx * 2 + 1000) + (int) Math.floor(gz * 2 + 1000)) % 2 == 0) ? 1 : 0.85;
                double f = clamp((tg - 5) / 6, 0, 1), sh = 1;
                for (int i = 0; i < 3; i++) {                    // soft shadows of the blocks
                    double dx = gx - new double[]{-0.9, 0.0, 0.9}[i], dz = gz;
                    sh = Math.min(sh, clamp(len2(dx, dz) / 0.45, 0.55, 1));
                }
                r = (0.16 * ck * sh) * (1 - f) + (0.02 + acc[0] * 0.12) * f;
                g = (0.2 * ck * sh) * (1 - f) + (0.03 + acc[1] * 0.12) * f;
                b = (0.16 * ck * sh) * (1 - f) + (0.08 + acc[2] * 0.12) * f;
            }
            if (hit) {
                double px = ox + rdx * dist, py = oy + rdy * dist, pz = oz + rdz * dist;
                lxW = px; lzW = pz;
                int m = mat; double kk = k, l1 = lx, l2 = ly, l3 = lz; boolean bt = bitten;
                double e = 0.0012;
                double nx = map(px + e, py - e, pz - e) * 1 + map(px - e, py - e, pz + e) * -1 + map(px - e, py + e, pz - e) * -1 + map(px + e, py + e, pz + e);
                double ny = map(px + e, py - e, pz - e) * -1 + map(px - e, py - e, pz + e) * -1 + map(px - e, py + e, pz - e) + map(px + e, py + e, pz + e);
                double nz = map(px + e, py - e, pz - e) * -1 + map(px - e, py - e, pz + e) + map(px - e, py + e, pz - e) * -1 + map(px + e, py + e, pz + e);
                double nl = len(nx, ny, nz);
                nx /= nl; ny /= nl; nz /= nl;
                mat = m; k = kk; lx = l1; ly = l2; lz = l3; bitten = bt;
                double[] mc = new double[4];
                material(nx, ny, nz, mc);
                double lxd = -0.45, lyd = 0.75, lzd = -0.5, ll = len(lxd, lyd, lzd);
                double dif = Math.max(0, (nx * lxd + ny * lyd + nz * lzd) / ll);
                double amb = 0.32 + 0.18 * ny;
                double rim = Math.pow(1 - Math.max(0, -(nx * rdx + ny * rdy + nz * rdz)), 3) * 0.35;
                double hx = lxd / ll - rdx, hy = lyd / ll - rdy, hz = lzd / ll - rdz, hl = len(hx, hy, hz);
                double spec = Math.pow(Math.max(0, (nx * hx + ny * hy + nz * hz) / hl), 32) * 0.35;
                double lit = dif * 0.85 + amb;
                r = mc[0] * lit + spec + rim * acc[0] + mc[0] * mc[3];
                g = mc[1] * lit + spec + rim * acc[1] + mc[1] * mc[3];
                b = mc[2] * lit + spec + rim * acc[2] + mc[2] * mc[3];
                if (m == 64) {   // fade the ground into the sky
                    double f = clamp((dist - 5) / 6, 0, 1);
                    r = r * (1 - f) + (0.02 + acc[0] * 0.12) * f; g = g * (1 - f) + (0.03 + acc[1] * 0.12) * f; b = b * (1 - f) + (0.08 + acc[2] * 0.12) * f;
                }
            }
            // UFO tractor beam
            if ("ufo".equals(ev) && t > 0.2 && t < 0.8) {
                double ux = Math.sin(t * 40) * 0.02;
                double sx = ox + rdx * 5.5, sy = oy + rdy * 5.5;        // plane z=0
                double half = 0.35 + (1.1 - sy) * 0.35;
                if (sy < 1.0 && sy > -1.7 && Math.abs(sx - ux) < half) {
                    double a = 0.22 * Math.min(1, Math.min((t - 0.2) * 10, (0.8 - t) * 10));
                    double stripe = 0.6 + 0.4 * Math.sin(sy * 25 + sec * 12);
                    r += 0.55 * a * stripe; g += 0.95 * a * stripe; b += 0.25 * a * stripe;
                }
            }
            r += glr; g += glg; b += glb;
            // tone map + gamma
            r = Math.pow(1 - Math.exp(-r * 1.5), 1 / 1.6); g = Math.pow(1 - Math.exp(-g * 1.5), 1 / 1.6); b = Math.pow(1 - Math.exp(-b * 1.5), 1 / 1.6);
            int R = (int) clamp(r * 255, 0, 255), G = (int) clamp(g * 255, 0, 255), B = (int) clamp(b * 255, 0, 255);
            return (R << 16) | (G << 8) | B;
        }
    }
}
