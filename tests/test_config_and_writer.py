import os
from types import SimpleNamespace

import pytest

from typesafe_computer_use import config
from typesafe_computer_use.calls import Calls, MeteredWriter
from typesafe_computer_use.config import (
    answer_model,
    custom_writer_endpoint,
    load_dotenv,
    writer_api_key,
    writer_base_url,
    writer_model,
)
from typesafe_computer_use.writer import WriterError, compose_url, make_writer, parse_json, provider, valid_url


def test_dotenv_sets_only_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("CLICKER_TEST_PRESENT", "keep")
    monkeypatch.delenv("CLICKER_TEST_NEW", raising=False)
    (tmp_path / ".env").write_text('# comment\nCLICKER_TEST_PRESENT=override\nCLICKER_TEST_NEW="quoted value"\nbroken line\n')
    load_dotenv(tmp_path / ".env")
    assert os.environ["CLICKER_TEST_PRESENT"] == "keep"
    assert os.environ["CLICKER_TEST_NEW"] == "quoted value"


def test_dotenv_missing_file_is_fine(tmp_path):
    load_dotenv(tmp_path / "nope.env")


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("http://localhost:8081", "http://localhost:8081"),
        ("http://localhost:8081/", "http://localhost:8081"),
        ("http://localhost:8081/v1", "http://localhost:8081"),
        ("http://localhost:8081/v1/messages", "http://localhost:8081"),
        ("https://proxy.example.com/v1/messages/", "https://proxy.example.com"),
    ],
)
def test_the_writer_endpoint_accepts_any_of_its_spellings(given, expected, clean_env):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", given)
    assert writer_base_url() == expected


def test_the_anthropic_base_url_is_left_to_the_sdk(clean_env):
    clean_env.setenv("ANTHROPIC_BASE_URL", "http://localhost:8081")
    assert writer_base_url() is None


def test_an_endpoint_of_its_own_needs_no_key(clean_env, endpoint):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", f"{endpoint.url}/v1/messages")
    assert compose_url(make_writer(), "open example", []) == "https://example.com"
    (request,) = endpoint.seen
    assert request["path"] == "/v1/messages"
    assert request["headers"]["x-api-key"] == "not-needed"


def test_the_endpoint_key_goes_to_the_endpoint_and_no_anthropic_credential_does(clean_env, endpoint):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", endpoint.url)
    clean_env.setenv("CLICKER_WRITER_API_KEY", "proxy-key")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-real")
    clean_env.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-real")
    compose_url(make_writer(), "open example", [])
    headers = endpoint.seen[0]["headers"]
    assert headers["x-api-key"] == "proxy-key"
    assert headers["authorization"] == "Bearer proxy-key"
    assert not any("sk-ant-real" in v or "oauth-real" in v for v in headers.values())


def test_a_bearer_token_still_goes_out_as_a_bearer_token(clean_env, endpoint):
    clean_env.setenv("ANTHROPIC_BASE_URL", endpoint.url)
    clean_env.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-real")
    compose_url(make_writer(), "open example", [])
    headers = endpoint.seen[0]["headers"]
    assert headers["authorization"] == "Bearer oauth-real"
    assert "x-api-key" not in headers


def test_without_credentials_or_an_endpoint_there_is_no_writer(clean_env):
    assert make_writer() is None


def test_a_custom_endpoint_is_told_the_schema_in_the_prompt(clean_env, endpoint):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", endpoint.url)
    endpoint.state["reply"] = 'Here you go:\n```json\n{"ok": true, "url": "https://example.com", "reason": "x"}\n```'
    # Metered, as the runner hands it out.
    assert compose_url(MeteredWriter(make_writer(), Calls()), "open example", []) == "https://example.com"
    assert '"required": ["ok", "url", "reason"]' in endpoint.seen[0]["body"]["system"]
    # Thinking on by default would spend the whole 200-token budget and leave no text.
    assert endpoint.seen[0]["body"]["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize(
    ("env", "custom"),
    [
        ({}, False),
        ({"ANTHROPIC_BASE_URL": "https://api.anthropic.com"}, False),
        ({"ANTHROPIC_BASE_URL": "http://localhost:1234"}, True),
        ({"CLICKER_WRITER_BASE_URL": "http://localhost:1234/v1/messages"}, True),
    ],
)
def test_the_endpoint_is_custom_whichever_variable_names_it(clean_env, env, custom):
    for name, value in env.items():
        clean_env.setenv(name, value)
    assert custom_writer_endpoint() is custom


def test_anthropic_itself_gets_the_schema_only_through_output_config(clean_env, monkeypatch):
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    writer = make_writer()
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"ok": false, "url": "", "reason": ""}')])

    monkeypatch.setattr(writer.messages, "create", create)
    compose_url(writer, "open example", [])
    assert "schema" not in sent["system"]
    assert "thinking" not in sent
    assert sent["output_config"]["format"]["schema"]["required"] == ["ok", "url", "reason"]


