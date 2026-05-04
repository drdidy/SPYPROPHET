"use client";

import { motion, useReducedMotion } from "framer-motion";

/**
 * Decorative "live structure" SVG used in the landing hero.
 * Draws a sloped structure line + candles + a subtle scanline.
 * No real data — purely cinematic.
 */
export function LiveChart({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  const drawDuration = reduce ? 0 : 2.4;

  // Synthesised candles (semi-realistic ascending wedge).
  const candles = [
    { x: 60, o: 220, c: 200, h: 195, l: 230 },
    { x: 100, o: 200, c: 210, h: 188, l: 218 },
    { x: 140, o: 210, c: 192, h: 182, l: 222 },
    { x: 180, o: 192, c: 178, h: 170, l: 200 },
    { x: 220, o: 178, c: 188, h: 168, l: 196 },
    { x: 260, o: 188, c: 174, h: 164, l: 192 },
    { x: 300, o: 174, c: 158, h: 150, l: 184 },
    { x: 340, o: 158, c: 168, h: 148, l: 178 },
    { x: 380, o: 168, c: 152, h: 142, l: 176 },
    { x: 420, o: 152, c: 138, h: 130, l: 162 },
    { x: 460, o: 138, c: 144, h: 124, l: 152 },
    { x: 500, o: 144, c: 126, h: 118, l: 152 },
    { x: 540, o: 126, c: 138, h: 116, l: 148 },
    { x: 580, o: 138, c: 118, h: 110, l: 144 },
  ];

  return (
    <svg
      className={className}
      viewBox="0 0 640 280"
      role="img"
      aria-label="Decorative live structure chart"
    >
      <defs>
        <linearGradient id="lc-bull" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2ecc71" stopOpacity="0.3" />
          <stop offset="1" stopColor="#2ecc71" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="lc-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#4ea8de" stopOpacity="0.0" />
          <stop offset="0.2" stopColor="#67c2ff" stopOpacity="1" />
          <stop offset="1" stopColor="#2ecc71" stopOpacity="1" />
        </linearGradient>
        <linearGradient id="lc-grid-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#67c2ff" stopOpacity="0.18" />
          <stop offset="1" stopColor="#67c2ff" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* grid */}
      <g stroke="rgba(255,255,255,0.04)" strokeWidth="1">
        {[40, 80, 120, 160, 200, 240].map((y) => (
          <line key={y} x1="20" y1={y} x2="620" y2={y} />
        ))}
        {[120, 240, 360, 480, 600].map((x) => (
          <line key={x} x1={x} y1="20" y2="260" x2={x} />
        ))}
      </g>

      {/* under-line glow band */}
      <rect x="20" y="20" width="600" height="180" fill="url(#lc-grid-fade)" opacity="0.35" />

      {/* candles, drawn one by one */}
      {candles.map((c, i) => {
        const bull = c.c < c.o; // remember y is inverted
        const top = Math.min(c.o, c.c);
        const h = Math.abs(c.o - c.c);
        const fill = bull ? "#2ecc71" : "#f45d75";
        return (
          <motion.g
            key={c.x}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 + i * 0.06, duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <line x1={c.x + 4} y1={c.h} x2={c.x + 4} y2={c.l} stroke={fill} strokeWidth="1.5" opacity="0.9" />
            <rect x={c.x} y={top} width="8" height={Math.max(2, h)} rx="1.5" fill={fill} opacity="0.95" />
          </motion.g>
        );
      })}

      {/* structure line drawn left-to-right */}
      <motion.path
        d="M 40 240 L 620 96"
        fill="none"
        stroke="url(#lc-line)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="4 6"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: drawDuration, ease: [0.2, 0.8, 0.2, 1], delay: 0.4 }}
      />

      {/* trigger dot at the right tip, pulses */}
      <motion.circle
        cx="620"
        cy="96"
        r="6"
        fill="#67c2ff"
        initial={{ opacity: 0, scale: 0.5 }}
        animate={{ opacity: [0, 1, 1], scale: [0.5, 1.4, 1] }}
        transition={{ delay: drawDuration + 0.4, duration: 1.6, ease: "easeOut" }}
      />
      <motion.circle
        cx="620"
        cy="96"
        r="6"
        fill="none"
        stroke="#67c2ff"
        strokeWidth="2"
        initial={{ opacity: 0 }}
        animate={{ opacity: [0, 0.6, 0], scale: [1, 3, 5] }}
        transition={{
          delay: drawDuration + 0.6,
          duration: 1.8,
          repeat: Infinity,
          ease: "easeOut",
        }}
        style={{ transformOrigin: "620px 96px" }}
      />

      {/* Trigger label tag */}
      <motion.g
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: drawDuration + 0.6, duration: 0.5 }}
      >
        <rect x="486" y="60" width="120" height="22" rx="11" fill="#0e1620" stroke="#4ea8de" strokeOpacity="0.5" />
        <text
          x="546"
          y="75"
          textAnchor="middle"
          fontSize="10"
          fontWeight="700"
          letterSpacing="1.4"
          fill="#67c2ff"
          fontFamily="JetBrains Mono, monospace"
        >
          ▲ TRIGGER 624.85
        </text>
      </motion.g>

      {/* Scanline */}
      <motion.line
        x1="20"
        x2="620"
        y1="0"
        y2="0"
        stroke="rgba(103,194,255,0.4)"
        strokeWidth="1.5"
        initial={{ y: 20 }}
        animate={{ y: [20, 240, 20] }}
        transition={{
          duration: 6,
          repeat: Infinity,
          ease: "easeInOut",
          delay: drawDuration + 1,
        }}
      />
    </svg>
  );
}
