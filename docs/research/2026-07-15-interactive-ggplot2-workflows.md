# Interactive ggplot2 workflows

**Date:** 2026-07-15  
**Question:** How should users change plot parameters and see a ggplot2 figure update?

## Recommendation

Extend this repository's existing **controls -> JSON spec -> webR worker -> R/ggplot2 -> SVG** workflow. It already implements parameter-driven rerendering, preserves the project's static-hosting and no-data-egress design, and keeps R as the source of statistical and graphical truth.

Use Shiny as the baseline for a new, conventional server-backed R product, not as a migration target here. Add `plotly::ggplotly()` or ggiraph only when the requirement is interaction *inside* the rendered chart—hover tooltips, pan/zoom, brushing, or mark selection—not merely changing controls and rebuilding the plot. Parameterized Quarto is suited to pre-rendered report variants, not a live application.

## What the repository already has

The desired workflow is already present in two analyses:

- [Kaplan-Meier experiment controls](../../web/guided/guided-analysis.js) and [Summary experiment controls](../../web/guided/summary/guided-summary.js) patch `demoOptions` and call a shared rerun callback.
- [The guided shell](../../web/guided/shell.js) builds a typed spec, sends it through `runFigure()`, displays returned SVG/text, caches results by context, guards reset/tab races, and disables experiment controls while a request is in flight so an older response cannot contradict the visible controls.
- [app.js](../../web/app.js) serializes the spec as JSON and posts it to a Web Worker. [worker.js](../../web/worker.js) runs R via webR, while [R/dispatch.R](../../R/dispatch.R) validates the figure key, calls the relevant `fig_*()` function, and serializes the ggplot as SVG.

