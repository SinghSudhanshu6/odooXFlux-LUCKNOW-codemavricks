(function () {
  const el = document.getElementById("scene");
  if (!el || typeof THREE === "undefined") return;
  const hero = document.body.dataset.scene === "hero";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas: el, alpha: true, antialias: true }); } catch (e) { return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(0, 0, hero ? 7 : 9);
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const l1 = new THREE.PointLight(0x7c6cff, 2.2, 40); l1.position.set(4, 3, 5); scene.add(l1);
  const l2 = new THREE.PointLight(0x3de0a5, 1.8, 40); l2.position.set(-5, -2, 4); scene.add(l2);

  const group = new THREE.Group(); scene.add(group);

  // the "billing loop": a knot at the centre, coins orbiting on tilted rings
  let knot;
  if (hero) {
    knot = new THREE.Mesh(
      new THREE.TorusKnotGeometry(0.9, 0.27, 200, 24, 2, 3),
      new THREE.MeshStandardMaterial({ color: 0x7c6cff, metalness: 0.65, roughness: 0.22, emissive: 0x1d1760 }));
    group.add(knot);
  }
  const orbits = [];
  const specs = [[2.3, 0.9, 0.2, 0.004, 3], [3.1, -0.6, 0.5, -0.003, 4], [3.9, 0.25, -0.7, 0.002, 5]];
  specs.forEach(([r, rx, ry, speed, n], i) => {
    const tilt = new THREE.Group(); tilt.rotation.set(rx, ry, 0);
    tilt.add(new THREE.Mesh(new THREE.TorusGeometry(r, 0.01, 8, 160),
      new THREE.MeshBasicMaterial({ color: i % 2 ? 0x3de0a5 : 0x7c6cff, transparent: true, opacity: 0.55 })));
    const pivot = new THREE.Group(); tilt.add(pivot);
    for (let k = 0; k < n; k++) {
      const a = (k / n) * Math.PI * 2;
      const coin = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.26, 0.06, 36),
        new THREE.MeshStandardMaterial({ color: 0xffb547, metalness: 0.85, roughness: 0.25, emissive: 0x3a2400 }));
      coin.position.set(Math.cos(a) * r, Math.sin(a) * r, 0);
      coin.rotation.x = Math.PI / 2;
      pivot.add(coin);
    }
    group.add(tilt); orbits.push({ pivot, speed, tilt, baseZ: 0 });
  });
  const pts = new Float32Array(600 * 3);
  for (let i = 0; i < pts.length; i++) pts[i] = (Math.random() - 0.5) * 22;
  const dustGeo = new THREE.BufferGeometry(); dustGeo.setAttribute("position", new THREE.BufferAttribute(pts, 3));
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({ size: 0.025, color: 0x9aa3ff, transparent: true, opacity: 0.7 }));
  scene.add(dust);

  function layout() {
    const w = innerWidth, h = innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    const wide = w > 900;
    group.position.x = hero ? (wide ? 2.6 : 0) : (wide ? 3.4 : 0);
    group.position.y = hero && !wide ? -1.4 : 0;
    group.scale.setScalar(hero ? (wide ? 1 : 0.75) : 0.9);
  }
  addEventListener("resize", layout); layout();

  let mx = 0, my = 0;
  addEventListener("pointermove", (e) => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; });
  const clock = new THREE.Clock();
  function frame() {
    const t = clock.getElapsedTime();
    orbits.forEach((o, i) => { o.pivot.rotation.z += o.speed * 3; o.tilt.rotation.z = Math.sin(t * 0.2 + i) * 0.15; });
    if (knot) { knot.rotation.x = t * 0.25; knot.rotation.y = t * 0.35; }
    group.rotation.y += (mx * 0.8 - group.rotation.y) * 0.04;
    group.rotation.x += (my * 0.5 - group.rotation.x) * 0.04;
    dust.rotation.y = t * 0.01;
    renderer.render(scene, camera);
    if (!reduce) requestAnimationFrame(frame);
  }
  frame();
})();
