// Railway Infrastructure as Code for Foresight.
// One service in two environments: each environment deploys from the Git branch
// with the same name (main -> main, dev -> dev) and gets the same variables.
// Secrets are set in Railway and kept here with preserve().
import { defineRailway, github, preserve, project, service } from "railway/iac";

const START =
  "streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true";

export default defineRailway((ctx) => {
  const branch = ctx.environment === "main" ? "main" : "dev";

  const app = service("foresight-app", {
    source: github("RavidEliav/foresight", { branch }),
    start: START,
    healthcheck: "/_stcore/health",
    healthcheckTimeout: 120,
    env: {
      LLM_MODEL: "gpt-4o-mini",
      MOCK_LLM: "false",
      // Set with scripts/push_secrets_to_railway.ps1 (same values in dev and main).
      OPENAI_API_KEY: preserve(),
      RUN_PASSCODE: preserve(),
    },
  });

  return project("foresight", { resources: [app] });
});
