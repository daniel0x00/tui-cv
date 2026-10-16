# TUI CV

An interactive terminal-style CV and portfolio for Daniel Ferreira.

## Published Outputs

- [Interactive TUI CV](https://cv-daniel.ferreira.fm/)
- [One-page PDF CV](https://cv-daniel.ferreira.fm/D.A.Ferreira.pdf)
- [Markdown CV](https://cv-daniel.ferreira.fm/D.A.Ferreira.md)
- [Agentic SOC case study](https://daniel.ferreira.fm/portfolio-agentic-SOC.html)
- [Identical GitHub Pages mirror](https://cv-daniel.ferreira.fm/portfolio-agentic-SOC.html)

The TUI supports keyboard commands and clickable command controls. Start with
`/help`.

## Build

Requirements:

- Python 3
- Google Chrome or Chromium for PDF generation

Validate the configuration:

```sh
python3 build.py --check
```

Build all public outputs:

```sh
python3 build.py tui md pdf --max-pages 1
```

Generated files are:

- `index.html`
- `D.A.Ferreira.md`
- `D.A.Ferreira.pdf`

Do not edit generated files directly. Rebuild them from `config.json` and the
templates.

## Source Of Truth

- `config.json` contains the CV content and output configuration.
- `template-TUI.html` contains the interactive terminal interface.
- `template-CV.html` contains the print/PDF layout.
- `build.py` generates the public outputs.
- `portfolio-agentic-SOC.html`, `soc.css` and `soc.js` are the generated case-study mirror. Their editorial source is `socCaseStudy` in the `portfolio-cv` project's `content/cv.json`; its renderer and presentation are `src/soc.*`. Rebuild there, then copy the three `dist/` files here byte-for-byte. Both sites use the Cloudflare canonical URL; do not hand-edit the mirror.

The Markdown export can append an additional source Markdown file through
`outputs.md.appendix` in `config.json`. The appendix is included only in
`D.A.Ferreira.md`; it is not included in the TUI or PDF. Appendix headings are
automatically nested below the generated `## Appendix` heading.

## GitHub Pages

The repository is published from the `main` branch root using GitHub Pages.
The custom domain is:

```text
https://cv-daniel.ferreira.fm
```

### SOC mirror release — 16 October 2026

The case study now uses a concise continuous layout, an animated AI illustration, sequential model/tool architecture and optional motion. All SOC links in the TUI, Markdown appendix and one-page PDF point to the Cloudflare canonical page; the original GitHub Pages URL remains a full mirror.

Verification before publication: `python3 build.py --check` and `python3 build.py tui md pdf --max-pages 1` passed; the PDF has one A4 page and both SOC hyperlink annotations use the canonical URL. The TUI's `#autotest` passed 85/85 assertions in Orca with no console errors. The owner approved Orca for this release because cmux was unavailable. The mirrored page's native navigation and keyboard motion toggle were exercised in Orca; its HTML/CSS/JavaScript matched the checked Cloudflare build byte-for-byte. Independent QA passed and the public-file/PDF privacy audit was clean.

## Privacy

See [PRIVACY.md](PRIVACY.md) for contact-data collection and permitted-use
requirements.

## License

See [LICENSE](LICENSE) for the file-by-file licensing terms.
