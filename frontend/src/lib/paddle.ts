export interface PaddleCheckoutLaunchConfig {
  environment: "sandbox" | "production";
  clientToken: string;
  priceId: string;
  successUrl: string;
  email?: string | null;
  customData?: Record<string, unknown>;
}

interface PaddleCheckoutSettings {
  allowLogout?: boolean;
  displayMode?: "overlay" | "inline";
  successUrl?: string;
  theme?: "light" | "dark";
  variant?: "one-page" | "multi-page";
}

interface PaddleCheckoutOpenOptions {
  settings?: PaddleCheckoutSettings;
  items: Array<{
    priceId: string;
    quantity?: number;
  }>;
  customer?: {
    email?: string | null;
  };
  customData?: Record<string, unknown>;
}

interface PaddleGlobal {
  Environment: {
    set: (environment: "sandbox") => void;
  };
  Initialize: (config: { token: string }) => void;
  Checkout: {
    open: (options: PaddleCheckoutOpenOptions) => void;
  };
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

let paddleScriptPromise: Promise<PaddleGlobal> | null = null;
let initializedConfig: { token: string; environment: "sandbox" | "production" } | null = null;

function loadPaddleScript(): Promise<PaddleGlobal> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Paddle checkout requires a browser environment"));
  }
  if (window.Paddle) {
    return Promise.resolve(window.Paddle);
  }
  if (paddleScriptPromise) {
    return paddleScriptPromise;
  }

  paddleScriptPromise = new Promise<PaddleGlobal>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[src="https://cdn.paddle.com/paddle/v2/paddle.js"]',
    );
    if (existingScript) {
      existingScript.addEventListener("load", () => {
        if (!window.Paddle) {
          reject(new Error("Paddle.js loaded without exposing the Paddle global"));
          return;
        }
        resolve(window.Paddle);
      });
      existingScript.addEventListener("error", () => {
        reject(new Error("Failed to load Paddle.js"));
      });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://cdn.paddle.com/paddle/v2/paddle.js";
    script.async = true;
    script.onload = () => {
      if (!window.Paddle) {
        reject(new Error("Paddle.js loaded without exposing the Paddle global"));
        return;
      }
      resolve(window.Paddle);
    };
    script.onerror = () => {
      reject(new Error("Failed to load Paddle.js"));
    };
    document.head.append(script);
  });

  return paddleScriptPromise;
}

async function getInitializedPaddle(
  environment: "sandbox" | "production",
  clientToken: string,
): Promise<PaddleGlobal> {
  const paddle = await loadPaddleScript();

  if (initializedConfig) {
    if (
      initializedConfig.token !== clientToken ||
      initializedConfig.environment !== environment
    ) {
      throw new Error("Paddle.js is already initialized with a different configuration");
    }
    return paddle;
  }

  if (environment === "sandbox") {
    paddle.Environment.set("sandbox");
  }
  paddle.Initialize({ token: clientToken });
  initializedConfig = { token: clientToken, environment };
  return paddle;
}

export async function openPaddleOverlayCheckout(
  config: PaddleCheckoutLaunchConfig,
): Promise<void> {
  const paddle = await getInitializedPaddle(config.environment, config.clientToken);
  paddle.Checkout.open({
    settings: {
      displayMode: "overlay",
      variant: "one-page",
      theme: "light",
      successUrl: config.successUrl,
      allowLogout: !config.email,
    },
    items: [{ priceId: config.priceId, quantity: 1 }],
    customer: config.email ? { email: config.email } : undefined,
    customData: config.customData,
  });
}
