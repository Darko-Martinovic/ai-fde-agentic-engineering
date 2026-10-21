import os

# Tests read only the committed defaults, never a developer's .env. This runs
# before any test module imports a config module.
os.environ["UNDERCOVER_ENV_FILES"] = ".env.defaults"
