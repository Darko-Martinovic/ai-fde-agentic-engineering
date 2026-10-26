import os

# Tests read only the committed defaults, never a developer's .env, never reach
# Supabase, and send nothing to Langfuse. This runs before any test module
# imports a config module.
os.environ["UNDERCOVER_ENV_FILES"] = ".env.defaults"
os.environ.pop("DATABASE_URL", None)
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
