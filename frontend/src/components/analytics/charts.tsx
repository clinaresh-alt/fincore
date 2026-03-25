"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
  LineChart,
  Line,
} from "recharts";

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}

export function ChartContainer({
  title,
  subtitle,
  children,
  className,
}: ChartContainerProps) {
  return (
    <div
      className={`rounded-xl border bg-white p-6 shadow-sm ${className || ""}`}
    >
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

interface InvestmentTimelineChartProps {
  data: Array<{
    date: string;
    label: string;
    investments: number;
    dividends: number;
  }>;
}

export function InvestmentTimelineChart({ data }: InvestmentTimelineChartProps) {
  const formatValue = (value: number) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
    return `$${value}`;
  };

  return (
    <ResponsiveContainer width="100%" height={350}>
      <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorInvestments" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorDividends" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: "#6b7280" }}
          tickLine={false}
          axisLine={{ stroke: "#e5e7eb" }}
        />
        <YAxis
          tick={{ fontSize: 12, fill: "#6b7280" }}
          tickLine={false}
          axisLine={{ stroke: "#e5e7eb" }}
          tickFormatter={formatValue}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
          }}
          formatter={(value: number) => [formatValue(value), ""]}
        />
        <Legend />
        <Area
          type="monotone"
          dataKey="investments"
          name="Inversiones"
          stroke="#3b82f6"
          fillOpacity={1}
          fill="url(#colorInvestments)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="dividends"
          name="Dividendos"
          stroke="#22c55e"
          fillOpacity={1}
          fill="url(#colorDividends)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

interface SectorDistributionChartProps {
  data: Array<{
    sector: string;
    amount: number;
    percentage: number;
    color: string;
  }>;
}

export function SectorDistributionChart({ data }: SectorDistributionChartProps) {
  const formatValue = (value: number) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    return `$${(value / 1000).toFixed(0)}K`;
  };

  return (
    <div className="flex items-center gap-8">
      <ResponsiveContainer width="50%" height={280}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={2}
            dataKey="amount"
            nameKey="sector"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "white",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
            }}
            formatter={(value: number) => [formatValue(value), "Monto"]}
          />
        </PieChart>
      </ResponsiveContainer>

      <div className="flex-1 space-y-3">
        {data.map((item, index) => (
          <div key={index} className="flex items-center gap-3">
            <div
              className="h-3 w-3 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">
                  {item.sector}
                </span>
                <span className="text-sm font-semibold text-gray-900">
                  {item.percentage}%
                </span>
              </div>
              <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
                <div
                  className="h-2 rounded-full transition-all"
                  style={{
                    width: `${item.percentage}%`,
                    backgroundColor: item.color,
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface ProjectPerformanceChartProps {
  data: Array<{
    name: string;
    roi: number;
    invested: number;
    progress: number;
    sector: string;
  }>;
}

export function ProjectPerformanceChart({ data }: ProjectPerformanceChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="vertical" margin={{ left: 120 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          type="number"
          tick={{ fontSize: 12, fill: "#6b7280" }}
          tickLine={false}
          domain={[0, 30]}
          tickFormatter={(value) => `${value}%`}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 12, fill: "#374151" }}
          tickLine={false}
          axisLine={false}
          width={110}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
          }}
          formatter={(value: number) => [`${value}%`, "ROI"]}
        />
        <Bar dataKey="roi" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={24}>
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.roi > 15 ? "#22c55e" : entry.roi > 10 ? "#3b82f6" : "#f59e0b"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

interface TransactionDistributionChartProps {
  data: Array<{
    type: string;
    count: number;
    volume: number;
    color: string;
  }>;
}

export function TransactionDistributionChart({
  data,
}: TransactionDistributionChartProps) {
  const typeLabels: Record<string, string> = {
    investment: "Inversiones",
    dividend: "Dividendos",
    withdrawal: "Retiros",
    fee: "Comisiones",
  };

  const chartData = data.map((item) => ({
    ...item,
    name: typeLabels[item.type] || item.type,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 12, fill: "#6b7280" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: "#6b7280" }}
          tickLine={false}
          tickFormatter={(value) => {
            if (value >= 1000000) return `$${(value / 1000000).toFixed(0)}M`;
            if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
            return `$${value}`;
          }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
          }}
          formatter={(value: number) => [
            `$${(value / 1000000).toFixed(2)}M`,
            "Volumen",
          ]}
        />
        <Bar dataKey="volume" radius={[4, 4, 0, 0]}>
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

interface KPIProgressProps {
  kpis: Record<
    string,
    {
      current: number;
      target: number;
      progress: number;
      trend: string;
    }
  >;
}

export function KPIProgress({ kpis }: KPIProgressProps) {
  const kpiLabels: Record<string, { label: string; format: (v: number) => string }> = {
    aum: {
      label: "AUM (Assets Under Management)",
      format: (v) => `$${(v / 1000000).toFixed(1)}M`,
    },
    investor_growth: {
      label: "Crecimiento de Inversionistas",
      format: (v) => v.toLocaleString(),
    },
    avg_ticket: {
      label: "Ticket Promedio",
      format: (v) => `$${(v / 1000).toFixed(0)}K`,
    },
    nps: {
      label: "Net Promoter Score",
      format: (v) => v.toString(),
    },
    default_rate: {
      label: "Tasa de Morosidad",
      format: (v) => `${v}%`,
    },
  };

  return (
    <div className="space-y-4">
      {Object.entries(kpis).map(([key, kpi]) => {
        const config = kpiLabels[key];
        if (!config) return null;

        const isGood =
          key === "default_rate"
            ? kpi.current <= kpi.target
            : kpi.current >= kpi.target * 0.9;

        return (
          <div key={key} className="rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                {config.label}
              </span>
              <span
                className={`text-sm font-semibold ${
                  isGood ? "text-green-600" : "text-amber-600"
                }`}
              >
                {config.format(kpi.current)} / {config.format(kpi.target)}
              </span>
            </div>
            <div className="mt-2">
              <div className="h-2 w-full rounded-full bg-gray-100">
                <div
                  className={`h-2 rounded-full transition-all ${
                    isGood ? "bg-green-500" : "bg-amber-500"
                  }`}
                  style={{ width: `${Math.min(kpi.progress, 100)}%` }}
                />
              </div>
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>{kpi.progress.toFixed(1)}% completado</span>
                <span
                  className={`font-medium ${
                    kpi.trend === "up"
                      ? "text-green-600"
                      : kpi.trend === "down"
                      ? "text-red-600"
                      : "text-gray-600"
                  }`}
                >
                  {kpi.trend === "up" ? "+" : kpi.trend === "down" ? "-" : "="}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface InvestorTierChartProps {
  data: Array<{
    tier: string;
    count: number;
    color: string;
  }>;
}

export function InvestorTierChart({ data }: InvestorTierChartProps) {
  const total = data.reduce((acc, item) => acc + item.count, 0);

  return (
    <div className="space-y-4">
      {data.map((tier, index) => (
        <div key={index} className="flex items-center gap-4">
          <div
            className="h-10 w-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
            style={{ backgroundColor: tier.color }}
          >
            {tier.tier.charAt(0)}
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <span className="font-medium text-gray-900">{tier.tier}</span>
              <span className="text-sm text-gray-600">
                {tier.count.toLocaleString()} ({((tier.count / total) * 100).toFixed(1)}%)
              </span>
            </div>
            <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
              <div
                className="h-2 rounded-full transition-all"
                style={{
                  width: `${(tier.count / total) * 100}%`,
                  backgroundColor: tier.color,
                }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
