"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import type { SupabaseClient } from "@supabase/supabase-js";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createSupabaseBrowserClient } from "@/lib/supabase";

async function postSession(accessToken: string, refreshToken: string) {
  return fetch("/api/auth/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      access_token: accessToken,
      refresh_token: refreshToken,
    }),
  });
}

export default function LoginPage() {
  const clientRef = useRef<SupabaseClient | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const client = createSupabaseBrowserClient();
    clientRef.current = client;
    const {
      data: { subscription },
    } = client.auth.onAuthStateChange(async (event, session) => {
      if (event === "TOKEN_REFRESHED" && session) {
        await postSession(session.access_token, session.refresh_token);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    const client = clientRef.current;
    if (!client) {
      setError("Client Supabase non initialisé — rechargez la page.");
      return;
    }
    setLoading(true);
    const { data, error: authError } = await client.auth.signInWithPassword({
      email,
      password,
    });
    if (authError) {
      setError(
        `Erreur Supabase: ${authError.message} (status ${authError.status ?? "?"})`
      );
      setLoading(false);
      return;
    }
    if (!data?.session) {
      setError("Connexion échouée: aucune session retournée.");
      setLoading(false);
      return;
    }
    const res = await postSession(
      data.session.access_token,
      data.session.refresh_token
    );
    if (!res.ok) {
      setError(`Erreur serveur: impossible de créer la session (${res.status})`);
      setLoading(false);
      return;
    }
    window.location.href = "/profile";
  }

  async function handleResetPassword() {
    setError(null);
    setSuccess(null);
    const client = clientRef.current;
    if (!client) {
      setError("Client Supabase non initialisé.");
      return;
    }
    if (!email) {
      setError("Entre ton email d'abord.");
      return;
    }
    const { error: resetError } = await client.auth.resetPasswordForEmail(
      email,
      { redirectTo: `${window.location.origin}/auth/reset-password` }
    );
    if (resetError) {
      setError(`Erreur: ${resetError.message}`);
      return;
    }
    setSuccess("Email envoyé ! Vérifie Inbucket sur localhost:54324.");
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">Diggo</CardTitle>
        </CardHeader>
        <CardContent>
          {error && <p className="text-sm text-destructive mb-4">{error}</p>}
          {success && <p className="text-sm text-primary mb-4">{success}</p>}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? "Connexion…" : "Se connecter"}
            </Button>
          </form>
          <p className="text-sm text-muted-foreground mt-4 text-center">
            Pas de compte ?{" "}
            <Link href="/signup" className="text-primary hover:underline">
              Créer un compte
            </Link>
          </p>
          <p className="text-sm text-muted-foreground mt-2 text-center">
            <button
              type="button"
              onClick={handleResetPassword}
              className="hover:underline"
            >
              Mot de passe oublié ?
            </button>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
