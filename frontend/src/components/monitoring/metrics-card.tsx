"use client";

import { LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive?: boolean;
  };
  color?: "default" | "green" | "red" | "yellow" | "blue" | "purple";
  size?: "sm" | "md" | "lg";
}

const COLOR_CLASSES = {
  default: {
    icon: "text-gray-600 bg-gray-100",
    card: "",
  },
  green: {
    icon: "text-green-600 bg-green-100",
    card: "border-green-200",
  },
  red: {
    icon: "text-red-600 bg-red-100",
    card: "border-red-200",
  },
  yellow: {
    icon: "text-yellow-600 bg-yellow-100",
    card: "border-yellow-200",
  },
  blue: {
    icon: "text-blue-600 bg-blue-100",
    card: "border-blue-200",
  },
  purple: {
    icon: "text-purple-600 bg-purple-100",
    card: "border-purple-200",
  },
};

export function MetricsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = "default",
  size = "md",
}: MetricsCardProps) {
  const colorClasses = COLOR_CLASSES[color];

  const TrendIcon = trend
    ? trend.value > 0
      ? TrendingUp
      : trend.value < 0
      ? TrendingDown
      : Minus
    : null;

  return (
    <Card className={cn("transition-all hover:shadow-md", colorClasses.card)}>
      <CardContent className={cn("p-4", size === "sm" && "p-3", size === "lg" && "p-6")}>
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {title}
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span
                className={cn(
                  "font-bold",
                  size === "sm" && "text-xl",
                  size === "md" && "text-2xl",
                  size === "lg" && "text-3xl"
                )}
              >
                {value}
              </span>
              {trend && TrendIcon && (
                <span
                  className={cn(
                    "flex items-center text-xs font-medium",
                    trend.isPositive !== undefined
                      ? trend.isPositive
                        ? "text-green-600"
                        : "text-red-600"
                      : trend.value > 0
                      ? "text-green-600"
                      : trend.value < 0
                      ? "text-red-600"
                      : "text-gray-500"
                  )}
                >
                  <TrendIcon className="h-3 w-3 mr-0.5" />
                  {Math.abs(trend.value).toFixed(1)}%
                </span>
              )}
            </div>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
          </div>
          <div className={cn("p-3 rounded-xl", colorClasses.icon)}>
            <Icon className={cn(size === "sm" ? "h-4 w-4" : "h-5 w-5")} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
