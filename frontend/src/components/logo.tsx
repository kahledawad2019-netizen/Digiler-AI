import { cn } from "@/lib/utils";

/** The Digiler AI brand mark, rendered as inline SVG so it always displays (no
 *  external-file dependency, no 404). Used in the sidebar / login / navbar.
 *  To use a custom raster logo instead, drop it at public/logo.png and swap the
 *  <LogoMark/> below for <img src="/logo.png" />. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none"
      role="img" aria-label="Digiler AI" className="shrink-0">
      <defs>
        <linearGradient id="dg-mark" x1="8" y1="52" x2="56" y2="14" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#2563EB" />
          <stop offset="1" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
      <path d="M32 24 C24 19 14 19 8 22 L8 47 C14 44 24 44 32 49 Z" fill="url(#dg-mark)" />
      <path d="M32 24 C40 19 50 19 56 22 L56 47 C50 44 40 44 32 49 Z" fill="url(#dg-mark)" opacity="0.82" />
      <path d="M20 47 L20 55 L27 48 Z" fill="url(#dg-mark)" />
      <g stroke="#67E8F9" strokeWidth="1.6">
        <line x1="17" y1="34" x2="23" y2="30" /><line x1="23" y1="30" x2="26" y2="37" />
      </g>
      <g fill="#67E8F9">
        <circle cx="17" cy="34" r="2.4" /><circle cx="23" cy="30" r="2.4" /><circle cx="26" cy="37" r="2.4" />
      </g>
      <path d="M32 8 L54 16 L32 24 L10 16 Z" fill="#1E3A8A" />
      <path d="M22 20 L22 27 C22 30 42 30 42 27 L42 20 L32 23.6 Z" fill="#1E3A8A" />
      <line x1="54" y1="16" x2="54" y2="26" stroke="#1E3A8A" strokeWidth="1.8" />
      <circle cx="54" cy="27" r="2" fill="#67E8F9" />
    </svg>
  );
}

export function Logo({ size = 32, withWordmark = true, className }: {
  size?: number;
  withWordmark?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark size={size} />
      {withWordmark && (
        <span className="text-[15px] font-semibold tracking-tight text-foreground">
          Digiler <span className="text-primary">AI</span>
        </span>
      )}
    </div>
  );
}
