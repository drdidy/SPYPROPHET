"use client";

import { motion, type Variants, useReducedMotion } from "framer-motion";
import * as React from "react";

const variants: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.2, 0.8, 0.2, 1] } },
};

export function Reveal({
  children,
  delay = 0,
  className,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "h1" | "h2" | "h3" | "h4" | "p" | "span" | "ol" | "ul" | "li";
}) {
  const reduce = useReducedMotion();
  const Component = (motion as unknown as Record<string, React.ComponentType<Record<string, unknown>>>)[Tag];
  if (reduce) {
    return <Tag className={className}>{children}</Tag>;
  }
  return (
    <Component
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.2 }}
      variants={variants}
      transition={{ delay }}
    >
      {children}
    </Component>
  );
}

export function StaggerGroup({
  children,
  delayChildren = 0,
  staggerChildren = 0.03,
  className,
}: {
  children: React.ReactNode;
  delayChildren?: number;
  staggerChildren?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  if (reduce) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.05 }}
      variants={{
        hidden: {},
        show: { transition: { delayChildren, staggerChildren } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={variants}>
      {children}
    </motion.div>
  );
}
