import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: {
    value: number;
    direction: "up" | "down";
    label?: string;
  };
  progress?: {
    value: number;
    maxValue?: number;
    showValue?: boolean;
  };
  className?: string;
}

export function StatsCard({
  title,
  value,
  icon: Icon,
  trend,
  progress,
  className,
}: StatsCardProps) {
  const trendColor =
    trend?.direction === "up"
      ? "text-success"
      : trend?.direction === "down"
        ? "text-danger"
        : "text-muted-foreground";

  return (
    <Card
      className={cn("transition-colors hover:border-foreground/20", className)}
    >
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {title}
          </p>
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>

        <div className="flex items-baseline gap-2 mb-3">
          <span className="text-2xl font-extrabold text-foreground">
            {value}
          </span>
          {trend && (
            <span className={cn("text-[10px] font-medium", trendColor)}>
              {trend.direction === "up" ? "+" : "-"}
              {Math.abs(trend.value)}%
              {trend.label && (
                <span className="text-muted-foreground ml-1">
                  ({trend.label})
                </span>
              )}
            </span>
          )}
        </div>

        {progress && (
          <Progress
            value={progress.value}
            maxValue={progress.maxValue ?? 100}
            color="auto"
            size="sm"
            showValue={progress.showValue}
          />
        )}
      </CardContent>
    </Card>
  );
}
