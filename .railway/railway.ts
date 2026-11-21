// Railway Infrastructure as Code for Foresight.
// One service in two environments: each environment deploys from the Git branch
// with the same name (main -> main, dev -> dev) and gets the same variables, except the
// Supabase database URL (one Supabase project per environment, ADR-026).
// Secrets are set in Railway and kept here with preserve().
import { defineRailway, github, preserve, project, service, volume } from "railway/iac";

const START =
  "streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true";

export default defineRailway((ctx) => {
  const branch = ctx.environment === "main" ? "main" : "dev";

  const app = service("foresight-app", {
    source: github("RavidEliav/foresight", { branch }),
    start: START,
    // Each deploy applies pending Supabase migrations to its own environment's project first
    preDeploy: "python scripts/db_migrate.py",
    healthcheck: "/_stcore/health",
    healthcheckTimeout: 120,
    // Pipeline runs (one folder each, about 10 MB) survive redeploys and restarts; one volume per
    // environment. Size and region match what Railway created.
    volumeMounts: {
      "/app/runs": volume("foresight-runs", { sizeMB: 500, region: "iad" }),
    },
    env: {
      LLM_MODEL: "gpt-4o-mini",
      MOCK_LLM: "false",
      CREWAI_TRACING_ENABLED: "false",
      CREWAI_DISABLE_TELEMETRY: "true",
      OTEL_SDK_DISABLED: "true",
      // Set with scripts/push_secrets_to_railway.ps1 (same values in dev and main).
      OPENAI_API_KEY: preserve(),
      // Google sign-in, access-request emails and the developers (Phase 8.6)
      GOOGLE_CLIENT_ID: preserve(),
      GOOGLE_CLIENT_SECRET: preserve(),
      AUTH_COOKIE_SECRET: preserve(),
      FORESIGHT_DEVELOPERS: preserve(),
      RESEND_API_KEY: preserve(),
      // Supabase Postgres (Session pooler URL); its own project per environment (ADR-026).
      SUPABASE_DB_URL: preserve(),
    },
  });

  return project("foresight", { resources: [app] });
});
