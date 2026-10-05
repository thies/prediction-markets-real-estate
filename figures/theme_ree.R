# Shared theme, palette, and helpers for all REE figures.
# Source this at the top of every plot script:
#   source(file.path(dirname(sys.frame(1)$ofile), "theme_ree.R"))

library(ggplot2)

# ── Zissou1 palette ───────────────────────────────────────────────────────────
ZISSOU <- c("#3B9AB2", "#78B7C5", "#EBCC2A", "#E1AF00", "#F21A00")

GREY_BG   <- "#CCCCCC"   # corpus background dots (legacy)
RED_IDEAS <- "#F21A00"   # generated ideas / highlight

# ── Unified corpus / highlight palette ───────────────────────────────────────
# Shared across Figures 2b, 3, 4 for consistent cross-plot reading.
COL_RE   <- "#3B9AB2"   # blue   — RE corpus (REE, JREFE, JRER)
COL_JUE  <- "#F5C518"   # yellow — Urban Economics (JUE)
COL_ECON <- "#7B2D8B"   # purple — Econ./Finance (AER, JF, RFS)
COL_RED  <- "#F21A00"   # red    — highlights (AI papers, generated ideas)

# ── Base theme ────────────────────────────────────────────────────────────────
theme_ree <- function(base_size = 13, base_family = "sans") {
  theme_minimal(base_size = base_size, base_family = base_family) +
  theme(
    # Legend: no box, no background
    legend.background    = element_blank(),
    legend.key           = element_blank(),
    legend.box.background = element_blank(),
    legend.text          = element_text(size = base_size),
    legend.title         = element_text(size = base_size),
    # Axes
    axis.text            = element_text(size = base_size - 1),
    axis.title           = element_text(size = base_size),
    # Strip (facets)
    strip.text           = element_text(size = base_size, face = "bold"),
    strip.background     = element_blank(),
    # Grid
    panel.grid.minor     = element_blank(),
    # Background
    plot.background      = element_rect(fill = "white", colour = NA),
    panel.background     = element_rect(fill = "white", colour = NA)
  )
}

# ── Convenience: save at standard resolution ──────────────────────────────────
save_fig <- function(filename, plot = last_plot(),
                     width = 8, height = 6, dpi = 200) {
  ggsave(filename, plot = plot, width = width, height = height,
         dpi = dpi, bg = "white")
  message("Saved ", filename)
}
