# TUI-CV agent guide

## Architecture

- `config.json` is the source of truth for public CV and TUI content plus output-specific presentation settings. This includes `contact.note` and `contact.noteColor`.
- `outputs.tui` owns `sections`. `outputs.pdf` owns `filename`, `header`, `footer`, `fontSizes`, and `sections`. `outputs.md` owns `filename`, `enabled`, `header`, `footer`, and `sections`.
- `template-TUI.html` contains the interactive terminal SPA: HTML, CSS, JavaScript, and the `#autotest` suite.
- `build.py` has explicit `tui`, `md`, and `pdf` targets. It injects `config.json` into `template-TUI.html` and writes generated `index.html`.
- `template-CV.html` contains the editable A4 CV document shell and print CSS. Its `%%CV_*%%` placeholders are filled by the PDF target in `build.py`.
- `build.py` renders escaped content fragments from `config.json`, writes the configured Markdown output when enabled, creates temporary `.cv-print.html`, and exports the configured PDF output.
- `index.html`, the configured PDF and optional Markdown outputs, and `.cv-print.html` are generated artifacts. Never edit them by hand.
- `portfolio-autonomous-SOC.html` is an independent public static page.

Edit `config.json` for copy, `template-TUI.html` for the web interface, and `template-CV.html` for the print layout. Do not duplicate content between templates.

## Ownership

- Use `content-editor` for `config.json` copy only.
- Use `ui-engineer` for `template-TUI.html`, the TUI export portion of `build.py`, TUI behavior, and autotests.
- Use `pdf-publisher` for `template-CV.html`, the PDF/Markdown export portions of `build.py`, and PDF layout.
- Use `qa-tester` to verify all generated artifacts after implementation and before releases.
- Use `privacy-auditor` to scan public sources and the generated PDF plus optional Markdown output after public-content changes and before releases.
- Use `deploy-engineer` only when the user explicitly requests deployment; it publishes the generated site and CV artifacts.

Preserve unrelated work. Use `apply_patch` for manual edits. Keep the config-driven design and existing terminal visual language; do not add libraries or build tooling without a concrete need.

## Build And PDF Checks

After TUI or content changes, run:

```sh
python3 build.py --check
python3 build.py tui md pdf
```

After CV content, template, or exporter changes, run:

```sh
python3 build.py pdf --max-pages 1
```

The PDF must remain one A4 page unless the user explicitly authorizes a different limit. The PDF target validates every required `%%CV_*%%` placeholder and rejects unresolved placeholders.

## cmux Browser Testing

Use cmux's WKWebView browser surfaces for every local HTML, UI, and interaction test. Do not launch a native browser.

1. Identify and target the caller workspace, not the visually focused one:

```sh
cmux identify --json
```

2. Start `python3 -m http.server 8765 --bind 127.0.0.1` in a visible cmux helper terminal in the caller workspace. Keep the server in that helper pane for the duration of the test; do not use detached processes.

3. Open the site in the caller workspace and retain the returned `surface:N` reference:

```sh
cmux --json browser open \
  "http://127.0.0.1:8765/index.html#autotest" \
  --workspace "${CMUX_WORKSPACE_ID:-}"
cmux browser surface:N wait --load-state complete --timeout-ms 15000
cmux browser surface:N get title
cmux browser surface:N errors list
```

4. The in-page autotest passes only if the title begins `TESTS PASS`. Re-snapshot after any interaction and inspect console errors before reporting success:

```sh
cmux browser surface:N snapshot --interactive --compact
cmux browser surface:N console list
cmux browser surface:N screenshot --out /tmp/tui-cv-ui.png
```

5. Test responsive changes at desktop and mobile viewports when the installed cmux release supports `viewport`; otherwise report that the viewport check could not run. Also exercise changed commands, keyboard interactions, theme changes, and links through the cmux surface.

6. Preview static pages through the local server. For an intermediate CV preview, run `python3 build.py pdf --keep-html` and open its exact `file://` URL in a cmux browser surface, then remove `.cv-print.html` when finished.

7. Clean up after verification. Record every browser/helper surface created by the agent, stop any foreground helper server, and close only those agent-created surfaces:

```sh
cmux close-surface --workspace "${CMUX_WORKSPACE_ID:-}" --surface surface:<browser-created-by-agent>
cmux close-surface --workspace "${CMUX_WORKSPACE_ID:-}" --surface surface:<helper-created-by-agent>
```

Close browser tabs after use even when the test passes. If a pre-existing helper pane was reused, close only the browser surface created for this test and leave the pane and its original surfaces intact. Never close the caller terminal, user-created tabs, or user-created panes. Remove temporary `.cv-print.html` files after previews.

Use explicit `--workspace "${CMUX_WORKSPACE_ID:-}"` flags. Do not select workspaces, focus panes, move surfaces, or close user surfaces unless the user explicitly requests it.

## Browser And PDF Policy

- Never use `open -a "Google Chrome"`, Safari, Firefox, Playwright, Puppeteer, Selenium, or a Chrome driver for local HTML testing.
- Do not grant agent permissions for direct Chrome launches.
- The sole exception is the `build.py pdf` subprocess that invokes Chrome or Chromium with `--headless=new` strictly to render the requested PDF. It is not a UI-test browser and must not be used for browser testing, screenshots, or autotests.

## Release Gates

Before a public release or deployment, run the build checks, cmux browser autotest, PDF validation when CV output is affected, and the privacy audit. The privacy audit must scan all public files for employer-internal names, hostnames, tenant identifiers, secrets, and unsanitized operational details. Do not deploy, commit, or push unless the user explicitly asks.
