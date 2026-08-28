# V&VN licensed console fonts

HK Grotesk (Regular, Bold, Italic) and Raleway Bold are the digital stylesheet typefaces.

Licensed font files are **not** in this repository. Place V&VN-licensed files here when they are supplied:

- `HKGrotesk-Regular`
- `HKGrotesk-Bold`
- `HKGrotesk-Italic`
- `Raleway-Bold`

Until those files are present, the console **fails closed** to the documented system stack:

- body: `ui-sans-serif, system-ui, sans-serif`
- headings, primary buttons and statements: the same stack at `font-weight: 700`

Do not commit unlicensed font binaries. Do not fetch HK Grotesk or Raleway from a public CDN.
