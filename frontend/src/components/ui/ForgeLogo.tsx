import { cn } from "../../lib/utils"

interface ForgeLogoProps extends React.SVGProps<SVGSVGElement> {}

export function ForgeLogo({ className, ...props }: ForgeLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      className={cn("text-primary", className)}
      fill="currentColor"
      {...props}
    >
      <path d="M50 10 L80 30 L80 70 L50 90 L20 70 L20 30 Z" />
      <path d="M50 25 L65 35 L65 65 L50 75 L35 65 L35 35 Z" fill="background" />
    </svg>
  )
}
