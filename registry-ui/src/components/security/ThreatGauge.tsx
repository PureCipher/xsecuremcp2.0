"use client";

const LEVEL_CONFIG: Record<string, { color: string; bg: string; pct: number }> = {
  none: { color: "text-emerald-400", bg: "stroke-emerald-500", pct: 5 },
  low: { color: "text-sky-400", bg: "stroke-sky-500", pct: 25 },
  medium: { color: "text-amber-400", bg: "stroke-amber-500", pct: 50 },
  high: { color: "text-orange-400", bg: "stroke-orange-500", pct: 75 },
  critical: { color: "text-red-400", bg: "stroke-red-500", pct: 95 },
};

export function ThreatGauge({
  level,
  score,
  size = "md",
}: {
  level: string;
  score?: number;
  size?: "sm" | "md" | "lg";
}) {
  const config = LEVEL_CONFIG[level.toLowerCase()] || LEVEL_CONFIG.none;
  const dims = size === "sm" ? 80 : size === "lg" ? 160 : 120;
  const strokeWidth = size === "sm" ? 6 : size === "lg" ? 10 : 8;
  const radius = (dims - strokeWidth) / 2;
  const circumference = Math.PI * radius; // semicircle
  const offset = circumference * (1 - config.pct / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={dims} height={dims / 2 + 10} viewBox={`0 0 ${dims} ${dims / 2 + 10}`}>
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${dims / 2} A ${radius} ${radius} 0 0 1 ${dims - strokeWidth / 2} ${dims / 2}`}
          fill="none"
          stroke="currentColor"
          className="text-emerald-800/40"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d={`M ${strokeWidth / 2} ${dims / 2} A ${radius} ${radius} 0 0 1 ${dims - strokeWidth / 2} ${dims / 2}`}
          fill="none"
          className={config.bg}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <p className={`text-[12px] font-bold uppercase tracking-wider ${config.color}`}>
        {level}
      </p>
      {score !== undefined ? (
        <p className="text-[10px] text-emerald-300/70">Score: {score.toFixed(1)}</p>
      ) : null}
    </div>
  );
}
