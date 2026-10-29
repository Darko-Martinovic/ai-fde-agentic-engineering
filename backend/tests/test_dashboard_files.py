"""The dashboard's build served beside the API, and the app on AWS Lambda through
a Function URL."""

import base64
import json
from typing import cast

import pytest
from mangum.types import LambdaContext

from backend import dashboard_files
from backend.main import handler

PAGE = "<!doctype html><title>UnderCover</title>"


@pytest.fixture
def build(tmp_path, monkeypatch):
    """A stand-in for the dashboard's build, its index.html and one asset, with
    a secret beside the build that nothing may serve."""
    built = tmp_path / "dist"
    (built / "assets").mkdir(parents=True)
    (built / "index.html").write_text(PAGE, encoding="utf-8")
    (built / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("the secret", encoding="utf-8")
    monkeypatch.setattr(dashboard_files, "BUILD", built)
    return built


def function_url(path, method="GET"):
    """A request as a Lambda Function URL hands it to the function."""
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "undercover.lambda-url.us-east-1.on.aws"},
        "requestContext": {
            "accountId": "anonymous",
            "apiId": "undercover",
            "domainName": "undercover.lambda-url.us-east-1.on.aws",
            "domainPrefix": "undercover",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test",
            },
            "requestId": "test",
            "routeKey": "$default",
            "stage": "$default",
            "time": "29/Oct/2026:12:00:00 +0000",
            "timeEpoch": 0,
        },
        "isBase64Encoded": False,
    }


# What Lambda passes the handler beside the event, which Mangum doesn't read
CONTEXT = cast(LambdaContext, object())


def body(response):
    text = response["body"]
    return base64.b64decode(text).decode() if response["isBase64Encoded"] else text


def test_the_lambda_handler_answers_a_function_url_request():
    response = handler(function_url("/api/health"), CONTEXT)
    assert response["statusCode"] == 200
    assert json.loads(body(response)) == {"status": "ok"}


def test_on_lambda_the_dashboard_and_its_pages_get_index_html(build):
    for path in ("/", "/claims/CLM-1001"):
        response = handler(function_url(path), CONTEXT)
        assert (response["statusCode"], body(response)) == (200, PAGE)


def test_a_built_file_is_served_at_its_own_path(client, build):
    response = client.get("/assets/app.js")
    assert (response.status_code, response.text) == (200, "console.log(1)")


def test_an_unknown_api_path_still_gets_the_apis_404(client, build):
    for method in ("get", "post"):
        response = getattr(client, method)("/api/no-such-thing")
        assert (response.status_code, response.json()) == (404, {"detail": "Not Found"})


def test_a_wrong_method_on_an_api_path_still_gets_the_apis_405(client, build):
    assert client.delete("/api/health").status_code == 405
    assert client.put("/api/claims").status_code == 405


def test_a_path_out_of_the_build_gets_index_html_not_the_file(client, build):
    for path in ("/%2e%2e/secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt"):
        assert client.get(path).text == PAGE


def test_without_a_build_the_backend_answers_as_before(client, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_files, "BUILD", tmp_path / "not-built")
    response = client.get("/")
    assert (response.status_code, response.json()) == (404, {"detail": "Not Found"})
    assert client.get("/api/health").json() == {"status": "ok"}
