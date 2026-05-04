"use client";

import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "framer-motion";
import * as React from "react";

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  /** Time in ms after mount before the spring starts (e.g. wait for a card to reveal). */
  startDelay?: number;
}

export function AnimatedNumber({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  className,
  startDelay = 0,
}: AnimatedNumberProps) {
  const reduce = useReducedMotion();
  const motionValue = useMotionValue(0);
  const spring = useSpring(motionValue, { stiffness: 70, damping: 22, mass: 0.7 });
  const display = useTransform(spring, (v) => {
    const fmt = v.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return `${prefix}${fmt}${suffix}`;
  });

  React.useEffect(() => {
    if (reduce) {
      motionValue.set(value);
      return;
    }
    const t = setTimeout(() => motionValue.set(value), startDelay);
    return () => clearTimeout(t);
  }, [value, motionValue, reduce, startDelay]);

  return <motion.span className={className}>{display}</motion.span>;
}
