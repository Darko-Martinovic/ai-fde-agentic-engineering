"""Whether the backend runs on AWS Lambda, which sets AWS_LAMBDA_FUNCTION_NAME in
every function's environment. There, each copy of the function handles one
request at a time, keeps no database connection between requests and seeds
nothing."""

import os


def on_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
