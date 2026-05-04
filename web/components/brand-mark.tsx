"use client";

import { motion, useReducedMotion } from "framer-motion";
import * as React from "react";

interface BrandMarkProps {
  size?: number;
  animated?: boolean;
  className?: string;
}

/**
 * SPY Prophet — "Apex" mark.
 *
 * A faceted geometric pyramid with two visible faces (light + dark) and a
 * luminous orb at the peak. Reads as one bold shape at any size; the dual
 * facet creates depth without detail.
 *
 * Symbology: every path converges at the apex; the orb is the trigger.
 */
export function BrandMark({ size = 48, animated = true, className }: BrandMarkProps) {
  const reduce = useReducedMotion();
  const id = React.useId();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      role="img"
      aria-label="SPY Prophet"
      className={className}
    >
      <defs>
        {/* Bright face — catches the light */}
        <linearGradient id={`${id}-bright`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#28d2c2" />
          <stop offset="0.5" stopColor="#67c2ff" />
          <stop offset="1" stopColor="#a8e6ff" />
        </linearGradient>
        {/* Shadow face — gives depth */}
        <linearGradient id={`${id}-shadow`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3a6f8c" />
          <stop offset="0.6" stopColor="#1f3a4d" />
          <stop offset="1" stopColor="#0e1c26" />
        </linearGradient>
        {/* Inner edge highlight */}
        <linearGradient id={`${id}-edge`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.85" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        {/* Halo behind the orb */}
        <radialGradient id={`${id}-halo`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#a8e6ff" stopOpacity="0.9" />
          <stop offset="0.4" stopColor="#67c2ff" stopOpacity="0.4" />
          <stop offset="1" stopColor="#67c2ff" stopOpacity="0" />
        </radialGradient>
        {/* Drop shadow under base */}
        <linearGradient id={`${id}-base-shadow`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#000000" stopOpacity="0.5" />
          <stop offset="1" stopColor="#000000" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Soft drop shadow / floor reflection */}
      <ellipse cx="32" cy="58" rx="22" ry="2.5" fill={`url(#${id}-base-shadow)`} opacity={0.5} />

      {/* Halo behind the apex orb */}
      <circle cx="32" cy="10" r="14" fill={`url(#${id}-halo)`} />

      {/* The pyramid — two facets meeting at the apex */}
      {/* Left bright facet */}
      <motion.polygon
        points="32,8 8,52 32,52"
        fill={`url(#${id}-bright)`}
        initial={animated && !reduce ? { opacity: 0, y: 6 } : false}
        animate={animated && !reduce ? { opacity: 1, y: 0 } : undefined}
        transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
      />
      {/* Right shadow facet */}
      <motion.polygon
        points="32,8 56,52 32,52"
        fill={`url(#${id}-shadow)`}
        initial={animated && !reduce ? { opacity: 0, y: 6 } : false}
        animate={animated && !reduce ? { opacity: 1, y: 0 } : undefined}
        transition={{ duration: 0.6, delay: 0.05, ease: [0.2, 0.8, 0.2, 1] }}
      />
      {/* Sharp center seam — the spine */}
      <line x1="32" y1="8" x2="32" y2="52" stroke={`url(#${id}-edge)`} strokeWidth="1.2" />

      {/* Base accent */}
      <line x1="8" y1="52" x2="56" y2="52" stroke="#67c2ff" strokeOpacity="0.35" strokeWidth="1" />

      {/* The Apex orb */}
      <motion.circle
        cx="32"
        cy="8"
        r="4.5"
        fill="#ffffff"
        initial={animated && !reduce ? { opacity: 0, scale: 0.4 } : false}
        animate={
          animated && !reduce
            ? { opacity: [0, 1, 1], scale: [0.4, 1.4, 1] }
            : undefined
        }
        transition={{ delay: 0.3, duration: 1, ease: "easeOut" }}
      />
      <circle cx="32" cy="8" r="4.5" fill="none" stroke="#67c2ff" strokeWidth="1.5" />
      {animated && !reduce && (
        <motion.circle
          cx="32"
          cy="8"
          r="4.5"
          fill="none"
          stroke="#67c2ff"
          strokeWidth="1.5"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.7, 0], scale: [1, 2.6, 3.6] }}
          transition={{
            delay: 0.6,
            duration: 2,
            repeat: Infinity,
            ease: "easeOut",
          }}
          style={{ transformOrigin: "32px 8px" }}
        />
      )}
    </svg>
  );
}

interface BrandLogoProps {
  size?: number;
  withWordmark?: boolean;
  animated?: boolean;
  className?: string;
}

export function BrandLogo({ size = 48, withWordmark = true, animated = true, className }: BrandLogoProps) {
  return (
    <span className={"inline-flex items-center gap-3 " + (className ?? "")}>
      <BrandMark size={size} animated={animated} />
      {withWordmark && (
        <span className="flex flex-col leading-none">
          <span className="font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tracking-tight text-text">
            SPY Prophet
          </span>
          <span className="mt-1 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-blue-bright/85">
            Structure Terminal
          </span>
        </span>
      )}
    </span>
  );
}