This is a browser-side reactive rerender architecture even though it is not Shiny. webR officially runs the R interpreter on the user's machine without an R server, which matches this project's privacy and GitHub Pages constraints. Its documentation also warns that the API is under active development and mobile browsers may impose WebAssembly memory limits; production should therefore pin a tested webR release instead of relying indefinitely on `latest`. [webR overview](https://docs.r-wasm.org/webr/latest/)

## Recommended implementation pattern

For each adjustable plot option:

1. Add a bounded UI control and a default in the analysis's `createGuidedShell()` config.
2. Patch only that option in `demoOptions`; use the existing rerun callback.
3. Put the option into the analysis's `build*Spec()` result.
4. Validate and clamp it in R before applying it to the ggplot layer, scale, coordinate system, or theme.
5. Test both the R result and the browser control-to-SVG flow.

Prefer a small allow-listed schema—such as `point_size`, `alpha`, `show_ci`, `horizon`, and `theme`—over accepting arbitrary R or ggplot expressions. If users choose columns by name, ggplot2's official programming guidance recommends `.data[[column_name]]`; `aes_string()` is deprecated. [Using ggplot2 in packages](https://ggplot2.tidyverse.org/articles/ggplot2-in-packages.html)

For checkboxes and selects, the existing `change` event plus disabled-in-flight controls is a good first version. For continuously updating sliders, either rerender on release (`change`) or add a short debounce and a latest-request-wins generation token before enabling overlapping changes. Shiny exposes the same performance principle through `debounce()`/`throttle()`: reduce downstream invalidations when inputs are chatty and rendering is expensive. [Shiny debounce reference](https://shiny.posit.co/r/reference/shiny/latest/debounce.html)

## Alternatives

| Approach | Architecture and strengths | Limitations and deployment | Fit here |
|---|---|---|---|
| Existing webR + ggplot2 SVG | UI changes a JSON option; R rebuilds an exact ggplot and returns SVG. No application server and user data stays in the browser. | First use downloads R/packages; every change that affects the figure requires an R rerender; the SVG has no native hover/brush behavior. | **Recommended.** It is already implemented and deployed statically. |
| Shiny `renderPlot()` | Inputs referenced inside `renderPlot()` form reactive dependencies; Shiny reruns only invalidated outputs. `plotOutput()` also supports click, hover, and brush inputs. [Official ggplot2 plot component](https://shiny.posit.co/r/components/outputs/plot-ggplot2/) [Reactive dependency behavior](https://shiny.posit.co/r/getstarted/shiny-basics/lesson6/) | Requires a running R server. Official deployment choices include shinyapps.io, Shiny Server, and Posit Connect. [Shiny deployment](https://shiny.posit.co/r/deploy) A normal Shiny browser maintains a connection to server-side R, which changes this project's no-egress architecture. [Shiny reconnection architecture](https://shiny.posit.co/r/articles/improve/reconnecting/) | Best baseline for a separate server-backed product, especially for databases, authentication, or computations unsuitable for webR. Not a good migration for this repository. |
| `plotly::ggplotly()` | Converts a ggplot into Plotly JSON rendered by plotly.js; provides hover, legend toggling, pan, and zoom with little initial code. [Plotly ggplot2 guide](https://plotly.com/ggplot2/getting-started/) | Conversion is not exact: Plotly states that translating ggplot layers requires assumptions that may not suit a plot, and its site says R documentation is being retired. Integrating the htmlwidget into the current webR/SVG return contract would require a prototype for package availability, dependencies, sizing, exports, and CSP. | Use only when pan/zoom/hover is a real requirement and accept visual regression testing plus a different output contract. |
| ggiraph | A ggplot2 extension that adds `tooltip`, `data_id`, and `onclick` aesthetics to interactive geoms, then produces an SVG-based htmlwidget; Shiny can expose selected IDs reactively. [ggiraph overview](https://davidgohel.github.io/ggiraph/) | Requires changing layers to `*_interactive()` and returning an htmlwidget rather than the repository's plain SVG string. The docs note that interactive aesthetics can alter implicit grouping, so some plots need explicit `group`. [girafe reference](https://davidgohel.github.io/ggiraph/reference/girafe.html) | Prefer over Plotly when tooltips or selection should stay close to ggplot's SVG/geoms, but prototype the webR dependency/output path first. |
| Quarto parameters / OJS | Quarto parameters create document variants at render time using `-P` or `--execute-params`. [Quarto parameters](https://quarto.org/docs/computations/parameters.html) OJS is reactive and client-side; R can preprocess data once and pass it to OJS. [Quarto OJS](https://quarto.org/docs/interactive/ojs/) | Parameters are not a live end-user control system. OJS live interactions run in JavaScript rather than rebuilding ggplot2; using R reactively in Quarto requires `server: shiny` and a Shiny server. [Quarto Shiny](https://quarto.org/docs/interactive/shiny/) | Useful for reports/tutorials or precomputed scenarios, not this app's primary workflow. |

## Minimal Shiny baseline for a separate product

This is the conventional server-backed version of the idea:

```r
library(shiny)
library(ggplot2)

ui <- fluidPage(
  selectInput("x", "X", names(mtcars), selected = "wt"),
  selectInput("y", "Y", names(mtcars), selected = "mpg"),
  sliderInput("size", "Point size", 1, 8, 3),
  plotOutput("plot")
)

server <- function(input, output, session) {
  output$plot <- renderPlot({
    ggplot(mtcars, aes(x = .data[[input$x]], y = .data[[input$y]])) +
      geom_point(size = input$size) +
      theme_minimal()
  })
}

shinyApp(ui, server)
```

Reading `input$x`, `input$y`, and `input$size` inside `renderPlot()` is enough for Shiny to track dependencies and redraw the plot when those values change. The equivalent behavior in this repository should remain explicit: patch the option, rebuild the JSON spec, call `runFigure()`, and replace the returned SVG.

## Decision rule

- **Controls change plot parameters:** extend the existing webR rerender pipeline.
- **Users must hover, zoom, brush, or select marks:** prototype ggiraph first for SVG/ggplot affinity; compare Plotly if richer pan/zoom behavior matters more than exact ggplot translation.
- **A server, database, authentication, or heavy shared computation is required:** build a separate Shiny application.
- **The output is a family of reports rather than a live app:** use Quarto parameters; use OJS only when the visualization itself can be JavaScript-driven.
