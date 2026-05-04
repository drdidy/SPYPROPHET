"use client";

import { motion, useReducedMotion } from "framer-motion";
import * as React from "react";

interface BrandMarkProps {
  size?: number;
  animated?: boolean;
  className?: string;
}

/**
 * SPY Prophet brand mark.
 *
 * Concept: "The Rising Trigger".
 *   - a bold solid wedge anchored at the base (the prior-session anchor)
 *   - a single sloped line cutting from the wedge's left edge upward
 *   - a luminous orb at the line's terminus (the trigger)
 *
 * Iconic at 16px (favicon) AND at 200px (hero). Pure geometric form, no
 * decorative chrome, scales without losing identity.
 */
export function BrandMark({ size = 40, animated = true, className }: BrandMarkProps) {
  const reduce = useReducedMotion();
  const id = React.useId();
  const draw = reduce || !animated ? 0 : 1.6;

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
        {/* Wedge gradient — the anchor */}
        <linearGradient id={`${id}-wedge`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#2ecc71" />
          <stop offset="1" stopColor="#67c2ff" />
        </linearGradient>
        {/* Line gradient — left to right */}
        <linearGradient id={`${id}-line`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#2ecc71" />
          <stop offset="1" stopColor="#67c2ff" />
        </linearGradient>
        {/* Soft halo behind the orb */}
        <radialGradient id={`${id}-halo`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#67c2ff" stopOpacity="0.85" />
          <stop offset="0.6" stopColor="#67c2ff" stopOpacity="0.18" />
          <stop offset="1" stopColor="#67c2ff" stopOpacity="0" />
        </radialGradient>
        {/* Inner glow under the wedge */}
        <linearGradient id={`${id}-shadow`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#000" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity="0.35" />
        </linearGradient>
      </defs>

      {/* Big halo behind the trigger orb */}
      <circle cx="52" cy="14" r="18" fill={`url(#${id}-halo)`} />

      {/* The wedge (solid anchor) — a confident asymmetric shape */}
      <motion.path
        d="M 8 56 L 36 56 L 36 38 L 18 56 Z M 8 56 L 8 44 L 36 38 L 36 56 Z"
        fill={`url(#${id}-wedge)`}
        initial={animated && !reduce ? { opacity: 0, y: 4 } : false}
        animate={animated && !reduce ? { opacity: 1, y: 0 } : undefined}
        transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
      />
      {/* simpler bold wedge — overrides the more complex one above for crispness */}
      <motion.polygon
        points="6,58 36,58 36,32"
        fill={`url(#${id}-wedge)`}
        initial={animated && !reduce ? { opacity: 0, scale: 0.85 } : false}
        animate={animated && !reduce ? { opacity: 1, scale: 1 } : undefined}
        transition={{ duration: 0.55, ease: [0.2, 0.8, 0.2, 1] }}
        style={{ transformOrigin: "21px 58px" }}
      />

      {/* Subtle highlight on the wedge top edge */}
      <line x1="6" y1="58" x2="36" y2="32" stroke="#ffffff" strokeOpacity="0.18" strokeWidth="1" />

      {/* Sloped trigger line ascending from the wedge tip */}
      <motion.path
        d="M 36 32 L 56 12"
        stroke={`url(#${id}-line)`}
        strokeWidth="3"
        strokeLinecap="round"
        initial={animated && !reduce ? { pathLength: 0 } : false}
        animate={animated && !reduce ? { pathLength: 1 } : undefined}
        transition={{ duration: draw, delay: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      />

      {/* Trigger orb */}
      <motion.circle
        cx="56"
        cy="12"
        r="4"
        fill="#ffffff"
        stroke="#67c2ff"
        strokeWidth="2"
        initial={animated && !reduce ? { opacity: 0, scale: 0.4 } : false}
        animate={
          animated && !reduce
            ? { opacity: [0, 1, 1], scale: [0.4, 1.4, 1] }
            : undefined
        }
        transition={{ delay: draw + 0.1, duration: 1, ease: "easeOut" }}
      />
      {animated && !reduce && (
        <motion.circle
          cx="56"
          cy="12"
          r="4"
          fill="none"
          stroke="#67c2ff"
          strokeWidth="1.5"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.7, 0], scale: [1, 2.6, 3.6] }}
          transition={{
            delay: draw + 0.4,
            duration: 1.8,
            repeat: Infinity,
            ease: "easeOut",
          }}
          style={{ transformOrigin: "56px 12px" }}
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

export function BrandLogo({ size = 40, withWordmark = true, animated = true, className }: BrandLogoProps) {
  return (
    <span className={"inline-flex items-center gap-3 " + (className ?? "")}>
      <BrandMark size={size} animated={animated} />
      {withWordmark && (
        <span className="flex flex-col leading-none">
          <span className="font-[family-name:var(--font-space-grotesk)] text-xl font-extrabold tracking-tight text-text">
            SPY Prophet
          </span>
          <span className="mt-1 text-[0.66rem] font-bold uppercase tracking-[0.22em] text-blue-bright/85">
            Structure Terminal
          </span>
        </span>
      )}
    </span>
  );
}
