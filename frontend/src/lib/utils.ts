import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const COLORS = {
  ai: "#2a78d6",
  aiLight: "#5aa2f0",
  rule: "#eb6834",
  random: "#9a9893",
  red: "#EF4444",
  yellow: "#F59E0B",
  green: "#22C55E",
  grid: "#1e293b",
  axis: "#64748b",
} as const;
