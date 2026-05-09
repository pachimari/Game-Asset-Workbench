import { Icon } from './Sidebar'

export default function TopBar({
  title,
  breadcrumb,
}: {
  title: string
  breadcrumb?: string
}) {
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-outline-variant/12 bg-surface-container-low/92 px-5 backdrop-blur-xl md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <h1 className="text-base font-black tracking-tight text-on-surface">{title}</h1>
        {breadcrumb ? (
          <>
            <div className="h-4 w-px bg-outline-variant/30" />
            <nav className="min-w-0 truncate text-xs text-on-surface-variant">
              <span className="truncate text-primary">{breadcrumb}</span>
            </nav>
          </>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <div className="relative hidden md:block">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-outline"
          />
          <input
            className="w-52 rounded-lg bg-surface-container-highest py-1.5 pl-9 pr-3 text-xs text-on-surface outline-none placeholder:text-outline transition-all focus:ring-1 focus:ring-primary/40"
            placeholder="搜索目标"
          />
        </div>
        <button className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-bright">
          <Icon name="notifications" className="text-[18px]" />
        </button>
      </div>
    </header>
  )
}
