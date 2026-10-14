#!/usr/bin/env python3
"""Unit tests for scripts/jev_series.py — stdlib unittest, no extra deps.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error

import jev_series as jv


# The series ids in the order jev_series.md lists them, plus the escape option.
EXPECTED_ORDER = [
    "gundam_0079",
    "the_08th_ms_team",
    "gundam_0080",
    "gundam_0083",
    "zeta",
    "zz",
    "chars_counterattack",
    "unicorn",
    "hathaways_flash",
    "f91",
    "victory",
    "seed",
    "seed_destiny",
    "seed_freedom",
    "gundam_00",
    "iron_blooded_orphans",
    "witch_from_mercury",
    "g_gundam",
    "gundam_wing",
    "gundam_x",
    "turn_a",
    "build_fighters",
    "gquuuuuux",
    "unknown",
]


class _FakeResponse:
    """Minimal stand-in for the urlopen context manager."""

    def __init__(self, document):
        self._body = json.dumps(document).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _choice_document(choice, **overrides):
    """An OpenRouter success body for the `series` question."""
    answer = {"type": "choice",
              "choice": choice,
              "probabilities": {choice: 0.9, "unknown": 0.1},
              "confidence": 0.88}
    answer.update(overrides)
    return {"model": "jev-1.13.0",
            "answers": {"series": answer},
            "usage": {"input_tokens": 300, "output_tokens": 20}}


def _envelope(result, code=0, message="ok", credits=1):
    """A legacy thejevai.com body wrapping a result payload."""
    return {"code": code, "message": message,
            "data": {"creditsUsed": credits, "result": result}}


def _chat_document(content):
    """A DeepSeek chat-completion body whose message content is `content`."""
    return {"id": "chatcmpl-1",
            "model": jv.DEEPSEEK_MODEL,
            "choices": [{"index": 0,
                         "finish_reason": "stop",
                         "message": {"role": "assistant",
                                     "content": content}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 12,
                      "total_tokens": 412}}


def _http_error(code, body=b'{"message": "boom"}'):
    return urllib.error.HTTPError(jv.JEV_API_URL, code, "err", {},
                                  io.BytesIO(body))


class UrlopenStub:
    """Serve queued items in order; each is a document or an exception.

    The last item repeats once the queue would run dry, so a one-item stub
    answers every call and a two-item stub answers twice.
    """

    def __init__(self, *items):
        self.items = list(items)
        self.requests = []

    @property
    def calls(self):
        return len(self.requests)

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        item = self.items.pop(0) if len(self.items) > 1 else self.items[0]
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class StubbedHttpTestCase(unittest.TestCase):
    """Base: a urlopen stub and a silent sleep, both restored afterwards."""

    def stub_http(self, *items):
        stub = UrlopenStub(*items)
        sleeps = []
        original_open = jv.urllib.request.urlopen
        original_sleep = jv.time.sleep
        jv.urllib.request.urlopen = stub
        jv.time.sleep = sleeps.append
        self.addCleanup(setattr, jv.urllib.request, "urlopen", original_open)
        self.addCleanup(setattr, jv.time, "sleep", original_sleep)
        return stub, sleeps


class EndpointTest(unittest.TestCase):
    def test_targets_the_openrouter_decisions_api(self):
        self.assertEqual(jv.JEV_API_URL,
                         "https://openrouter.ai/api/alpha/decisions")
        # The `~` alias is required: the bare name answers HTTP 400.
        self.assertEqual(jv.JEV_MODEL, "~typesafe/jev-latest")


class SeriesTableTest(unittest.TestCase):
    def test_ids_are_unique_lowercase_ascii(self):
        ids = [series_id for series_id, _name, _description in jv.SERIES]
        self.assertEqual(len(ids), len(set(ids)))
        for series_id in ids:
            with self.subTest(series_id=series_id):
                self.assertTrue(series_id.isascii())
                self.assertRegex(series_id, r"^[a-z][a-z0-9_]*$")

    def test_order_matches_jev_series_md(self):
        self.assertEqual([series_id for series_id, _name, _description
                          in jv.SERIES],
                         EXPECTED_ORDER)

    def test_every_series_has_a_name_and_a_description(self):
        for series_id, name, description in jv.SERIES:
            with self.subTest(series_id=series_id):
                self.assertTrue(name.strip())
                self.assertTrue(description.strip())

    def test_unknown_is_the_last_escape_option(self):
        self.assertEqual(jv.SERIES[-1][0], "unknown")


class PayloadTest(unittest.TestCase):
    def test_default_model_and_state(self):
        payload = jv.build_payload("RX-93 ν高達")
        self.assertEqual(payload["model"], jv.JEV_MODEL)
        self.assertEqual(payload["state"], "RX-93 ν高達")
        question = payload["questions"][jv.QUESTION_ID]
        self.assertEqual(question["type"], "choice")
        self.assertTrue(question["instructions"])

    def test_criteria_cover_every_series_in_order(self):
        question = jv.build_payload("x")["questions"][jv.QUESTION_ID]
        self.assertEqual(list(question["criteria"]), EXPECTED_ORDER)
        for series_id, _name, description in jv.SERIES:
            self.assertEqual(question["criteria"][series_id], description)

    def test_model_override(self):
        payload = jv.build_payload("x", model="other/model")
        self.assertEqual(payload["model"], "other/model")


class ExtractChoiceTest(unittest.TestCase):
    def test_reads_a_valid_choice(self):
        self.assertEqual(jv._extract_choice(_choice_document("seed_destiny")),
                         "seed_destiny")

    def test_unknown_is_a_valid_choice(self):
        self.assertEqual(jv._extract_choice(_choice_document("unknown")),
                         "unknown")

    def test_choice_outside_the_criteria_is_an_error(self):
        with self.assertRaises(RuntimeError) as ctx:
            jv._extract_choice(_choice_document("nonexistent"))
        self.assertIn("nonexistent", str(ctx.exception))

    def test_unusable_documents_are_errors(self):
        for document in ({}, {"answers": {}}, {"answers": {"series": "x"}},
                         {"answers": None}, "not-a-dict"):
            with self.subTest(document=document):
                with self.assertRaises(RuntimeError):
                    jv._extract_choice(document)


class UnwrapTest(unittest.TestCase):
    def test_extracts_the_result_from_the_live_envelope(self):
        result = _choice_document("unicorn")
        self.assertEqual(jv._unwrap(_envelope(result)), result)

    def test_flat_documents_pass_through(self):
        document = _choice_document("seed")
        self.assertEqual(jv._unwrap(document), document)
        self.assertEqual(jv._unwrap("not-a-dict"), "not-a-dict")

    def test_nonzero_code_is_an_api_level_failure(self):
        with self.assertRaises(RuntimeError) as ctx:
            jv._unwrap(_envelope({}, code=-1, message="Invalid API key."))
        self.assertIn("-1", str(ctx.exception))
        self.assertIn("Invalid API key.", str(ctx.exception))


class ClassifyTest(StubbedHttpTestCase):
    def test_happy_path_maps_the_choice_to_the_series_table(self):
        stub, _sleeps = self.stub_http(_choice_document("chars_counterattack"))
        result = jv.classify("RX-93 ν高達", "test-key")
        self.assertEqual(result, {"input": "RX-93 ν高達",
                                  "series": "chars_counterattack",
                                  "name": "馬沙之反擊"})
        self.assertEqual(stub.calls, 1)

    def test_live_envelope_classifies(self):
        inner = _choice_document("gquuuuuux")
        inner["elapsedMs"] = 1401
        inner["usage"] = {"input_tokens": 2226, "output_tokens": 267}
        self.stub_http(_envelope(inner, credits=1))
        result = jv.classify("GQuuuuuuX", "test-key")
        self.assertEqual(result, {"input": "GQuuuuuuX",
                                  "series": "gquuuuuux",
                                  "name": "GQUUUUUUX"})

    def test_live_openrouter_response_classifies(self):
        """The flat Decisions API body, captured live from Jev 1.13."""
        self.stub_http({
            "model": "typesafe/jev-1.13-20260917",
            "answers": {"series": {"type": "choice",
                                   "choice": "chars_counterattack",
                                   "probabilities": {
                                       "chars_counterattack": 0.98,
                                       "unicorn": 0.01,
                                       "unknown": 0.01},
                                   "confidence": 0.97}},
            "usage": {"input_tokens": 337, "output_tokens": 49,
                      "cost": 0.000014154},
            "id": "gen-dec-1791914991-kCJBkL2etojoFiBFvVSj",
            "provider": "TypeSafe",
        })
        result = jv.classify("RX-93 ν高達", "test-key")
        self.assertEqual(result, {"input": "RX-93 ν高達",
                                  "series": "chars_counterattack",
                                  "name": "馬沙之反擊"})

    def test_request_carries_bearer_auth_and_the_payload(self):
        stub, _sleeps = self.stub_http(_choice_document("seed"))
        jv.classify("自由高達", "test-key")

        request = stub.requests[0]
        self.assertEqual(request.full_url, jv.JEV_API_URL)
        self.assertEqual(request.headers.get("Authorization"),
                         "Bearer test-key")
        self.assertEqual(request.headers.get("Content-type"),
                         "application/json")
        # Cloudflare answers urllib's default UA with `403 error code: 1010`,
        # so the request must carry its own explicit User-Agent.
        self.assertEqual(request.headers.get("User-agent"), jv.USER_AGENT)
        self.assertNotIn("Python-urllib", jv.USER_AGENT)
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], jv.JEV_MODEL)
        self.assertEqual(body["state"], "自由高達")
        self.assertEqual(body["questions"][jv.QUESTION_ID]["type"], "choice")

    def test_unknown_series_still_classifies(self):
        self.stub_http(_choice_document("unknown"))
        result = jv.classify("謎之機體", "test-key")
        self.assertEqual(result["series"], "unknown")
        self.assertEqual(result["name"], "無法確定")


class DeepSeekEngineTest(StubbedHttpTestCase):
    def test_chat_payload_carries_the_kit_and_every_series_option(self):
        payload = jv.build_chat_payload("超卓渣古")
        self.assertEqual(payload["model"], jv.DEEPSEEK_MODEL)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        system, user = payload["messages"]
        self.assertEqual(system["role"], "system")
        self.assertIn("超卓渣古", user["content"])
        self.assertIn('{"series"', user["content"])
        for series_id, name, _description in jv.SERIES:
            with self.subTest(series_id=series_id):
                self.assertIn(series_id, user["content"])
                self.assertIn(name, user["content"])

    def test_classify_deepseek_maps_the_choice(self):
        stub, _sleeps = self.stub_http(
            _chat_document('{"series": "build_fighters"}'))
        result = jv.classify_deepseek("[現貨] HGBF 超卓渣古", "test-ds-key")
        self.assertEqual(result, {"input": "[現貨] HGBF 超卓渣古",
                                  "series": "build_fighters",
                                  "name": "創戰者"})
        self.assertEqual(stub.calls, 1)
        request = stub.requests[0]
        self.assertEqual(request.full_url, jv.DEEPSEEK_API_URL)
        self.assertEqual(request.headers.get("Authorization"),
                         "Bearer test-ds-key")
        self.assertEqual(request.headers.get("User-agent"), jv.USER_AGENT)

    def test_401_is_an_auth_error_naming_deepseek(self):
        error = urllib.error.HTTPError(jv.DEEPSEEK_API_URL, 401, "err", {},
                                       io.BytesIO(b'{"error": "bad key"}'))
        self.stub_http(error)
        with self.assertRaises(jv.AuthError) as ctx:
            jv.classify_deepseek("x", "test-ds-key")
        self.assertIn("DeepSeek", str(ctx.exception))
        self.assertIn("API key", str(ctx.exception))

    def test_a_non_json_completion_is_an_error(self):
        self.stub_http(_chat_document("not json"))
        with self.assertRaises(RuntimeError) as ctx:
            jv.classify_deepseek("x", "test-ds-key")
        self.assertIn("no usable completion", str(ctx.exception))

    def test_a_completion_without_choices_is_an_error(self):
        self.stub_http({"choices": []})
        with self.assertRaises(RuntimeError) as ctx:
            jv.classify_deepseek("x", "test-ds-key")
        self.assertIn("no usable completion", str(ctx.exception))

    def test_a_choice_outside_the_criteria_is_an_error(self):
        for content in ('{"series": "nonexistent"}', '{"grade": "hg"}'):
            with self.subTest(content=content):
                self.stub_http(_chat_document(content))
                with self.assertRaises(RuntimeError):
                    jv.classify_deepseek("x", "test-ds-key")


class RetryTest(StubbedHttpTestCase):
    def test_429_then_success_waits_the_first_backoff_step(self):
        stub, sleeps = self.stub_http(_http_error(429),
                                      _choice_document("zeta"))
        result = jv.classify("Z高達", "test-key")
        self.assertEqual(result["series"], "zeta")
        self.assertEqual(stub.calls, 2)
        self.assertEqual(sleeps, [jv.RETRY_BACKOFF_S[0]])

    def test_exhausted_retries_raise_the_last_error(self):
        stub, sleeps = self.stub_http(_http_error(529))
        with self.assertRaises(urllib.error.HTTPError):
            jv.classify("x", "test-key")
        self.assertEqual(stub.calls, len(jv.RETRY_BACKOFF_S) + 1)
        self.assertEqual(sleeps, list(jv.RETRY_BACKOFF_S))

    def test_401_is_not_retried(self):
        stub, sleeps = self.stub_http(_http_error(401))
        with self.assertRaises(jv.AuthError):
            jv.classify("x", "test-key")
        self.assertEqual(stub.calls, 1)
        self.assertEqual(sleeps, [])

    def test_422_is_not_retried_and_names_the_status(self):
        stub, sleeps = self.stub_http(_http_error(422, b'{"detail": "state"}'))
        with self.assertRaises(RuntimeError) as ctx:
            jv.classify("x", "test-key")
        self.assertIn("422", str(ctx.exception))
        self.assertEqual(stub.calls, 1)
        self.assertEqual(sleeps, [])

    def test_500_is_not_retried(self):
        stub, sleeps = self.stub_http(_http_error(500))
        with self.assertRaises(urllib.error.HTTPError):
            jv.classify("x", "test-key")
        self.assertEqual(stub.calls, 1)
        self.assertEqual(sleeps, [])


class ApiKeyTest(unittest.TestCase):
    def test_env_var_wins_over_the_env_file(self):
        original = os.environ.get("JEV_API_KEY")
        real = jv._env_file_value
        os.environ["JEV_API_KEY"] = "from-env"
        jv._env_file_value = lambda key: "from-file"
        try:
            self.assertEqual(jv.load_api_key(), "from-env")
        finally:
            jv._env_file_value = real
            if original is None:
                os.environ.pop("JEV_API_KEY", None)
            else:
                os.environ["JEV_API_KEY"] = original

    def test_falls_back_to_the_env_file(self):
        original = os.environ.pop("JEV_API_KEY", None)
        real = jv._env_file_value
        jv._env_file_value = lambda key: "from-file"
        try:
            self.assertEqual(jv.load_api_key(), "from-file")
        finally:
            jv._env_file_value = real
            if original is not None:
                os.environ["JEV_API_KEY"] = original

    def test_missing_key_raises_auth_error_naming_the_variable(self):
        original = os.environ.pop("JEV_API_KEY", None)
        real = jv._env_file_value
        jv._env_file_value = lambda key: ""
        try:
            with self.assertRaises(jv.AuthError) as ctx:
                jv.load_api_key()
            self.assertIn("JEV_API_KEY", str(ctx.exception))
        finally:
            jv._env_file_value = real
            if original is not None:
                os.environ["JEV_API_KEY"] = original

    def test_deepseek_missing_key_raises_auth_error_naming_the_variable(self):
        original = os.environ.pop("DEEPSEEK_API_KEY", None)
        real = jv._env_file_value
        jv._env_file_value = lambda key: ""
        try:
            with self.assertRaises(jv.AuthError) as ctx:
                jv.load_deepseek_key()
            self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))
        finally:
            jv._env_file_value = real
            if original is not None:
                os.environ["DEEPSEEK_API_KEY"] = original

    def test_optional_deepseek_key_is_empty_when_absent(self):
        original = os.environ.pop("DEEPSEEK_API_KEY", None)
        real = jv._env_file_value
        jv._env_file_value = lambda key: ""
        try:
            self.assertEqual(jv._optional_deepseek_key(), "")
        finally:
            jv._env_file_value = real
            if original is not None:
                os.environ["DEEPSEEK_API_KEY"] = original

    def test_env_file_parser_skips_comments_blanks_and_strips_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\n\nOTHER=1\nJEV_API_KEY=\"sk-quoted\"\n")
            self.assertEqual(jv._read_env_file(path, "JEV_API_KEY"),
                             "sk-quoted")
            self.assertEqual(jv._read_env_file(path, "ABSENT"), "")

    def test_env_file_parser_tolerates_a_missing_file(self):
        self.assertEqual(jv._read_env_file("/no/such/.env", "JEV_API_KEY"), "")

    def test_auth_error_is_not_retryable(self):
        """The retry loop catches HTTPError; a 401 must not be retried."""
        self.assertFalse(issubclass(jv.AuthError, RuntimeError))


class ParseArgsTest(unittest.TestCase):
    def test_splits_names_and_flags(self):
        names, options = jv._parse_args(["--json", "RX-78-2", "沙煞比"])
        self.assertEqual(names, ["RX-78-2", "沙煞比"])
        self.assertTrue(options["json"])
        self.assertEqual(options["model"], jv.JEV_MODEL)

    def test_the_removed_verbose_flag_is_rejected(self):
        with self.assertRaises(ValueError):
            jv._parse_args(["-v", "x"])

    def test_model_flag_takes_a_value(self):
        _names, options = jv._parse_args(["--model", "other/m"])
        self.assertEqual(options["model"], "other/m")

    def test_model_flag_without_a_value_raises(self):
        with self.assertRaises(ValueError):
            jv._parse_args(["--model"])

    def test_unknown_option_raises(self):
        with self.assertRaises(ValueError):
            jv._parse_args(["--nope"])

    def test_engine_defaults_to_auto(self):
        _names, options = jv._parse_args(["x"])
        self.assertEqual(options["engine"], "auto")

    def test_engine_flag_selects_a_valid_engine(self):
        for engine in ("auto", "jev", "deepseek"):
            with self.subTest(engine=engine):
                _names, options = jv._parse_args(["--engine", engine, "x"])
                self.assertEqual(options["engine"], engine)

    def test_engine_flag_without_a_value_raises(self):
        with self.assertRaises(ValueError):
            jv._parse_args(["--engine"])

    def test_unknown_engine_raises(self):
        with self.assertRaises(ValueError):
            jv._parse_args(["--engine", "gpt", "x"])


class CliTest(StubbedHttpTestCase):
    def _run(self, argv, jev_key="test-key", deepseek_key="test-ds-key"):
        stubs = {
            "load_api_key": lambda: jev_key,
            "load_deepseek_key": lambda: deepseek_key,
            "_optional_deepseek_key": lambda: deepseek_key,
        }
        for name, stub in stubs.items():
            real = getattr(jv, name)
            setattr(jv, name, stub)
            self.addCleanup(setattr, jv, name, real)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = jv.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_no_arguments_prints_usage_and_exits_2(self):
        code, _out, err = self._run([])
        self.assertEqual(code, 2)
        self.assertIn("Usage", err)

    def test_help_exits_0(self):
        code, out, _err = self._run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Usage", out)

    def test_one_kit_prints_only_the_series_name(self):
        self.stub_http(_choice_document("witch_from_mercury"))
        code, out, _err = self._run(["風靈高達"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "水星的魔女")

    def test_json_flag_prints_one_object(self):
        self.stub_http(_choice_document("seed"))
        code, out, _err = self._run(["--json", "自由高達"])
        self.assertEqual(code, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload, {"input": "自由高達", "series": "seed",
                                   "name": "SEED"})

    def test_removed_verbose_flag_exits_2(self):
        code, _out, err = self._run(["-v", "Z高達"])
        self.assertEqual(code, 2)
        self.assertIn("Usage", err)

    def test_a_failed_kit_does_not_stop_the_others(self):
        self.stub_http(_http_error(500), _choice_document("seed"))
        code, out, err = self._run(["a", "b"])
        self.assertEqual(code, 1)
        self.assertEqual(out.strip(), "SEED")
        self.assertIn("a", err)

    def test_a_dead_key_without_a_fallback_aborts_immediately(self):
        stub, _sleeps = self.stub_http(_http_error(401))
        code, _out, err = self._run(["a", "b"], deepseek_key="")
        self.assertEqual(code, 1)
        self.assertEqual(stub.calls, 1)
        self.assertIn("API key", err)

    def test_auto_falls_back_to_deepseek_when_jev_rejects_the_key(self):
        stub, _sleeps = self.stub_http(
            _http_error(401, b'{"code": -1, "message": "Invalid API key."}'),
            _chat_document('{"series": "gundam_0079"}'))
        code, out, err = self._run(["RX-78-2 高達"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "初代(0079)")
        self.assertIn("falling back to DeepSeek", err)
        self.assertEqual([r.full_url for r in stub.requests],
                         [jv.JEV_API_URL, jv.DEEPSEEK_API_URL])

    def test_engine_jev_surfaces_a_rejected_key(self):
        stub, _sleeps = self.stub_http(_http_error(401))
        code, _out, err = self._run(["--engine", "jev", "x"])
        self.assertEqual(code, 1)
        self.assertEqual(stub.calls, 1)
        self.assertIn("API key", err)

    def test_auto_falls_back_to_deepseek_when_jev_has_no_credits(self):
        stub, _sleeps = self.stub_http(
            _http_error(402,
                        b'{"code": -1, "message": "Insufficient credits."}'),
            _chat_document('{"series": "build_fighters"}'))
        code, out, err = self._run(["[現貨] HGBF 超卓渣古"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "創戰者")
        self.assertIn("falling back to DeepSeek", err)
        self.assertEqual([r.full_url for r in stub.requests],
                         [jv.JEV_API_URL, jv.DEEPSEEK_API_URL])

    def test_auto_without_a_deepseek_key_reports_the_402(self):
        stub, _sleeps = self.stub_http(_http_error(402))
        code, _out, err = self._run(["x"], deepseek_key="")
        self.assertEqual(code, 1)
        self.assertEqual(stub.calls, 1)
        self.assertIn("402", err)

    def test_engine_jev_never_falls_back(self):
        stub, _sleeps = self.stub_http(_http_error(402))
        code, _out, err = self._run(["--engine", "jev", "x"])
        self.assertEqual(code, 1)
        self.assertEqual(stub.calls, 1)
        self.assertNotIn("falling back", err)

    def test_engine_deepseek_skips_jev_entirely(self):
        stub, _sleeps = self.stub_http(
            _chat_document('{"series": "witch_from_mercury"}'))
        code, out, _err = self._run(["--engine", "deepseek", "風靈高達"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "水星的魔女")
        self.assertEqual([r.full_url for r in stub.requests],
                         [jv.DEEPSEEK_API_URL])


if __name__ == "__main__":
    unittest.main(verbosity=2)
