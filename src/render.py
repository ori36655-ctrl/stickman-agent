import math
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DURATION = 720, 1280, 30, 6.0
GROUND_Y = 900
HIP_Y = GROUND_Y - 120
TORSO, HEAD_R, UPPER, FORE, THIGH, SHIN = 110, 28, 50, 50, 60, 60
BG = (245, 245, 240)
INK = (25, 25, 25)

POSES = {
    "idle": dict(lean=5, af_u=30, af_f=120, ab_u=15, ab_f=110, lf_u=20, lf_l=5, lb_u=-20, lb_l=-5),
    "punch": dict(lean=18, af_u=90, af_f=90, ab_u=10, ab_f=130, lf_u=45, lf_l=10, lb_u=-35, lb_l=-10),
    "kick": dict(lean=-12, af_u=20, af_f=120, ab_u=-20, ab_f=100, lf_u=90, lf_l=90, lb_u=-5, lb_l=-5),
    "hit": dict(lean=-25, af_u=-40, af_f=-20, ab_u=-60, ab_f=-30, lf_u=10, lf_l=0, lb_u=-35, lb_l=-25),
    "ko": dict(lean=-85, af_u=-120, af_f=-100, ab_u=-100, ab_f=-90, lf_u=-75, lf_l=-75, lb_u=-80, lb_l=-85),
}

# (זמן, תנוחה, מיקום x, הזזה למטה)
TRACKS = {
    "A": [(0.0, "idle", 200, 0), (1.0, "idle", 200, 0), (1.9, "punch", 380, 0),
          (2.3, "punch", 380, 0), (3.0, "idle", 250, 0), (3.5, "idle", 250, 0),
          (4.0, "kick", 380, 0), (4.4, "kick", 380, 0), (5.0, "idle", 300, 0),
          (6.0, "idle", 300, 0)],
    "B": [(0.0, "idle", 520, 0), (1.9, "idle", 520, 0), (2.15, "hit", 555, 0),
          (2.9, "idle", 540, 0), (3.9, "idle", 540, 0), (4.15, "hit", 600, 0),
          (4.7, "ko", 640, 85), (6.0, "ko", 640, 85)],
}
BURSTS = [(1.95, 2.3), (4.05, 4.4)]


def lerp(a, b, t):
    return a + (b - a) * t


def eval_track(track, t):
    if t <= track[0][0]:
        k = track[0]
        return POSES[k[1]], k[2], k[3]
    for (t0, p0, x0, y0), (t1, p1, x1, y1) in zip(track, track[1:]):
        if t0 <= t < t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            pose = {k: lerp(POSES[p0][k], POSES[p1][k], u) for k in POSES[p0]}
            return pose, lerp(x0, x1, u), lerp(y0, y1, u)
    k = track[-1]
    return POSES[k[1]], k[2], k[3]


def limb(p, angle_deg, length, facing):
    a = math.radians(angle_deg)
    return (p[0] + math.sin(a) * length * facing, p[1] + math.cos(a) * length)


def seg(d, a, b, w=10):
    d.line([a, b], fill=INK, width=w)
    for p in (a, b):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=INK)


def draw_fighter(d, x, dy, pose, facing, color):
    hip = (x, HIP_Y + dy)
    lean = math.radians(pose["lean"])
    dirx, diry = math.sin(lean) * facing, -math.cos(lean)
    neck = (hip[0] + dirx * TORSO, hip[1] + diry * TORSO)
    shoulder = (hip[0] + dirx * TORSO * 0.85, hip[1] + diry * TORSO * 0.85)
    head = (neck[0] + dirx * (HEAD_R + 4), neck[1] + diry * (HEAD_R + 4))
    seg(d, hip, neck)
    for up, lo in (("lb_u", "lb_l"), ("lf_u", "lf_l")):
        knee = limb(hip, pose[up], THIGH, facing)
        seg(d, hip, knee)
        seg(d, knee, limb(knee, pose[lo], SHIN, facing))
    for up, lo in (("ab_u", "ab_f"), ("af_u", "af_f")):
        elbow = limb(shoulder, pose[up], UPPER, facing)
        seg(d, shoulder, elbow)
        seg(d, elbow, limb(elbow, pose[lo], FORE, facing))
    d.ellipse([head[0] - HEAD_R, head[1] - HEAD_R, head[0] + HEAD_R, head[1] + HEAD_R],
              fill=color, outline=INK, width=6)


def draw_burst(d, cx, cy, r):
    pts = []
    for i in range(12):
        ang = math.pi * 2 * i / 12
        rad = r if i % 2 == 0 else r * 0.5
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    d.polygon(pts, fill=(255, 210, 0), outline=INK)


def draw_frame(t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, GROUND_Y, W, H], fill=(225, 225, 215))
    d.line([0, GROUND_Y, W, GROUND_Y], fill=INK, width=6)
    bob = 3 * math.sin(t * 6)
    xs = {}
    for name, facing, color in (("A", 1, (60, 120, 220)), ("B", -1, (220, 70, 70))):
        pose, x, dy = eval_track(TRACKS[name], t)
        xs[name] = x
        draw_fighter(d, x, dy + (bob if dy < 1 else 0), pose, facing, color)
    for start, end in BURSTS:
        if start <= t <= end:
            r = 50 + 30 * (t - start) / (end - start)
            draw_burst(d, xs["B"] - 20, HIP_Y - 90, r)
    if t >= 4.8:
        font = ImageFont.load_default(size=160)
        d.text((W // 2, 300), "K.O.", font=font, fill=(200, 30, 30), anchor="mm")
    return img


def main():
    os.makedirs("out", exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-preset", "veryfast", "out/fight.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DURATION * FPS)
    for i in range(total):
        p.stdin.write(draw_frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
    print("done", total, "frames")


if __name__ == "__main__":
    main()
