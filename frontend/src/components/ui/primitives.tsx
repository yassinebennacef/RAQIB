// Small shadcn-style primitives written with Tailwind (the shadcn CLI was not used: see PROGRESS.md).
import { cva, type VariantProps } from "class-variance-authority";
import { Info } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ Card */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-800/90 bg-slate-900/75 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)] backdrop-blur",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-start justify-between gap-3 px-5 pt-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-sm font-semibold tracking-tight text-slate-100", className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-0.5 text-xs text-slate-400", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5 pt-3", className)} {...props} />;
}

/* ------------------------------------------------------------------ Button */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-ai text-white hover:bg-ai-light",
        secondary: "bg-slate-800 text-slate-100 hover:bg-slate-700",
        outline: "border border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800",
        ghost: "text-slate-300 hover:bg-slate-800 hover:text-slate-100",
        red: "bg-lane-red/90 text-white hover:bg-lane-red",
        yellow: "bg-lane-yellow/90 text-slate-950 hover:bg-lane-yellow",
        green: "bg-lane-green/90 text-slate-950 hover:bg-lane-green",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-11 px-5 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";

/* ------------------------------------------------------------------ Badge */
export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-[11px] font-medium text-slate-300",
        className,
      )}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ Slider */
export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  label,
  className,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  label: string;
  className?: string;
}) {
  const fill = `${((value - min) / (max - min)) * 100}%`;
  return (
    <input
      type="range"
      aria-label={label}
      className={cn("raqib-range", className)}
      style={{ ["--fill" as string]: fill } as React.CSSProperties}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  );
}

/* ------------------------------------------------------------------ Switch */
export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border transition-colors",
        checked ? "border-ai bg-ai" : "border-slate-700 bg-slate-800",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-6" : "translate-x-1",
        )}
      />
    </button>
  );
}

/* ------------------------------------------------------------------ Segmented tabs */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: { value: T; label: React.ReactNode }[];
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div role="tablist" className={cn("inline-flex rounded-lg border border-slate-800 bg-slate-950/60 p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            value === o.value ? "bg-slate-800 text-slate-100 shadow" : "text-slate-400 hover:text-slate-200",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Info tooltip */
export function InfoTip({ text, className }: { text: string; className?: string }) {
  return (
    <span className={cn("group relative inline-flex align-middle", className)}>
      <span
        tabIndex={0}
        aria-label={text}
        className="inline-flex cursor-help text-slate-500 outline-none hover:text-slate-300 focus-visible:text-slate-200"
      >
        <Info className="h-3.5 w-3.5" />
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-64 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-slate-300 opacity-0 shadow-xl transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ Skeleton / states */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-slate-800/70", className)} />;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-lane-red/30 bg-lane-red/5 p-8 text-center">
      <p className="text-sm text-slate-200">Could not load data from the RAQIB API.</p>
      <p className="font-mono text-xs text-slate-400">{message}</p>
      <p className="text-xs text-slate-500">
        Is the backend running? <code className="font-mono">python -m raqib.serve</code>
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  tip,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tip?: string;
  className?: string;
}) {
  return (
    <Card className={cn("px-4 py-3", className)}>
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-400">
        {label}
        {tip && <InfoTip text={tip} />}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular text-slate-50">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-400">{sub}</div>}
    </Card>
  );
}
