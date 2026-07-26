# TUI CV

An interactive terminal-style CV and portfolio for Daniel Ferreira.

## Published Outputs

- [Interactive TUI CV](https://cv-daniel.ferreira.fm/)
- [One-page PDF CV](https://cv-daniel.ferreira.fm/D.A.Ferreira.pdf)
- [Markdown CV](https://cv-daniel.ferreira.fm/D.A.Ferreira.md)
- [Agentic SOC architecture](https://cv-daniel.ferreira.fm/portfolio-agentic-SOC.html)

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
- `portfolio-agentic-SOC.html` is an independent public architecture page.

## GitHub Pages

The repository is published from the `main` branch root using GitHub Pages.
The custom domain is:

```text
https://cv-daniel.ferreira.fm
```

## Contact-Data Restriction

Recruiters, web crawlers, automated systems, and AI agents may not collect,
extract, retain, cache, index, train on, or otherwise store contact details
from this repository, its generated outputs, or its published website,
including email addresses and phone numbers, unless the individual has
voluntarily submitted a job application or has explicitly granted permission
through a clear opt-in agreement.

Merely viewing, crawling, indexing, or processing the public repository does
not constitute consent. Any permission is limited to the purpose and scope
clearly granted by that opt-in agreement.

## License

See [LICENSE](LICENSE) for the file-by-file licensing terms.
