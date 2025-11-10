• Major Issues

  - ivan.py:565 – /index/status imports webindexmanager.getstatus, but that module was deleted (see TODO.md). The import raises at runtime, so the endpoint always 500s. Either remove the route or wire it up to
    the new status helper in hashicorpdocsearch.
  - ivan.py:615-619 – startwebui launches open-webui with both stdout/stderr piped but nothing ever consumes those pipes. As soon as Open Web UI emits enough output, the buffer fills and the subprocess blocks,
    effectively hanging Ivan. Run the child with inherited stdio or spawn a reader thread.

  Moderate Risks

  - ivan.py:682-688 – initializedocsearch runs synchronously during startup. A cold build of the 12k‑page index takes minutes, so the API port stays closed (and the Chrome extension just fails) until crawling
    finishes. Consider moving the build to a managed background job and serving requests with a degraded “index unavailable” mode.
  - ivan.py:134/ivan.py:173 – All backend calls use requests.post with no timeouts. If LM Studio/Ollama hang or the socket stalls, every request thread blocks forever. Add a short connect/read timeout and surface
    clean 504-style errors.
  - ivan.py:518-523 – request.get_json() can return None on bad JSON or missing body; calling .get on None throws a 500. Guard the return value and emit a 400 with a clearer validation message instead.

  Minor Observations

  - ivan.py:648-650 – Updating mutable globals on the imported config module works in single-process mode, but the Flask debug reloader will fork and re-import config, so child processes may ignore CLI overrides.
    Using an explicit config object passed into request handlers would avoid the mismatch.
  - ivan-extension/background.js:54 – The extension assumes data.choices[0].message.content always exists. Any tool-call response (no message.content) or backend error shape will throw and bubble to the console.
    Check the response shape before dereferencing and surface the real error to the user.

  Next steps: fix the broken import, unblock the Open Web UI subprocess, then rerun python tests/test_comparison.py to confirm the search layer still passes regression.