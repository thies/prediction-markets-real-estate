# Share of house-level price variance removed by an index hedge, by holding
# period and instrument. Reads data/derived/tab_hedging_warranty.csv.
source("figures/theme_ree.R")

h <- read.csv("data/derived/tab_hedging_warranty.csv")
h <- h[h$holding_years != "All", ]
h$holding_years <- factor(h$holding_years, levels = h$holding_years)
long <- rbind(
  data.frame(holding = h$holding_years, r2 = h$r2_linear, hedge = "Linear (future)"),
  data.frame(holding = h$holding_years, r2 = h$r2_ladder, hedge = "Ladder of seven binaries"),
  data.frame(holding = h$holding_years, r2 = h$r2_binary, hedge = "One binary (index up)")
)
long$hedge <- factor(long$hedge, levels = c("Linear (future)", "Ladder of seven binaries", "One binary (index up)"))

p <- ggplot(long, aes(x = holding, y = r2, colour = hedge, group = hedge)) +
  geom_line(linewidth = 0.9) + geom_point(size = 2.5) +
  scale_colour_manual(values = c(ZISSOU[1], ZISSOU[4], ZISSOU[5]), name = NULL) +
  scale_y_continuous(labels = scales::label_percent(), limits = c(0, 0.6)) +
  labs(x = "Holding period (years)", y = "Share of house-level variance removed") +
  theme_ree() + theme(legend.position = "bottom")
save_fig("figures/hedging_by_holding_period.png", p, width = 8, height = 5)
