import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-4">
      <h2 className="mb-2 text-4xl font-bold text-foreground">404</h2>
      <p className="mb-4 text-muted-foreground">
        The page you are looking for does not exist.
      </p>
      <Link
        href="/"
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Go home
      </Link>
      <div className="mt-8 flex flex-wrap justify-center gap-3 text-sm">
        <Link href="/publications" className="text-muted-foreground hover:text-foreground transition-colors">Publications</Link>
        <span className="text-muted-foreground/30">|</span>
        <Link href="/leaderboard" className="text-muted-foreground hover:text-foreground transition-colors">Leaderboard</Link>
        <span className="text-muted-foreground/30">|</span>
        <Link href="/families" className="text-muted-foreground hover:text-foreground transition-colors">Families</Link>
        <span className="text-muted-foreground/30">|</span>
        <Link href="/methodology" className="text-muted-foreground hover:text-foreground transition-colors">Methodology</Link>
      </div>
    </div>
  );
}
