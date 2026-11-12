import type { FormEvent, JSX } from "react";
import { useState } from "react";
import { Link, useSearch } from "@tanstack/react-router";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { loginLocalUser } from "../lib/api";
import { normalizeNextPath } from "../lib/navigation";
import { useAuth } from "../lib/useAuth";

export function LoginPage(): JSX.Element {
  const search = useSearch({ from: "/login" });
  const { bootstrapRegistrationRequired, refreshUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await loginLocalUser({ email, password });
      await refreshUser();
      window.location.assign(normalizeNextPath(search.next));
    } catch (submitError) {
      console.error("Local login failed:", submitError);
      setError("Unable to sign in with that email and password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="container mx-auto flex min-h-[70vh] items-center justify-center px-4 py-16">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>
            Sign in to your self-hosted VigilWeave workspace.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                autoComplete="email"
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                autoComplete="current-password"
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : null}
            <Button className="w-full" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>
          {bootstrapRegistrationRequired ? (
            <p className="text-sm text-muted-foreground">
              This instance still needs its first admin user.{" "}
              <Link
                className="text-primary underline-offset-4 hover:underline"
                to="/setup"
                search={{ next: normalizeNextPath(search.next) }}
              >
                Complete setup
              </Link>
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
