import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";

export default function ConfirmPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-sm text-center">
        <CardContent>
          <div className="text-4xl mb-4">📬</div>
          <h1 className="text-lg font-bold mb-2 text-primary">
            Vérifie tes emails
          </h1>
          <p className="text-sm text-muted-foreground mb-4">
            Un lien de confirmation a été envoyé à ton adresse. Clique dessus
            pour activer ton compte.
          </p>
          <p className="text-xs text-muted-foreground">
            En local : consulte{" "}
            <a
              href="http://localhost:54324"
              target="_blank"
              rel="noreferrer"
              className="text-primary hover:underline"
            >
              Inbucket (localhost:54324)
            </a>{" "}
            pour voir l&apos;email.
          </p>
          <Link
            href="/login"
            className="inline-block mt-6 text-sm text-primary hover:underline"
          >
            ← Retour à la connexion
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
