import Image from "next/image";

/**
 * Cabecera base: logo de marca + wordmark. Sin navegación todavía
 * (esta tarea es solo la base visual).
 */
export function SiteHeader() {
  return (
    <header className="w-full border-b border-border/60 bg-background/80 backdrop-blur-sm">
      <div className="container mx-auto flex h-16 max-w-5xl items-center gap-3 px-6">
        <Image
          src="/Logo.png"
          alt="Logo de DetoxApp"
          width={36}
          height={36}
          priority
          className="h-9 w-9 object-contain"
        />
        <span className="font-serif text-xl font-semibold tracking-tight text-foreground">
          DetoxApp
        </span>
      </div>
    </header>
  );
}
