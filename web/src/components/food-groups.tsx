import { Link } from "@tanstack/react-router"
import {
  AppleIcon,
  BeanIcon,
  BeefIcon,
  CakeSliceIcon,
  CandyIcon,
  CroissantIcon,
  CupSodaIcon,
  DropletIcon,
  DrumstickIcon,
  EggIcon,
  FishIcon,
  HamIcon,
  LayoutGridIcon,
  MilkIcon,
  SaladIcon,
  SoupIcon,
  SproutIcon,
  UtensilsCrossedIcon,
  WheatIcon,
  WineIcon,
} from "lucide-react"
import { cn } from "cn"
import type { LucideIcon } from "lucide-react"
import type { Facets } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"

/** An icon per BLS food group (the first letter of a BLS code). */
export const GROUP_ICONS: Record<string, LucideIcon> = {
  B: CroissantIcon,
  C: WheatIcon,
  D: CakeSliceIcon,
  E: EggIcon,
  F: AppleIcon,
  G: SaladIcon,
  H: BeanIcon,
  K: SproutIcon,
  M: MilkIcon,
  N: CupSodaIcon,
  P: WineIcon,
  Q: DropletIcon,
  R: SoupIcon,
  S: CandyIcon,
  T: FishIcon,
  U: BeefIcon,
  V: DrumstickIcon,
  W: HamIcon,
  X: SaladIcon,
  Y: UtensilsCrossedIcon,
}

export function groupIcon(code: string | undefined): LucideIcon {
  return (code && GROUP_ICONS[code]) || LayoutGridIcon
}

/**
 * The food groups as a navigation list. Each entry is a link that keeps the
 * other search settings, so back, forward, and new tabs work.
 */
export function FoodGroupNav({
  facets,
  active,
  onNavigate,
}: {
  facets: Facets
  active: string | undefined
  onNavigate?: () => void
}) {
  const entries = [
    { code: undefined, name: "All foods", count: facets.foods },
    ...facets.groups.map((group) => ({
      code: String(group.code),
      name: String(group.name),
      count: Number(group.count),
    })),
  ]
  return (
    <nav aria-label="Food groups">
      <ul className="flex flex-col gap-0.5">
        {entries.map((entry) => {
          const Icon = groupIcon(entry.code)
          const selected = entry.code === active
          return (
            <li key={entry.code ?? "all"}>
              <Link
                to="/foods"
                search={(prev) => ({ ...prev, group: entry.code })}
                onClick={onNavigate}
                aria-current={selected ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                  selected
                    ? "bg-primary font-medium text-primary-foreground"
                    : "text-foreground/80 hover:bg-accent hover:text-foreground"
                )}
              >
                <Icon className="size-4 shrink-0 opacity-80" aria-hidden />
                <span className="min-w-0 flex-1 leading-snug">
                  {entry.name}
                </span>
                <span
                  className={cn(
                    "text-xs tabular-nums",
                    selected ? "opacity-80" : "text-muted-foreground"
                  )}
                >
                  {formatNumber(entry.count, 0)}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
