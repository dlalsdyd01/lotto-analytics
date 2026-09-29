// 3D 로또 추첨기 (Three.js)
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const R = 2;          // 유리구 반지름
const r = 0.27;       // 공 반지름
const TUBE_H = 1.3;   // 배출관 길이
const COLORS = ['#fbc400', '#69c8f2', '#ff7272', '#aaaaaa', '#b0d840'];
const colorOf = (n) => COLORS[n <= 10 ? 0 : n <= 20 ? 1 : n <= 30 ? 2 : n <= 40 ? 3 : 4];

// 물리 상수 (프레임당 2스텝 기준)
// 바닥 근처 공을 스텝마다 JET_PROB 확률로 세게 차올려 유리구 전체로 튀게 함
const GRAVITY = 0.0016, JET = 0.14, JET_PROB = 0.05, JITTER = 0.0075, MAX_V = 0.2;

function ballTexture(n) {
    const c = document.createElement('canvas');
    c.width = 512;
    c.height = 256;
    const g = c.getContext('2d');
    g.fillStyle = colorOf(n);
    g.fillRect(0, 0, 512, 256);
    // 앞뒤 양면에 번호 인쇄 (u=0.25가 카메라 쪽)
    for (const x of [128, 384]) {
        g.beginPath();
        g.arc(x, 128, 54, 0, Math.PI * 2);
        g.fillStyle = '#fff';
        g.fill();
        g.fillStyle = '#1d1f24';
        g.font = "800 64px 'Pretendard Variable', sans-serif";
        g.textAlign = 'center';
        g.textBaseline = 'middle';
        g.fillText(n, x, 132);
        if (n === 6 || n === 9) g.fillRect(x - 13, 166, 26, 5);
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 4;
    return t;
}

const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

export class LottoMachine3D {
    static async create(canvas, options) {
        try { await document.fonts.load("800 64px 'Pretendard Variable'"); } catch (_) { /* 기본 폰트 사용 */ }
        return new LottoMachine3D(canvas, options);
    }

    // idleMix: 추첨하지 않을 때도 공을 계속 섞을지
    constructor(canvas, { idleMix = true } = {}) {
        this.canvas = canvas;
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        this.renderer.toneMapping = THREE.NeutralToneMapping;

        this.scene = new THREE.Scene();
        const pmrem = new THREE.PMREMGenerator(this.renderer);
        this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

        this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50);
        this.camera.position.set(0, 0.8, 10.6);
        this.camera.lookAt(0, 0.1, 0);

        const key = new THREE.DirectionalLight(0xffffff, 1.3);
        key.position.set(3, 5, 4);
        // 뒤쪽 보라빛 림 라이트로 어두운 배경에서 유리 윤곽을 살림
        const rim = new THREE.DirectionalLight(0x8f7cff, 1.1);
        rim.position.set(-4, 2, -5);
        const warm = new THREE.PointLight(0xffd27a, 6, 12);
        warm.position.set(2.5, -1, 3);
        this.scene.add(key, rim, warm, new THREE.AmbientLight(0xffffff, 0.35));

        this.balls = [];
        this.idleMix = idleMix;
        this.mixing = idleMix;
        this.extracting = null;
        this.running = false;
        this.visible = true;
        this.settle = 0;
        this.time = 0;
        this._pending = [];

        this.buildMachine();
        this.buildBalls();
        this.reset();

        new ResizeObserver(() => { this.resize(); this.render(); }).observe(canvas);
        // 화면 밖에 있을 때는 애니메이션 정지
        new IntersectionObserver(([entry]) => {
            this.visible = entry.isIntersecting;
            if (this.visible) this.wake();
        }).observe(canvas);
        this.resize();
        this.wake();
    }

    buildMachine() {
        const glass = new THREE.MeshPhysicalMaterial({
            color: 0xffffff, metalness: 0, roughness: 0.03,
            transparent: true, opacity: 0.08,
            clearcoat: 1, clearcoatRoughness: 0.05,
            envMapIntensity: 1.2, side: THREE.DoubleSide, depthWrite: false,
        });
        const metal = new THREE.MeshStandardMaterial({ color: 0xa3abb9, metalness: 0.9, roughness: 0.25 });
        const dark = new THREE.MeshStandardMaterial({ color: 0x2b2f3a, metalness: 0.6, roughness: 0.4 });

        const sphere = new THREE.Mesh(new THREE.SphereGeometry(R, 64, 48), glass);
        sphere.renderOrder = 2;

        const tubeR = r + 0.08;
        const tube = new THREE.Mesh(new THREE.CylinderGeometry(tubeR, tubeR, TUBE_H, 32, 1, true), glass);
        tube.position.y = R - 0.05 + TUBE_H / 2;
        tube.renderOrder = 2;

        const lip = new THREE.Mesh(new THREE.TorusGeometry(tubeR, 0.04, 12, 32), metal);
        lip.rotation.x = Math.PI / 2;
        lip.position.y = R - 0.05 + TUBE_H;

        const equator = new THREE.Mesh(new THREE.TorusGeometry(R + 0.02, 0.035, 12, 96), metal);
        equator.rotation.x = Math.PI / 2;

        const collar = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.07, 12, 48), metal);
        collar.rotation.x = Math.PI / 2;
        collar.position.y = -R + 0.12;

        const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.8, 0.5, 48), metal);
        neck.position.y = -R - 0.15;

        const base = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.7, 0.35, 64), dark);
        base.position.y = -R - 0.55;

        this.scene.add(sphere, tube, lip, equator, collar, neck, base);
    }

    buildBalls() {
        const geo = new THREE.SphereGeometry(r, 32, 20);
        this.group = new THREE.Group();
        this.scene.add(this.group);
        this.all = [];
        for (let n = 1; n <= 45; n++) {
            const mat = new THREE.MeshStandardMaterial({ map: ballTexture(n), roughness: 0.35, metalness: 0 });
            const mesh = new THREE.Mesh(geo, mat);
            this.all.push({ n, mesh, p: mesh.position, v: new THREE.Vector3() });
        }
    }

    reset() {
        this.group.clear();
        this.balls = [...this.all];
        for (const b of this.balls) {
            do {
                b.p.set((Math.random() - 0.5) * 2 * R, -Math.random() * R, (Math.random() - 0.5) * 2 * R);
            } while (b.p.length() > R - r - 0.05);
            b.v.set(0, 0, 0);
            b.mesh.scale.setScalar(1);
            b.mesh.material.opacity = 1;
            b.mesh.material.transparent = false;
            b.mesh.quaternion.setFromEuler(new THREE.Euler(Math.random() * 6, Math.random() * 6, Math.random() * 6));
            this.group.add(b.mesh);
        }
    }

    // 지난 추첨에서 꺼낸 공을 배출관 아래로 다시 떨어뜨림
    returnBalls() {
        for (const b of this.all) {
            if (this.balls.includes(b)) continue;
            b.p.set((Math.random() - 0.5) * 0.2, R - r - 0.1, (Math.random() - 0.5) * 0.2);
            b.v.set((Math.random() - 0.5) * 0.04, -0.05, (Math.random() - 0.5) * 0.04);
            b.mesh.material.opacity = 1;
            b.mesh.material.transparent = false;
            this.balls.push(b);
            this.group.add(b.mesh);
        }
    }

    resize() {
        const w = this.canvas.clientWidth || 300;
        this.renderer.setSize(w, w, false);
        this.camera.aspect = 1;
        this.camera.updateProjectionMatrix();
    }

    wake() {
        this.settle = 240;
        if (this.running) return;
        this.running = true;
        const loop = () => {
            this.step();
            this.step();
            this.animateExtract();
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
        const { balls, mixing } = this;
        const damp = mixing ? 0.995 : 0.975;
        const lim = R - r - 0.03;

        for (const b of balls) {
            const v = b.v;
            v.y -= GRAVITY;
            if (mixing) {
                if (b.p.y < -R * 0.2 && Math.random() < JET_PROB) v.y += JET * (0.6 + 0.4 * Math.random());
                v.x += (Math.random() - 0.5) * JITTER;
                v.z += (Math.random() - 0.5) * JITTER;
                v.y += (Math.random() - 0.5) * JITTER * 0.4;
            }
            v.multiplyScalar(damp);
            if (v.length() > MAX_V) v.setLength(MAX_V);
            b.p.add(v);
        }

        // 공끼리 충돌
        const min = r * 2;
        for (let i = 0; i < balls.length; i++) {
            const a = balls[i];
            for (let j = i + 1; j < balls.length; j++) {
                const b = balls[j];
                const dx = b.p.x - a.p.x, dy = b.p.y - a.p.y, dz = b.p.z - a.p.z;
                const d2 = dx * dx + dy * dy + dz * dz;
                if (d2 >= min * min || d2 === 0) continue;
                const d = Math.sqrt(d2), nx = dx / d, ny = dy / d, nz = dz / d;
                const push = (min - d) / 2;
                a.p.x -= nx * push; a.p.y -= ny * push; a.p.z -= nz * push;
                b.p.x += nx * push; b.p.y += ny * push; b.p.z += nz * push;
                const rv = (b.v.x - a.v.x) * nx + (b.v.y - a.v.y) * ny + (b.v.z - a.v.z) * nz;
                if (rv < 0) {
                    const imp = -1.85 * rv / 2;
                    a.v.x -= imp * nx; a.v.y -= imp * ny; a.v.z -= imp * nz;
                    b.v.x += imp * nx; b.v.y += imp * ny; b.v.z += imp * nz;
                }
            }
        }

        // 유리벽 충돌 + 굴러가는 회전
        const axis = new THREE.Vector3();
        for (const b of balls) {
            const d = b.p.length();
            if (d > lim) {
                const n = b.p.clone().divideScalar(d);
                b.p.copy(n).multiplyScalar(lim);
                const vn = b.v.dot(n);
                if (vn > 0) b.v.addScaledVector(n, -1.8 * vn);
            }
            axis.set(b.v.z, 0, -b.v.x);
            const speed = axis.length();
            if (speed > 1e-5) b.mesh.rotateOnWorldAxis(axis.divideScalar(speed), speed / r);
        }
    }

    animateExtract() {
        const ex = this.extracting;
        if (!ex) return;
        ex.t = Math.min(1, ex.t + 1 / 55);
        const { mesh } = ex.ball;
        const top = new THREE.Vector3(0, R - r - 0.1, 0);
        const tubeEnd = new THREE.Vector3(0, R + TUBE_H + 0.15, 0);
        const out = new THREE.Vector3(0, R + 0.2, 5.5);

        if (ex.t < 0.4) {
            mesh.position.lerpVectors(ex.from, top, ease(ex.t / 0.4));
        } else if (ex.t < 0.65) {
            mesh.position.lerpVectors(top, tubeEnd, (ex.t - 0.4) / 0.25);
        } else {
            const k = ease((ex.t - 0.65) / 0.35);
            mesh.position.lerpVectors(tubeEnd, out, k);
            mesh.material.transparent = true;
            mesh.material.opacity = 1 - Math.max(0, (k - 0.6) / 0.4);
        }
        // 번호가 카메라를 보도록 회전
        mesh.quaternion.slerp(new THREE.Quaternion(), Math.min(1, ex.t * 2.5));

        if (ex.t >= 1) this._finishExtract();
    }

    render() {
        if (this.mixing || this.extracting) this.time += 1 / 60;
        this.camera.position.x = Math.sin(this.time * 0.35) * 1.4;
        this.camera.lookAt(0, 0.1, 0);
        this.renderer.render(this.scene, this.camera);
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
        const ball = this._removeBall(n);
        if (!ball) return Promise.resolve();
        return new Promise((resolve) => {
            this.extracting = { ball, t: 0, from: ball.p.clone(), resolve };
        });
    }

    _finishExtract() {
        const ex = this.extracting;
        this.extracting = null;
        if (!ex) return;
        this.group.remove(ex.ball.mesh);
        ex.resolve();
    }

    async run(numbers, onBall) {
        this.skipped = false;
        this.returnBalls();
        this.mixing = true;
        this.wake();
        await this.wait(this.idleMix ? 1000 : 1600);
        for (const n of numbers) {
            if (!this.skipped) {
                await this.extract(n);
                if (!this.skipped) await this.wait(200);
            } else {
                const b = this._removeBall(n);
                if (b) this.group.remove(b.mesh);
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
