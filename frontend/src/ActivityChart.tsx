type Point = { date: string; requests: number };

type Props = { data: Point[] };

const width = 620;
const height = 150;
const inset = { top: 10, right: 8, bottom: 25, left: 30 };

export default function ActivityChart({ data }: Props) {
  const plotWidth = width - inset.left - inset.right;
  const plotHeight = height - inset.top - inset.bottom;
  const maximum = Math.max(1, ...data.map((point) => point.requests));
  const points = data.map((point, index) => ({
    ...point,
    x: inset.left + (data.length < 2 ? plotWidth / 2 : (index * plotWidth) / (data.length - 1)),
    y: inset.top + plotHeight - (point.requests / maximum) * plotHeight,
  }));
  const linePath = points.map((point, index) =>
    `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`,
  ).join(" ");
  const areaPath = points.length
    ? `${linePath} L ${points[points.length - 1].x} ${inset.top + plotHeight} L ${points[0].x} ${inset.top + plotHeight} Z`
    : "";
  const yTicks = [0, Math.ceil(maximum / 2), maximum];

  return (
    <svg className="activity-chart" viewBox={`0 0 ${width} ${height}`} role="img"
      aria-label="Daily AI conversations over the last seven days">
      <defs>
        <linearGradient id="activity-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#9b82ff" stopOpacity=".28" />
          <stop offset="100%" stopColor="#9b82ff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {yTicks.map((tick, index) => {
        const y = inset.top + (plotHeight * index) / (yTicks.length - 1);
        const value = maximum - tick;
        return (
          <g key={`${tick}-${index}`}>
            <line x1={inset.left} x2={width - inset.right} y1={y} y2={y}
              stroke="#232733" strokeDasharray="3 5" />
            <text x={inset.left - 8} y={y + 3} textAnchor="end">{value}</text>
          </g>
        );
      })}
      <path d={areaPath} fill="url(#activity-area)" />
      <path d={linePath} fill="none" stroke="#a591ff" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
      {points.map((point) => (
        <g key={point.date}>
          <circle cx={point.x} cy={point.y} r="3" fill="#b9a6ff" stroke="#171522" strokeWidth="2">
            <title>{`${point.date}: ${point.requests} requests`}</title>
          </circle>
          <text x={point.x} y={height - 5} textAnchor="middle">
            {new Date(`${point.date}T00:00:00`).toLocaleDateString("en", { weekday: "short" })}
          </text>
        </g>
      ))}
    </svg>
  );
}
