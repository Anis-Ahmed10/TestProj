export default function UploadCloudSVG({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="20" fill="#eff6ff" />
      <path
        d="M20 11v13M15 18l5-5 5 5"
        stroke="#2563eb"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M13 29h14"
        stroke="#93c5fd"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
