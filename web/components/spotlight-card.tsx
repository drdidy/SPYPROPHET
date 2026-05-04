"use client";

import { cn } from "@/lib/cn";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import * as React from "react";

interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  premium?: boolean;
  /** Subtle 3D tilt on hover. Disable on full-bleed hero cards if it feels excessive. */
  tilt?: boolean;
}

/**
 * A premium card that:
 *  - tracks the cursor with a soft radial highlight (the "spotlight")
 *  - on hover, slightly tilts in 3D to add tactile depth
 *  - inherits the brand glassmorphism from regular Card
 */
export function SpotlightCard({
  className,
  premium = false,
  tilt = true,
  children,
  ...props
}: SpotlightCardProps) {
  const ref = React.useRef<HTMLDivElement>(null);
  const x = useMotionValue(50);
  const y = useMotionValue(50);
  const rotateX = useSpring(useTransform(y, [0, 100], [4, -4]), { stiffness: 220, damping: 22 });
  const rotateY = useSpring(useTransform(x, [0, 100], [-4, 4]), { stiffness: 220, damping: 22 });

  function handleMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * 100;
    const py = ((e.clientY - rect.top) / rect.height) * 100;
    x.set(px);
    y.set(py);
  }

  function handleLeave() {
    x.set(50);
    y.set(50);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      style={tilt ? { rotateX, rotateY, transformStyle: "preserve-3d", transformPerspective: 1200 } : undefined}
      className={cn(
        "group/spotlight relative rounded-2xl border border-border bg-surface/70 backdrop-blur-md",
        premium && "premium-border",
        className,
      )}
      {...(props as React.ComponentProps<typeof motion.div>)}
    >
      {/* spotlight overlay */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover/spotlight:opacity-100"
        style={{
          background: useTransform(
            [x, y],
            ([cx, cy]) =>
              `radial-gradient(380px circle at ${cx}% ${cy}%, rgba(78,168,222,0.18), transparent 55%)`,
          ),
        }}
      />
      <div className="relative" style={tilt ? { transform: "translateZ(0.01px)" } : undefined}>
        {children}
      </div>
    </motion.div>
  );
}
