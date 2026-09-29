// 로또 추첨기 애니메이션 (canvas, 논리 좌표 300x300)
class LottoMachine {
    // idleMix: 추첨하지 않을 때도 공을 계속 섞을지
    constructor(canvas, { idleMix = true } = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.W = 300;
        this.H = 300;
        this.R = 115;                       // 유리구 반지름
        this.cx = 150;
        this.cy = this.H - 20 - this.R;     // 유리구 중심
        this.r = 11;                        // 공 반지름
        this.tubeTop = 10;
        this.balls = [];
        this.idleMix = idleMix;
        this.mixing = idleMix;
        this.extracting = null;
        this.running = false;
        this.visible = true;
        this.settle = 0;
        this._pending = [];

        this.readColors();
        matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { this.readColors(); this.render(); });
        window.addEventListener('resize', () => { this.resize(); this.render(); });
        // 화면 밖에 있을 때는 애니메이션 정지
        new IntersectionObserver(([entry]) => {
            this.visible = entry.isIntersecting;
            if (this.visible) this.wake();
        }).observe(canvas);
        this.resize();
        this.reset();
        this.wake();
    }

    readColors() {
        const css = getComputedStyle(document.documentElement);
        const v = (name) => css.getPropertyValue(name).trim();
        this.colors = {
            balls: [v('--r1'), v('--r2'), v('--r3'), v('--r4'), v('--r5')],
            glass: v('--surface-2'),
            stroke: v('--border'),
            base: v('--text-2'),
        };
    }

    resize() {
        const dpr = window.devicePixelRatio || 1;
        const w = this.canvas.clientWidth || this.W;
        this.canvas.width = Math.round(w * dpr);
        this.canvas.height = Math.round(w * (this.H / this.W) * dpr);
        this.scale = (w * dpr) / this.W;
    }

    reset() {
        const { cx, cy, R, r } = this;
        this.balls = [];
        for (let n = 1; n <= 45; n++) {
            let x, y;
            do {
                x = cx + (Math.random() - 0.5) * 2 * R;
                y = cy + (Math.random() - 0.1) * R;
            } while (Math.hypot(x - cx, y - cy) > R - r);
            this.balls.push({ n, x, y, vx: 0, vy: 0 });
        }
        this.all = [...this.balls];
    }

    // 지난 추첨에서 꺼낸 공을 배출구 아래로 다시 떨어뜨림
    returnBalls() {
        for (const b of this.all) {
            if (this.balls.includes(b)) continue;
            b.x = this.cx + (Math.random() - 0.5) * 10;
            b.y = this.cy - this.R + this.r + 2;
            b.vx = (Math.random() - 0.5) * 2;
            b.vy = 1;
            this.balls.push(b);
        }
    }

    wake() {
        this.settle = 240;
        if (this.running) return;
        this.running = true;
        const loop = () => {
            this.step();
            this.step();
            this.render();
            if (this.extracting || (this.visible && (this.mixing || this.settle-- > 0))) {
                requestAnimationFrame(loop);
            } else {
                this.running = false;
            }
        };
        requestAnimationFrame(loop);
    }

    step() {
        const { cx, cy, R, r, balls, mixing } = this;
        const damp = mixing ? 0.995 : 0.975;

        for (const b of balls) {
            b.vy += 0.09;
            if (mixing) {
                // 아래쪽에서 불어 올리는 바람
                if (b.y > cy + R * 0.2) b.vy -= Math.random() * 0.55;
                b.vx += (Math.random() - 0.5) * 0.4;
                b.vy += (Math.random() - 0.5) * 0.15;
            }
            b.vx *= damp;
            b.vy *= damp;
            const speed = Math.hypot(b.vx, b.vy);
            if (speed > 6) { b.vx *= 6 / speed; b.vy *= 6 / speed; }
            b.x += b.vx;
            b.y += b.vy;
        }

        // 공끼리 충돌
        const min = r * 2;
        for (let i = 0; i < balls.length; i++) {
            const a = balls[i];
            for (let j = i + 1; j < balls.length; j++) {
                const b = balls[j];
                const dx = b.x - a.x, dy = b.y - a.y;
                const d2 = dx * dx + dy * dy;
                if (d2 >= min * min || d2 === 0) continue;
                const d = Math.sqrt(d2), nx = dx / d, ny = dy / d;
                const push = (min - d) / 2;
                a.x -= nx * push; a.y -= ny * push;
                b.x += nx * push; b.y += ny * push;
                const rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
                if (rv < 0) {
                    const imp = -1.85 * rv / 2;
                    a.vx -= imp * nx; a.vy -= imp * ny;
                    b.vx += imp * nx; b.vy += imp * ny;
                }
            }
        }

        // 유리벽 충돌
        for (const b of balls) {
            const dx = b.x - cx, dy = b.y - cy;
            const d = Math.hypot(dx, dy);
            if (d <= R - r) continue;
            const nx = dx / d, ny = dy / d;
            b.x = cx + nx * (R - r);
            b.y = cy + ny * (R - r);
            const vn = b.vx * nx + b.vy * ny;
            if (vn > 0) { b.vx -= 1.8 * vn * nx; b.vy -= 1.8 * vn * ny; }
        }

        // 선택된 공이 위쪽 관으로 빠져나감
        const ex = this.extracting;
        if (ex) {
            ex.t = Math.min(1, ex.t + 1 / 60);
            const exitY = cy - R + r;
            const ease = (t) => 1 - Math.pow(1 - t, 3);
            if (ex.t < 0.6) {
                const k = ease(ex.t / 0.6);
                ex.x = ex.x0 + (cx - ex.x0) * k;
                ex.y = ex.y0 + (exitY - ex.y0) * k;
            } else {
                ex.x = cx;
                ex.y = exitY + (this.tubeTop + r - exitY) * ((ex.t - 0.6) / 0.4);
            }
            if (ex.t >= 1) this._finishExtract();
        }
    }

    ballColor(n) {
        return this.colors.balls[n <= 10 ? 0 : n <= 20 ? 1 : n <= 30 ? 2 : n <= 40 ? 3 : 4];
    }

    paintBall(x, y, r, n) {
        const ctx = this.ctx;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = this.ballColor(n);
        ctx.fill();
        const g = ctx.createRadialGradient(x - r * 0.4, y - r * 0.4, r * 0.1, x, y, r);
        g.addColorStop(0, 'rgba(255,255,255,.55)');
        g.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = g;
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = `700 ${Math.round(r * 0.95)}px 'Pretendard Variable', sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(n, x, y + r * 0.05);
    }

    render() {
        const { ctx, cx, cy, R, r, colors } = this;
        ctx.setTransform(this.scale, 0, 0, this.scale, 0, 0);
        ctx.clearRect(0, 0, this.W, this.H);

        // 받침대
        ctx.fillStyle = colors.base;
        ctx.globalAlpha = 0.35;
        ctx.beginPath();
        ctx.moveTo(cx - 45, cy + R - 4);
        ctx.lineTo(cx + 45, cy + R - 4);
        ctx.lineTo(cx + 70, this.H - 2);
        ctx.lineTo(cx - 70, this.H - 2);
        ctx.closePath();
        ctx.fill();
        ctx.globalAlpha = 1;

        // 배출관
        const tw = r + 4;
        ctx.fillStyle = colors.glass;
        ctx.strokeStyle = colors.stroke;
        ctx.lineWidth = 2;
        ctx.fillRect(cx - tw, this.tubeTop, tw * 2, cy - R - this.tubeTop + 4);
        ctx.strokeRect(cx - tw, this.tubeTop, tw * 2, cy - R - this.tubeTop + 4);

        // 유리구 안쪽
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.globalAlpha = 0.6;
        ctx.fill();
        ctx.globalAlpha = 1;

        for (const b of this.balls) this.paintBall(b.x, b.y, r, b.n);

        // 유리 테두리와 반사광
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(cx, cy, R - 12, Math.PI * 1.1, Math.PI * 1.4);
        ctx.strokeStyle = 'rgba(255,255,255,.6)';
        ctx.lineWidth = 5;
        ctx.lineCap = 'round';
        ctx.stroke();

        const ex = this.extracting;
        if (ex) this.paintBall(ex.x, ex.y, r * 1.1, ex.n);
    }

    wait(ms) {
        return new Promise((resolve) => {
            const t = setTimeout(resolve, ms);
            this._pending.push(() => { clearTimeout(t); resolve(); });
        });
    }

    _removeBall(n) {
        const i = this.balls.findIndex((b) => b.n === n);
        return i >= 0 ? this.balls.splice(i, 1)[0] : null;
    }

    extract(n) {
        const b = this._removeBall(n);
        if (!b) return Promise.resolve();
        return new Promise((resolve) => {
            this.extracting = { n, t: 0, x0: b.x, y0: b.y, x: b.x, y: b.y, resolve };
        });
    }

    _finishExtract() {
        const ex = this.extracting;
        this.extracting = null;
        if (ex) ex.resolve();
    }

    async run(numbers, onBall) {
        this.skipped = false;
        this.returnBalls();
        this.mixing = true;
        this.wake();
        await this.wait(this.idleMix ? 1000 : 1400);
        for (const n of numbers) {
            if (!this.skipped) {
                await this.extract(n);
                if (!this.skipped) await this.wait(250);
            } else {
                this._removeBall(n);
            }
            onBall(n);
        }
        this.mixing = this.idleMix;
        this.wake();
    }

    skip() {
        this.skipped = true;
        this._pending.splice(0).forEach((f) => f());
        this._finishExtract();
    }
}
