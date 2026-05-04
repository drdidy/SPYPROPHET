import { cn } from "@/lib/cn";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

const buttonStyles = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl font-semibold transition-all duration-200 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-br from-blue via-blue-bright to-green text-[#06121a] shadow-[0_8px_28px_-6px_rgba(78,168,222,0.6)] hover:shadow-[0_14px_36px_-6px_rgba(78,168,222,0.8)] hover:-translate-y-0.5 active:translate-y-0",
        ghost:
          "border border-border-2 bg-surface/60 text-text hover:bg-surface-2 hover:border-blue/60",
        soft:
          "bg-blue/10 text-blue-bright hover:bg-blue/20 border border-blue/30",
        bullish:
          "bg-gradient-to-br from-green to-green-bright text-[#08160e] shadow-[0_8px_28px_-6px_rgba(46,204,113,0.6)] hover:shadow-[0_14px_36px_-6px_rgba(46,204,113,0.8)]",
        bearish:
          "bg-gradient-to-br from-red to-red-bright text-[#1a070b] shadow-[0_8px_28px_-6px_rgba(244,93,117,0.6)]",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-5 text-sm",
        lg: "h-12 px-7 text-base",
        xl: "h-14 px-9 text-lg",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonStyles> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonStyles({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
