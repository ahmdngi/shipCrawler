/* Rotating Globe — Three.js particle globe for dashboard right panel */
(function() {
  if (typeof THREE === 'undefined') return;

  const container = document.getElementById('globe-container');
  if (!container) return;

  const W = container.clientWidth || 240;
  const H = 200;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 1000);
  camera.position.z = 3.2;

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  // ─── Globe (Points) ───
  const globeRadius = 1.4;
  const pointsCount = 1800;
  const positions = new Float32Array(pointsCount * 3);
  const colors = new Float32Array(pointsCount * 3);

  for (let i = 0; i < pointsCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = globeRadius + (Math.random() - 0.5) * 0.04;
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.cos(phi);
    positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);

    const bright = 0.4 + Math.random() * 0.6;
    colors[i * 3] = 0.3 * bright;
    colors[i * 3 + 1] = 0.55 * bright;
    colors[i * 3 + 2] = 1.0 * bright;
  }

  const globeGeo = new THREE.BufferGeometry();
  globeGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  globeGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const globeMat = new THREE.PointsMaterial({
    size: 0.035,
    vertexColors: true,
    transparent: true,
    opacity: 0.95,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const globe = new THREE.Points(globeGeo, globeMat);
  scene.add(globe);

  // ─── Grid Lines (lat/lon style) ───
  const ringMat = new THREE.LineBasicMaterial({
    color: 0x3273ff,
    transparent: true,
    opacity: 0.12,
  });

  for (let i = 0; i < 6; i++) {
    const lat = (i / 6) * Math.PI - Math.PI / 2 + Math.PI / 12;
    const rLat = globeRadius * Math.cos(lat) * 1.01;
    const y = globeRadius * Math.sin(lat) * 1.01;
    const segments = 48;
    const ringPos = [];
    for (let j = 0; j <= segments; j++) {
      const theta = (j / segments) * Math.PI * 2;
      ringPos.push(rLat * Math.cos(theta), y, rLat * Math.sin(theta));
    }
    const ringGeo = new THREE.BufferGeometry();
    ringGeo.setAttribute('position', new THREE.Float32BufferAttribute(ringPos, 3));
    scene.add(new THREE.Line(ringGeo, ringMat));
  }

  for (let i = 0; i < 4; i++) {
    const theta = (i / 4) * Math.PI;
    const ringPos = [];
    const segments = 48;
    for (let j = 0; j <= segments; j++) {
      const phi = (j / segments) * Math.PI * 2;
      const rRing = globeRadius * 1.01;
      ringPos.push(
        rRing * Math.cos(phi) * Math.cos(theta),
        rRing * Math.sin(phi),
        rRing * Math.cos(phi) * Math.sin(theta)
      );
    }
    const ringGeo = new THREE.BufferGeometry();
    ringGeo.setAttribute('position', new THREE.Float32BufferAttribute(ringPos, 3));
    scene.add(new THREE.Line(ringGeo, ringMat));
  }

  // ─── Sparkle Particles ───
  const sparkleCount = 600;
  const sparklePos = new Float32Array(sparkleCount * 3);
  for (let i = 0; i < sparkleCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 1.8 + Math.random() * 1.8;
    sparklePos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    sparklePos[i * 3 + 1] = r * Math.cos(phi);
    sparklePos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
  }

  const sparkleGeo = new THREE.BufferGeometry();
  sparkleGeo.setAttribute('position', new THREE.BufferAttribute(sparklePos, 3));

  const sparkleMat = new THREE.PointsMaterial({
    size: 0.015,
    color: 0x4a8aff,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const sparkles = new THREE.Points(sparkleGeo, sparkleMat);
  scene.add(sparkles);

  // ─── Glow aura ───
  const glowGeo = new THREE.SphereGeometry(globeRadius * 1.25, 32, 32);
  const glowMat = new THREE.MeshBasicMaterial({
    color: 0x3273ff,
    transparent: true,
    opacity: 0.06,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
  });
  const glow = new THREE.Mesh(glowGeo, glowMat);
  scene.add(glow);

  // ─── Animation ───
  function animate() {
    requestAnimationFrame(animate);
    globe.rotation.y += 0.004;
    sparkles.rotation.y += 0.002;
    glow.rotation.y += 0.001;
    renderer.render(scene, camera);
  }
  animate();

  // ─── Resize ───
  function resize() {
    const w = container.clientWidth || 240;
    camera.aspect = w / H;
    camera.updateProjectionMatrix();
    renderer.setSize(w, H);
  }
  window.addEventListener('resize', resize);
})();
