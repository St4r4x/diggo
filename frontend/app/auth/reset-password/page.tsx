"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createSupabaseBrowserClient } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    // Supabase puts the recovery token in the URL fragment after the email
    // link click; onAuthStateChange picks it up and sets the session that
    // updateUser() below relies on.
    const client = createSupabaseBrowserClient();
    const {
      data: { subscription },
    } = client.auth.onAuthStateChange(() => {});
    return () => subscription.unsubscribe();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }

    const client = createSupabaseBrowserClient();
    const { error: updateError } = await client.auth.updateUser({ password });
    if (updateError) {
      setError(updateError.message);
      return;
    }
    setSuccess(true);
    setTimeout(() => {
      window.location.href = "/login";
    }, 1500);
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">Nouveau mot de passe</CardTitle>
        </CardHeader>
        <CardContent>
          {error && <p className="text-sm text-destructive mb-4">{error}</p>}
          {success && (
            <p className="text-sm text-primary mb-4">
              Mot de passe mis à jour ! Redirection...
            </p>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">
                Nouveau mot de passe (min. 6 caractères)
              </Label>
              <Input
                id="password"
                type="password"
                minLength={6}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirm">Confirmer</Label>
              <Input
                id="confirm"
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>
            <Button type="submit">Mettre à jour</Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
