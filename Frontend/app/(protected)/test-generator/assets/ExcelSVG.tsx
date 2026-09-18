export default function ExcelSVG({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="3" width="20" height="18" rx="2" fill="#217346" />
      <path
        d="M8 8l3 4-3 4M13 8h3M13 12h3M13 16h3"
        stroke="#fff"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
