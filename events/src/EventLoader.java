// Event loader: a tiny joke "server" that plays a console animation for a limited-time event and exits.
// One source file, built into a separate jar per event by scripts/build_events.py (the event id is
// stored in /event.txt inside the jar). Java 8 compatible, ASCII only (works in any console code page).

import java.io.InputStream;
import java.io.PrintStream;
import java.util.Locale;

public final class EventLoader {
    static final int W = 64, H = 22;
    static final int FRAMES = 46, FRAME_MS = 95, HOLD_MS = 1800;

    // 256-colour codes (used only when the console understands ANSI escapes)
    static final int ORANGE = 208, YELLOW = 226, GREEN = 34, DARKGREEN = 28, BROWN = 94, RED = 196, PINK = 205,
            WHITE = 15, GREY = 245, CYAN = 51, BLUE = 39, MAGENTA = 201, CHOC = 130, LIME = 118;

    final char[][] ch = new char[H][W];
    final int[][] col = new int[H][W];
    final boolean ansi;
    final PrintStream out = System.out;
    String event;

    EventLoader(String event, boolean ansi) {
        this.event = event;
        this.ansi = ansi;
    }

    public static void main(String[] args) throws Exception {
        String ev = readEvent();
        boolean ascii = false;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--ascii")) ascii = true;
            else if (args[i].equals("--event") && i + 1 < args.length) ev = args[++i];
            else if (args[i].equals("--frames") && i + 1 < args.length) {   // dev: write preview PNGs
                Window3D.frames(ev, args[++i]);
                return;
            }
        }
        String os = System.getProperty("os.name", "").toLowerCase(Locale.ROOT);
        boolean windows = os.contains("win");
        EventLoader el = new EventLoader(ev, !windows || System.getenv("WT_SESSION") != null
                || System.getenv("TERM_PROGRAM") != null);
        // A window with the 3D animation when there is a screen; the console animation otherwise
        if (!ascii && !java.awt.GraphicsEnvironment.isHeadless()) {
            el.out.println("[INFO] Starting " + el.title() + " server");
            el.out.println("[INFO] Opening the 3D window...");
            try {
                Window3D.show(ev, el.title(), el.banner());
                el.out.println("[INFO] " + el.title() + " has finished. See you next event!");
                System.exit(0);
                return;
            } catch (Throwable t) {
                el.out.println("[WARN] No window available (" + t + "), using the console instead");
            }
        }
        el.run(windows);
    }

    String banner() {
        switch (event) {
            case "christmas": return "MERRY CHRISTMAS";
            case "newyear": return "HAPPY NEW YEAR";
            case "valentine": return "HAPPY VALENTINE'S DAY";
            case "aprilfools": return "APRIL FOOLS!";
            case "ufo": return "HAPPY WORLD UFO DAY";
            default: return "HAPPY HALLOWEEN";
        }
    }

    static String readEvent() {
        try (InputStream in = EventLoader.class.getResourceAsStream("/event.txt")) {
            if (in == null) return "halloween";
            byte[] b = new byte[64];
            int n = in.read(b);
            return new String(b, 0, Math.max(0, n), "US-ASCII").trim();
        } catch (Exception e) {
            return "halloween";
        }
    }

    void run(boolean windows) throws Exception {
        String[] boot = {
            "[INFO] Starting " + title() + " server",
            "[INFO] Loading libraries, please wait...",
        };
        for (String s : boot) {
            out.println(s);
            Thread.sleep(350);
        }
        if (ansi) out.print("\033[2J\033[?25l");
        try {
            for (int i = 0; i <= FRAMES; i++) {
                double t = i / (double) FRAMES;
                clear();
                draw(t);
                present(windows);
                Thread.sleep(FRAME_MS);
            }
            Thread.sleep(HOLD_MS);
        } finally {
            if (ansi) out.print("\033[0m\033[?25h");
            out.println();
            out.println("[INFO] " + title() + " has finished. See you next event!");
            out.flush();
        }
    }

    String title() {
        switch (event) {
            case "christmas": return "Jingle Loader";
            case "newyear": return "Firework Loader";
            case "valentine": return "Cocoa Loader";
            case "aprilfools": return "Prank Loader";
            case "ufo": return "UFO Loader";
            default: return "Pumpkin Loader";
        }
    }

    // ------------------------------------------------------------------ canvas
    void clear() {
        for (int y = 0; y < H; y++)
            for (int x = 0; x < W; x++) { ch[y][x] = ' '; col[y][x] = WHITE; }
    }

    void put(int x, int y, char c, int color) {
        if (x >= 0 && y >= 0 && x < W && y < H) { ch[y][x] = c; col[y][x] = color; }
    }

    void text(int x, int y, String s, int color) {
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) != ' ') put(x + i, y, s.charAt(i), color);
    }

    void center(int y, String s, int color) {
        text((W - s.length()) / 2, y, s, color);
    }

    void present(boolean windows) throws Exception {
        StringBuilder sb = new StringBuilder((W + 16) * H * 2);
        if (ansi) {
            sb.append("\033[H");
            int last = -1;
            for (int y = 0; y < H; y++) {
                for (int x = 0; x < W; x++) {
                    if (ch[y][x] != ' ' && col[y][x] != last) {
                        sb.append("\033[38;5;").append(col[y][x]).append('m');
                        last = col[y][x];
                    }
                    sb.append(ch[y][x]);
                }
                sb.append('\n');
            }
        } else {
            if (windows) {
                try { new ProcessBuilder("cmd", "/c", "cls").inheritIO().start().waitFor(); }
                catch (Exception e) { sb.append("\n\n\n\n\n\n\n\n"); }
            }
            for (int y = 0; y < H; y++) {
                sb.append(ch[y]);
                sb.append(System.lineSeparator());
            }
        }
        out.print(sb);
        out.flush();
    }

    // ------------------------------------------------------------------ helpers
    static double seg(double t, double a, double b) { return Math.max(0, Math.min(1, (t - a) / (b - a))); }
    static double easeOut(double x) { x = Math.max(0, Math.min(1, x)); return 1 - Math.pow(1 - x, 3); }
    static double easeOutBack(double x) {
        x = Math.max(0, Math.min(1, x));
        double c1 = 1.70158, c3 = c1 + 1;
        return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
    }
    static double hash(double a, double b) { double s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return s - Math.floor(s); }

    /** Height of a dropped object that bounces (gravity + restitution). tau = time since release (0..1 scale). */
    static double bounce(double tau, double h0) {
        double g = 2 * h0 / (0.35 * 0.35);           // lands after 0.35
        double v = 0, h = h0, tt = tau, dt = 0.004;
        for (double s = 0; s < tt; s += dt) {
            v -= g * dt;
            h += v * dt;
            if (h < 0) { h = 0; v = -v * 0.45; if (Math.abs(v) < 0.5) v = 0; }
        }
        return h;
    }

    void draw(double t) {
        switch (event) {
            case "christmas": christmas(t); break;
            case "newyear": newyear(t); break;
            case "valentine": valentine(t); break;
            case "aprilfools": aprilfools(t); break;
            case "ufo": ufo(t); break;
            default: halloween(t);
        }
    }

    // ------------------------------------------------------------------ Halloween: a pumpkin grows while spinning
    void halloween(double t) {
        double grow = 0.18 + 0.82 * easeOutBack(seg(t, 0, 0.65));
        double ang = (1 - easeOut(seg(t, 0, 0.8))) * Math.PI * 3;     // spins, ends facing the viewer
        double cx = W / 2.0, cy = 10, rx = 19 * grow, ry = 6.8 * grow;
        boolean flicker = ((int) (t * 40)) % 3 == 0;
        for (int y = 0; y < H; y++) {
            for (int x = 0; x < W; x++) {
                double u = (x + 0.5 - cx) / rx, v = (y + 0.5 - cy) / ry;
                double r2 = u * u + v * v * 1.05;
                if (r2 > 1) continue;
                double w = Math.sqrt(Math.max(1e-4, 1 - v * v));
                double lon = Math.asin(Math.max(-1, Math.min(1, u / w)));     // -pi/2..pi/2 visible side
                double rib = Math.cos((lon + ang) * 8);
                char c = rib > 0.55 ? '(' : (rib > -0.1 ? '@' : ')');
                int color = rib > -0.1 ? ORANGE : 166;
                // carved face, attached to the side that faces angle 0
                double fl = lon + ang;
                fl = Math.atan2(Math.sin(fl), Math.cos(fl));
                if (Math.cos(ang) > 0.25 && Math.abs(fl) < 1.2) {
                    double fu = fl / 1.1, fv = v;
                    boolean eye = false;
                    for (int s = -1; s <= 1; s += 2) {
                        double ex = fu - s * 0.42, ey = fv + 0.28;
                        if (ey < 0.16 && ey > -0.14 && Math.abs(ex) < (ey + 0.16) * 0.9) eye = true;   // triangles
                    }
                    boolean nose = Math.abs(fu) < (fv + 0.02) * 0.6 && fv > -0.02 && fv < 0.1;
                    boolean mouth = fv > 0.28 && fv < 0.55 && Math.abs(fu) < 0.62
                            && !(fv < 0.37 && (Math.abs(fu - 0.2) < 0.07 || Math.abs(fu + 0.2) < 0.07))
                            && !(fv > 0.46 && Math.abs(fu) < 0.07);
                    if (eye || nose || mouth) { c = flicker ? '*' : '#'; color = flicker ? 220 : YELLOW; }
                }
                put(x, y, c, color);
            }
        }
        int top = (int) Math.round(cy - ry) - 1;
        if (grow > 0.25) {
            put((int) cx, top, '|', DARKGREEN);
            put((int) cx + 1, top - 1, '/', DARKGREEN);
        }
        if (t > 0.78) center(H - 2, "~  H A P P Y   H A L L O W E E N  ~", t > 0.88 || flicker ? ORANGE : 166);
    }

    // ------------------------------------------------------------------ Christmas: a tree assembles, ornaments drop in
    void christmas(double t) {
        int cx = W / 2, ground = 18;
        double trunk = easeOut(seg(t, 0, 0.14));
        int th = (int) Math.round(3 * trunk);
        for (int y = 0; y < th; y++) text(cx - 2, ground - y, "|##|", BROWN);
        // three cone layers fall into place, bottom first
        int[][] layers = {{ground - 3, 13, 5}, {ground - 7, 10, 5}, {ground - 11, 7, 4}};   // base row, half width, rows
        for (int i = 0; i < 3; i++) {
            double k = easeOutBack(seg(t, 0.14 + i * 0.1, 0.3 + i * 0.1));
            if (k <= 0) continue;
            int off = (int) Math.round((1 - k) * -14);
            int base = layers[i][0] + off, hw = layers[i][1], rows = layers[i][2];
            for (int r = 0; r < rows; r++) {
                int w = (int) Math.round(hw * (0.4 + 0.6 * r / (double) (rows - 1)));
                int y = base - rows + 1 + r;
                for (int x = -w; x <= w; x++) put(cx + x, y, (x + r) % 3 == 0 ? '^' : '*', (x + r) % 4 == 0 ? DARKGREEN : GREEN);
            }
        }
        // ornaments: dropped from the top, they bounce (gravity + restitution) onto the branches
        int[][] orn = {{-9, ground - 4}, {7, ground - 5}, {-4, ground - 6}, {3, ground - 8}, {-6, ground - 9},
                       {5, ground - 10}, {-2, ground - 12}, {1, ground - 3}};
        int[] colors = {RED, YELLOW, BLUE, MAGENTA, CYAN, RED, YELLOW, WHITE};
        for (int i = 0; i < orn.length; i++) {
            double start = 0.48 + i * 0.035;
            if (t < start) continue;
            double tau = (t - start) / 0.62;
            double h = bounce(tau, orn[i][1] + 2);
            put(cx + orn[i][0], (int) Math.round(orn[i][1] - h), 'o', colors[i]);
        }
        if (t > 0.8) {
            boolean tw = ((int) (t * 30)) % 2 == 0;
            put(cx, ground - 15, '*', YELLOW);
            if (tw) { put(cx - 1, ground - 15, '-', YELLOW); put(cx + 1, ground - 15, '-', YELLOW); }
            center(H - 2, "*  M E R R Y   C H R I S T M A S  *", tw ? RED : GREEN);
        }
        // light snow
        for (int i = 0; i < 18; i++) {
            int sx = (int) (hash(i, 1) * W), sy = (int) ((hash(i, 2) * H + t * 30) % (H - 2));
            if (ch[sy][sx] == ' ') put(sx, sy, '.', WHITE);
        }
    }

    // ------------------------------------------------------------------ New year: rockets fly up into the sky and burst
    void newyear(double t) {
        int[] xs = {12, 44, 28, 54, 20};
        int[] ys = {6, 4, 3, 8, 5};
        int[][] pal = {{RED, YELLOW}, {CYAN, BLUE}, {MAGENTA, LIME}, {ORANGE, WHITE}, {LIME, CYAN}};
        for (int i = 0; i < 5; i++) {
            double t0 = 0.02 + i * 0.13;
            double up = seg(t, t0, t0 + 0.14);
            double ex = seg(t, t0 + 0.14, t0 + 0.36);
            int ax = xs[i], ay = ys[i];
            if (up > 0 && up < 1) {
                int y = (int) Math.round(H - 1 - (H - 1 - ay) * easeOut(up));
                put(ax, y, '^', WHITE);
                put(ax, y + 1, '|', GREY);
                put(ax, y + 2, ((int) (t * 60)) % 2 == 0 ? '*' : '.', ORANGE);
            }
            if (ex > 0 && ex < 1) {
                double r = 1 + easeOut(ex) * 6;
                for (int k = 0; k < 20; k++) {
                    double a = k / 20.0 * Math.PI * 2;
                    int x = (int) Math.round(ax + Math.cos(a) * r * 2), y = (int) Math.round(ay + Math.sin(a) * r + ex * ex * 3);
                    put(x, y, ex < 0.5 ? '*' : (ex < 0.8 ? '+' : '.'), pal[i][k % 2]);
                }
            }
        }
        if (t > 0.82) {
            boolean b = ((int) (t * 30)) % 2 == 0;
            center(H - 3, "*  H A P P Y   N E W   Y E A R  *", b ? YELLOW : ORANGE);
        }
    }

    // ------------------------------------------------------------------ Valentine: a heart-shaped chocolate gets bitten
    void valentine(double t) {
        double pop = easeOutBack(seg(t, 0, 0.25));
        double fade = seg(t, 0.8, 0.96);
        double cx = W / 2.0, cy = 10, s = 7.2 * pop;
        double bite = seg(t, 0.42, 0.46);
        for (int y = 0; y < H; y++) {
            for (int x = 0; x < W; x++) {
                if (s < 0.5) continue;
                double u = (x + 0.5 - cx) / (s * 2.1), v = -(y + 0.5 - cy) / s + 0.15;
                double a = u * u + v * v - 1;
                if (a * a * a - u * u * v * v * v > 0) continue;
                // bite: three overlapping circles at the upper right lobe
                if (bite > 0) {
                    boolean bitten = false;
                    for (int k = 0; k < 3; k++) {
                        double bx = 0.95 + 0.12 * (k - 1), byy = 0.85 - 0.25 * (k - 1);
                        double dx = (u - bx) * 1.0, dy = (v - byy);
                        if (dx * dx + dy * dy < 0.11 * bite) bitten = true;
                    }
                    if (bitten) continue;
                }
                if (fade > 0 && hash(x, y) < fade) continue;
                double edge = a * a * a - u * u * v * v * v;
                boolean rim = edge > -0.025;
                boolean grid = !rim && ((x % 6 == 0) || (y % 3 == 0));
                put(x, y, rim ? '%' : (grid ? '+' : '#'), rim ? PINK : (grid ? 94 : CHOC));
            }
        }
        // crumbs fall from the bite
        for (int i = 0; i < 9; i++) {
            double tau = t - 0.45 - i * 0.012;
            if (tau <= 0 || tau > 0.35) continue;
            int x = (int) Math.round(cx + 14 + (hash(i, 3) - 0.3) * 8 + tau * 20 * (hash(i, 4) - 0.2));
            int y = (int) Math.round(cy - 5 + tau * tau * 120);
            put(x, y, i % 2 == 0 ? '.' : ',', CHOC);
        }
        if (t > 0.45 && t < 0.62) text((int) cx + 15, 3, "*CRUNCH*", PINK);
        if (t > 0.86) center(H - 2, "<3  H A P P Y   V A L E N T I N E ' S   D A Y  <3", PINK);
    }

    // ------------------------------------------------------------------ April fools: a TNT box blows the little blocky guy away
    void aprilfools(double t) {
        String[] log = {
            "[INFO] Preparing spawn area: 99%",
            "[INFO] Loading 4,000,000 libraries...",
            "[WARN] Something is ticking...",
        };
        int shown = (int) Math.min(log.length, Math.floor(t / 0.1) + 1);
        for (int i = 0; i < shown; i++) text(2, 1 + i, log[i], i == 2 ? YELLOW : GREY);
        int gx = 40, gy = 15;
        double boom = seg(t, 0.45, 0.6);
        // TNT box with a burning fuse; blinks white faster and faster before going off
        if (t < 0.46) {
            boolean blink = Math.sin(t * t * 300) > 0.3 && t > 0.2;
            int c = blink ? WHITE : RED;
            text(14, 13, "+------+", c);
            text(14, 14, "|######|", c);
            text(14, 15, "|=TNT==|", blink ? RED : WHITE);
            text(14, 16, "|######|", c);
            text(14, 17, "+------+", c);
            put(17 + ((int) (t * 40)) % 2, 12, '*', YELLOW);
        } else if (boom < 1) {
            double r = 2 + boom * 8;
            for (int k = 0; k < 28; k++) {
                double a = k / 28.0 * Math.PI * 2;
                put((int) Math.round(18 + Math.cos(a) * r * 2), (int) Math.round(15 + Math.sin(a) * r),
                        boom < 0.6 ? '#' : '*', k % 2 == 0 ? ORANGE : YELLOW);
            }
            if (boom < 0.7) text(13, 15, "B O O M !", RED);
        }
        // the blocky guy: stands, then flies up and away in an arc, tumbling
        double fly = seg(t, 0.47, 0.82);
        int x = (int) Math.round(gx + fly * 34), y = (int) Math.round(gy - fly * 22 + fly * fly * 10);
        boolean flip = fly > 0 && ((int) (t * 30)) % 2 == 0;
        if (!flip) {
            text(x, y - 2, "[o_o]", CYAN);
            text(x, y - 1, " /|\\", CYAN);
            text(x, y, " / \\", BLUE);
        } else {
            text(x, y - 2, " \\ /", BLUE);
            text(x, y - 1, " \\|/", CYAN);
            text(x, y, "[o_o]", CYAN);
        }
        if (fly > 0.05 && fly < 0.9) text(x - 4, y - 3, "WAAAH!", WHITE);
        if (t > 0.84) center(H - 2, "!!  A P R I L   F O O L S  !!", ((int) (t * 30)) % 2 == 0 ? LIME : MAGENTA);
    }

    // ------------------------------------------------------------------ World UFO day: a UFO steals the menu and spits it back
    void ufo(double t) {
        String[] menu = {"> Server type", "> Version", "> Mods & plugins", "> Settings", "> Install"};
        int mx = 24, my0 = 9;
        double ux;
        if (t < 0.18) ux = -12 + (mx + 6 + 12) * easeOut(t / 0.18);
        else if (t < 0.85) ux = mx + 6 + Math.sin(t * 40) * (t > 0.55 && t < 0.62 ? 1.5 : 0.4);
        else ux = mx + 6 + (t - 0.85) / 0.15 * 50;
        int uy = 2;
        boolean beam = t > 0.2 && t < 0.78;
        for (int i = 0; i < menu.length; i++) {
            double take = easeOut(seg(t, 0.22 + i * 0.05, 0.32 + i * 0.05));
            double give = easeOutBack(seg(t, 0.62 + i * 0.03, 0.74 + i * 0.03));
            double k = take * (1 - give);
            int y = (int) Math.round(my0 + i * 2 - (my0 + i * 2 - uy - 2) * k);
            int x = (int) Math.round(mx + (ux - 2 - mx) * k * 0.5);
            String s = menu[i];
            if (k > 0.85) continue;                                   // inside the UFO
            if (k > 0.4) s = s.substring(0, Math.max(1, (int) (s.length() * (1 - k))));
            text(x, y, s, k > 0.01 ? LIME : WHITE);
        }
        if (beam) {
            for (int y = uy + 3; y < 20; y++) {
                for (int x = -4 - (y - uy) / 3; x <= 4 + (y - uy) / 3; x++) {
                    int px = (int) Math.round(ux) + x;
                    if (px >= 0 && px < W && ch[y][px] == ' ' && (x + y + (int) (t * 30)) % 4 == 0) put(px, y, ':', 120);
                }
            }
        }
        int px = (int) Math.round(ux);
        text(px - 3, uy, "_/^^\\_", GREY);
        text(px - 6, uy + 1, "(=o=O=o=O=)", t > 0.55 && t < 0.62 ? YELLOW : CYAN);
        text(px - 3, uy + 2, "\\____/", GREY);
        if (t > 0.55 && t < 0.62) text(px + 7, uy + 1, "*munch*", YELLOW);
        if (t > 0.64 && t < 0.75) text(px + 7, uy + 1, "*ptooey*", YELLOW);
        if (t > 0.86) center(H - 2, "o  H A P P Y   W O R L D   U F O   D A Y  o", LIME);
    }
}