def test_the_startup_line_leaves_credentials_out_of_the_url(clean_env):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", "https://user:secret@proxy.example.com/v1/messages")
    line = provider(make_writer())
    assert line.startswith("https://proxy.example.com (anthropic API)  models:")
    assert "secret" not in line


GATEWAY = "https://ai-gateway.vercel.sh"


@pytest.mark.parametrize(("api", "path"), [("anthropic", "/v1/messages"), ("openai", "/v1/chat/completions")])
def test_vercels_gateway_gets_vercels_key_and_its_own_model_names(clean_env, endpoint, api, path):
    clean_env.setattr(config, "VERCEL_GATEWAY_HOST", "127.0.0.1")  # the local endpoint stands in for the gateway
    clean_env.setenv("CLICKER_WRITER_API", api)
    clean_env.setenv("CLICKER_WRITER_BASE_URL", f"{endpoint.url}/v1")
    clean_env.setenv("AI_GATEWAY_API_KEY", "vck-gateway")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-real")
    compose_url(make_writer(), "open example", [])
    (request,) = endpoint.seen
    assert request["path"] == path
    assert request["headers"]["authorization"] == "Bearer vck-gateway"
    assert not any("sk-ant-real" in v for v in request["headers"].values())
    assert request["body"]["model"] == "anthropic/claude-haiku-4.5"
    assert answer_model() == "anthropic/claude-sonnet-5"


def test_a_gateway_key_goes_to_the_gateway_alone(clean_env, endpoint):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", endpoint.url)
    clean_env.setenv("AI_GATEWAY_API_KEY", "vck-gateway")
    clean_env.setenv("VERCEL_OIDC_TOKEN", "oidc-gateway")
    compose_url(make_writer(), "open example", [])
    headers = endpoint.seen[0]["headers"]
    assert headers["x-api-key"] == "not-needed"
    assert not any("gateway" in v for v in headers.values())
    assert endpoint.seen[0]["body"]["model"] == config.DEFAULT_WRITER_MODEL


@pytest.mark.parametrize(
    ("env", "key"),
    [
        ({"AI_GATEWAY_API_KEY": "vck", "VERCEL_OIDC_TOKEN": "oidc"}, "vck"),
        ({"VERCEL_OIDC_TOKEN": "oidc"}, "oidc"),
        ({"CLICKER_WRITER_API_KEY": "mine", "AI_GATEWAY_API_KEY": "vck"}, "mine"),
    ],
)
def test_the_gateway_key_is_the_writers_own_then_vercels(clean_env, env, key):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", f"{GATEWAY}/v1/messages")
    for name, value in env.items():
        clean_env.setenv(name, value)
    assert writer_api_key() == key
    assert make_writer().api_key == key


def test_the_gateway_without_a_key_stops_before_the_run(clean_env):
    clean_env.setenv("CLICKER_WRITER_BASE_URL", GATEWAY)
    with pytest.raises(ValueError, match="AI_GATEWAY_API_KEY"):
        make_writer()


def test_claude_code_style_gateway_setup_gets_the_gateway_model_names_unless_others_are_named(clean_env):
    clean_env.setenv("ANTHROPIC_BASE_URL", GATEWAY)
    clean_env.setenv("ANTHROPIC_AUTH_TOKEN", "vck-gateway")
    assert (writer_model(), answer_model()) == (config.VERCEL_GATEWAY_WRITER_MODEL, config.VERCEL_GATEWAY_ANSWER_MODEL)
    assert writer_api_key() is None  # the SDK sends ANTHROPIC_AUTH_TOKEN there itself
    clean_env.setenv("CLICKER_WRITER_MODEL", "openai/gpt-5-mini")
    clean_env.setenv("CLICKER_ANSWER_MODEL", "google/gemini-3.5-flash")
    assert (writer_model(), answer_model()) == ("openai/gpt-5-mini", "google/gemini-3.5-flash")


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"fill": true}', {"fill": True}),
        ('```json\n{"fill": false}\n```', {"fill": False}),
        ('Sure thing:\n{"fill": true, "text": "hi"}\nHope that helps.', {"fill": True, "text": "hi"}),
    ],
)
def test_the_writer_reply_is_read_whether_or_not_it_came_plain(reply, expected):
    assert parse_json(reply) == expected


def test_a_reply_without_any_json_says_so():
    with pytest.raises(WriterError, match="without usable JSON"):
        parse_json("I am not able to help with that.")


def test_valid_url():
    assert valid_url("https://www.cnn.com")
    assert valid_url("https://news.ycombinator.com/newest")
    assert not valid_url("http://www.cnn.com")
    assert not valid_url("https://localhost")
    assert not valid_url("https://www.cnn.com/a b")
    assert not valid_url("")
