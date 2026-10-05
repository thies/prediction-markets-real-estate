# Event-level traded volume by contract group, and volume per strike against
# the number of strikes. Reads data/derived/kalshi_events.csv.
source("figures/theme_ree.R")

ev <- read.csv("data/derived/kalshi_events.csv")
ev$group <- factor(ev$re_group,
  levels = c("other economics", "activity", "mortgage rate", "credit and CRE", "price", "rent"),
  labels = c("Other economics", "Housing activity", "Mortgage rate", "Credit and CRE",
             "House prices", "Rents"))
ev$is_re <- ifelse(ev$real_estate == "True", "Real estate", "Other economics")

p1 <- ggplot(ev, aes(x = group, y = volume + 1, fill = is_re)) +
  geom_boxplot(outlier.size = 0.4, outlier.alpha = 0.3, width = 0.6) +
  scale_y_log10(labels = scales::label_comma()) +
  scale_fill_manual(values = c("Other economics" = ZISSOU[2], "Real estate" = ZISSOU[4]), name = NULL) +
  labs(x = NULL, y = "Contracts traded per event (log scale)") +
  theme_ree() +
  theme(legend.position = "none", axis.text.x = element_text(angle = 25, hjust = 1))
save_fig("figures/event_volume_by_group.png", p1, width = 8, height = 5)

# One point per event: contracts traded per strike against the number of strikes listed,
# with a fitted line per group. Real estate events are drawn on top of the others.
set.seed(1)
ev$x <- ev$strikes * exp(runif(nrow(ev), -0.06, 0.06))   # small horizontal jitter; strikes are integers
other <- ev[ev$is_re == "Other economics", ]
re <- ev[ev$is_re == "Real estate", ]
p2 <- ggplot(mapping = aes(x = x, y = volume_per_strike + 1)) +
  geom_point(data = other, aes(colour = "Other economics"), alpha = 0.12, size = 0.9) +
  geom_point(data = re, aes(colour = "Real estate"), alpha = 0.75, size = 1.6) +
  geom_smooth(data = other, aes(x = strikes, colour = "Other economics"), method = "lm", formula = y ~ x,
              se = FALSE, linewidth = 1.1) +
  geom_smooth(data = re, aes(x = strikes, colour = "Real estate"), method = "lm", formula = y ~ x,
              se = FALSE, linewidth = 1.1) +
  scale_x_log10(breaks = c(1, 2, 3, 5, 10, 20, 50)) +
  scale_y_log10(labels = scales::label_comma()) +
  scale_colour_manual(values = c("Other economics" = ZISSOU[1], "Real estate" = ZISSOU[5]), name = NULL) +
  guides(colour = guide_legend(override.aes = list(alpha = 1, size = 2.5, linewidth = 0))) +
  labs(x = "Strikes listed in the event (log scale)", y = "Contracts traded per strike (log scale)") +
  theme_ree() + theme(legend.position = "bottom")
save_fig("figures/volume_per_strike_by_strikes.png", p2, width = 8, height = 5)
