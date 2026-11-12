import * as ProgressPrimitive from "@radix-ui/react-progress";
import {
  type ComponentPropsWithoutRef,
  type ElementRef,
  forwardRef,
} from "react";

import { cn } from "@/lib/utils";

type ProgressProps = ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & {
  color?: "primary" | "success" | "warning" | "danger" | "auto";
  maxValue?: number;
  size?: "sm" | "md" | "lg";
  showValue?: boolean;
  valueLabel?: string;
};

function getColorFromValue(value: number): "success" | "warning" | "danger" {
  if (value >= 90) return "success";
  if (value >= 70) return "warning";
  return "danger";
}

const colorMap = {
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

const sizeMap = {
  sm: "h-1.5",
  md: "h-2.5",
  lg: "h-4",
};

const Progress = forwardRef<
  ElementRef<typeof ProgressPrimitive.Root>,
  ProgressProps
>(
  (
    {
      className,
      value,
      color = "primary",
      maxValue = 100,
      size = "md",
      showValue = false,
      valueLabel,
      ...props
    },
    ref,
  ) => {
    const pct = Math.min(100, Math.max(0, ((value ?? 0) / maxValue) * 100));
    const actualColor = color === "auto" ? getColorFromValue(pct) : color;
    const displayValue = valueLabel ?? `${Math.round(pct)}%`;

    return (
      <div
        className={cn(
          "w-full",
          showValue && "flex items-center gap-3",
          className,
        )}
      >
        <ProgressPrimitive.Root
          ref={ref}
          aria-valuemax={maxValue}
          aria-valuemin={0}
          aria-valuenow={value ?? 0}
          className={cn(
            "relative flex-1 overflow-hidden rounded-full bg-muted",
            sizeMap[size],
          )}
          {...props}
        >
          <ProgressPrimitive.Indicator
            className={cn(
              "h-full w-full flex-1 rounded-full transition-all",
              colorMap[actualColor],
            )}
            style={{ transform: `translateX(-${100 - pct}%)` }}
          />
        </ProgressPrimitive.Root>
        {showValue && (
          <span
            className={cn(
              "text-xs font-semibold tabular-nums whitespace-nowrap",
              actualColor === "success" && "text-success",
              actualColor === "warning" && "text-warning",
              actualColor === "danger" && "text-danger",
              actualColor === "primary" && "text-primary",
            )}
          >
            {displayValue}
          </span>
        )}
      </div>
    );
  },
);
Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };
