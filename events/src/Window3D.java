// The window that plays an event loader's 3D animation (about 5 seconds) and then closes.

import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
import javax.swing.JFrame;
import javax.swing.JPanel;
import javax.swing.SwingUtilities;
import javax.swing.WindowConstants;

final class Window3D {
    static final int RW = 256, RH = 160;            // render resolution (scaled up: chunky pixels)
    static final double ANIM_SEC = 5.0, HOLD_SEC = 1.4;

    static void show(String event, String title, String banner) throws Exception {
        Scene3D scene = new Scene3D(event, RW, RH);
        BufferedImage img = new BufferedImage(RW, RH, BufferedImage.TYPE_INT_RGB);
        final double[] state = {0, 0};               // t, seconds
        JPanel panel = new JPanel() {
            @Override
            protected void paintComponent(Graphics g0) {
                Graphics2D g = (Graphics2D) g0;
                g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_NEAREST_NEIGHBOR);
                synchronized (img) {
                    g.drawImage(img, 0, 0, getWidth(), getHeight(), null);
                }
                g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
                g.setFont(new Font(Font.MONOSPACED, Font.BOLD, 14));
                g.setColor(new Color(255, 255, 255, 170));
                g.drawString(title, 14, 24);
                double t = state[0];
                if (t > 0.8) {
                    int a = (int) Math.min(255, (t - 0.8) / 0.08 * 255);
                    g.setFont(new Font(Font.MONOSPACED, Font.BOLD, Math.max(18, getWidth() / 22)));
                    FontMetrics fm = g.getFontMetrics();
                    int x = (getWidth() - fm.stringWidth(banner)) / 2, y = getHeight() - fm.getHeight();
                    g.setColor(new Color(0, 0, 0, a / 2));
                    g.drawString(banner, x + 3, y + 3);
                    g.setColor(new Color(255, 240, 200, a));
                    g.drawString(banner, x, y);
                }
            }
        };
        panel.setPreferredSize(new Dimension(800, 500));
        panel.setBackground(Color.BLACK);
        final JFrame[] frame = new JFrame[1];
        SwingUtilities.invokeAndWait(() -> {
            JFrame f = new JFrame(title);
            f.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
            f.setContentPane(panel);
            f.pack();
            f.setLocationRelativeTo(null);
            f.setVisible(true);
            frame[0] = f;
        });
        long start = System.nanoTime();
        BufferedImage work = new BufferedImage(RW, RH, BufferedImage.TYPE_INT_RGB);
        while (frame[0].isDisplayable()) {
            double sec = (System.nanoTime() - start) / 1e9;
            double t = Math.min(1, sec / ANIM_SEC);
            // these scenes fade out at the very end in the installer; here they stay up for the banner
            boolean keep = event.equals("halloween") || event.equals("christmas") || event.equals("aprilfools");
            scene.render(keep ? Math.min(t, 0.9) : t, sec, work);
            synchronized (img) {
                img.getGraphics().drawImage(work, 0, 0, null);
            }
            state[0] = t;
            state[1] = sec;
            panel.repaint();
            if (sec > ANIM_SEC + HOLD_SEC) break;
            Thread.sleep(5);
        }
        SwingUtilities.invokeAndWait(() -> frame[0].dispose());
    }

    /** Dev helper: write 6 preview frames as PNG (works without a screen). */
    static void frames(String event, String dir) throws Exception {
        Scene3D scene = new Scene3D(event, RW, RH);
        new File(dir).mkdirs();
        double[] ts = {0.1, 0.3, 0.45, 0.6, 0.75, 0.9};
        long t0 = System.nanoTime();
        for (double t : ts) {
            BufferedImage img = new BufferedImage(RW, RH, BufferedImage.TYPE_INT_RGB);
            scene.render(t, t * ANIM_SEC, img);
            ImageIO.write(img, "png", new File(dir, event + "_" + (int) (t * 100) + ".png"));
        }
        System.out.printf("%s: %.1f ms/frame%n", event, (System.nanoTime() - t0) / 1e6 / ts.length);
    }
}
