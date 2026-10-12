import {
  HeadContent,
  Link,
  Scripts,
  createRootRouteWithContext,
} from "@tanstack/react-router"
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools"
import { TanStackDevtools } from "@tanstack/react-devtools"
import { ThemeProvider } from "next-themes"
import type { QueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import type { ReactNode } from "react"
import { ThemeToggle } from "@/components/theme-toggle"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
  AppleIcon,
  CalendarDaysIcon,
  ChartColumnIcon,
  CookingPotIcon,
  RefrigeratorIcon,
} from "lucide-react"

import appCss from "../styles.css?url"

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    head: () => ({
      meta: [
        { charSet: "utf-8" },
        {
          name: "viewport",
          content: "width=device-width, initial-scale=1, viewport-fit=cover",
        },
        { name: "theme-color", content: "#0a0a0a" },
        { title: "Health" },
      ],
      links: [{ rel: "stylesheet", href: appCss }],
    }),
    notFoundComponent: () => (
      <div className="py-16 text-center">
        <h1 className="text-lg font-medium">Not found</h1>
        <p className="text-sm text-muted-foreground">
          This page does not exist.
        </p>
      </div>
    ),
    shellComponent: RootDocument,
  }
)

function RootDocument({ children }: { children: ReactNode }) {
  return (
    // next-themes sets the class on <html> before hydration.
    <html lang="en" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body className="min-h-svh bg-background text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <TooltipProvider>
            <AppHeader />
            <main className="mx-auto w-full max-w-6xl px-4 pt-4 pb-28 sm:pb-16">
              {children}
            </main>
            <Toaster position="top-center" />
          </TooltipProvider>
        </ThemeProvider>
        {import.meta.env.DEV && (
          <TanStackDevtools
            config={{ position: "bottom-right" }}
            plugins={[
              {
                name: "TanStack Router",
                render: <TanStackRouterDevtoolsPanel />,
              },
            ]}
          />
        )}
        <HydrationMarker />
        <Scripts />
      </body>
    </html>
  )
}

/** The four places, in the order of the tab bar. */
const SECTIONS = [
  { to: "/", label: "Today", icon: CalendarDaysIcon },
  { to: "/stats", label: "Stats", icon: ChartColumnIcon },
  { to: "/recipes", label: "Recipes", icon: CookingPotIcon },
  { to: "/inventory", label: "Inventory", icon: RefrigeratorIcon },
  { to: "/foods", label: "Foods", icon: AppleIcon },
] as const

function AppHeader() {
  const desktopLink =
    "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground data-[status=active]:bg-muted data-[status=active]:text-foreground"
  return (
    <>
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-4">
          <Link to="/" className="mr-2 font-heading font-semibold">
            Health
          </Link>
          {/* Phones use the tab bar below; this row is for wider screens. */}
          <nav aria-label="Main" className="hidden gap-1 sm:flex">
            {SECTIONS.map((section) => (
              <Link
                key={section.to}
                to={section.to}
                className={desktopLink}
                activeOptions={section.to === "/" ? { exact: true } : undefined}
              >
                {section.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
      >
        <div className="mx-auto grid max-w-md grid-cols-5">
          {SECTIONS.map((section) => (
            <Link
              key={section.to}
              to={section.to}
              activeOptions={section.to === "/" ? { exact: true } : undefined}
              className="group flex flex-col items-center gap-0.5 py-2 text-xs font-medium text-muted-foreground transition-colors data-[status=active]:text-foreground"
            >
              <span className="flex h-8 w-14 items-center justify-center rounded-full transition-colors group-data-[status=active]:bg-secondary group-data-[status=active]:text-secondary-foreground">
                <section.icon className="size-5" />
              </span>
              {section.label}
            </Link>
          ))}
        </div>
      </nav>
    </>
  )
}

/** Marks the page interactive; end-to-end tests wait for it before clicking. */
function HydrationMarker() {
  useEffect(() => {
    document.documentElement.dataset.hydrated = "true"
  }, [])
  return null
}
