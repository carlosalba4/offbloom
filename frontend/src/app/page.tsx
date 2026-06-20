import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-20">
      <section className="mx-auto flex max-w-2xl flex-col items-center gap-8 text-center">
        <h1 className="font-serif text-5xl font-semibold leading-tight tracking-tight text-foreground sm:text-6xl">
          DetoxApp
        </h1>

        <p className="font-serif text-2xl font-medium text-primary sm:text-3xl">
          Sustituir, no prohibir.
        </p>

        <p className="max-w-md text-lg leading-relaxed text-muted-foreground">
          Recupera tu sueño y tu tiempo de calidad sin renunciar al móvil. En
          lugar de bloquear, te proponemos alternativas reales para cada momento.
        </p>

        <Button asChild size="lg" className="mt-2 px-8 text-base">
          <Link href="/onboarding">Empezar</Link>
        </Button>
      </section>
    </main>
  );
}
