import type { FormEvent, JSX } from "react";
import { useState } from "react";
import { Link, useSearch } from "@tanstack/react-router";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { setupLocalUser } from "../lib/api";
import { normalizeNextPath } from "../lib/navigation";
import { useAuth } from "../lib/useAuth";

export function SetupPage(): JSX.Element {
  const search = useSearch({ from: "/setup" });
  const { refreshUser, refreshCapabilities } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await setupLocalUser({ name, email, password });
      await refreshUser();
      await refreshCapabilities();
      window.location.assign(normalizeNextPath(search.next));
    } catch (submitError) {
      console.error("Local bootstrap setup failed:", submitError);
      setError(
        "Unable to complete local admin setup. Refresh the page and confirm this instance has not already been initialized.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="container mx-auto flex min-h-[70vh] items-center justify-center px-4 py-16">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Set up your first admin</CardTitle>
          <CardDescription>
            This self-hosted VigilWeave instance needs an initial local admin account before anyone can sign in.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1">
              <Label htmlFor="name">Name</Label>
              <Input
                autoComplete="name"
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
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
                autoComplete="new-password"
                id="password"
                minLength={8}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : null}
            <Button className="w-full" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Creating admin..." : "Create admin account"}
            </Button>
          </form>
          <p className="text-sm text-muted-foreground">
            Already initialized this instance?{" "}
            <Link
              className="text-primary underline-offset-4 hover:underline"
              to="/login"
              search={{ next: normalizeNextPath(search.next), invite: undefined }}
            >
              Go to login
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
