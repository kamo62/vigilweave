import type { JSX } from "react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";

import { Spinner } from "../components/ui/spinner";

export function AuthCallbackPage(): JSX.Element {
  const navigate = useNavigate();
  const search = useSearch({ from: "/auth/callback" });
  const [error, setError] = useState<string | null>(null);
  const redirectTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    const scheduleRedirect = (to: "/" | "/login") => {
      if (redirectTimeoutRef.current !== null) {
        window.clearTimeout(redirectTimeoutRef.current);
      }
      redirectTimeoutRef.current = window.setTimeout(() => {
        void navigate({ to, replace: true });
      }, 3000);
    };

    const handleCallback = async () => {
      const errorParam = search.error;
      const errorDescription = search.error_description;

      if (errorParam) {
        setError(errorDescription || errorParam);
        scheduleRedirect("/");
        return;
      }

      setError("This authentication callback is no longer valid. Start sign-in again.");
      scheduleRedirect("/login");
    };

    void handleCallback();

    return () => {
      if (redirectTimeoutRef.current !== null) {
        window.clearTimeout(redirectTimeoutRef.current);
      }
    };
  }, [navigate, search]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-destructive mb-4">
            Authentication Failed
          </h1>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-sm text-muted-foreground">
            Redirecting you back...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <Spinner className="h-12 w-12 mx-auto mb-4" />
        <h1 className="text-2xl font-bold mb-2">Completing Sign In</h1>
        <p className="text-muted-foreground">
          Please wait while we authenticate you...
        </p>
      </div>
    </div>
  );
}
