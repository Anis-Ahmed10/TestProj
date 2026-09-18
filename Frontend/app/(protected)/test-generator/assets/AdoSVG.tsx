export default function AdoSVG({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M21 7.5L12 3 3 7.5V16.5L12 21l9-4.5V7.5z" fill="#0078D4" />
      <path
        d="M12 3v18M3 7.5l9 4.5 9-4.5"
        stroke="#fff"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
