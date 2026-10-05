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

ev$strike_bin <- cut(ev$strikes, breaks = c(0, 1, 3, 6, 10, 15, 60),
                     labels = c("1", "2-3", "4-6", "7-10", "11-15", "16+"))
agg <- aggregate(volume_per_strike ~ strike_bin + is_re, data = ev, FUN = median)
p2 <- ggplot(agg, aes(x = strike_bin, y = volume_per_strike + 1, colour = is_re, group = is_re)) +
  geom_line(linewidth = 0.9) + geom_point(size = 2.5) +
  scale_y_log10(labels = scales::label_comma()) +
  scale_colour_manual(values = c("Other economics" = ZISSOU[1], "Real estate" = ZISSOU[5]), name = NULL) +
  labs(x = "Strikes listed per event", y = "Median contracts traded per strike (log scale)") +
  theme_ree() + theme(legend.position = "bottom")
save_fig("figures/volume_per_strike_by_strikes.png", p2, width = 8, height = 5)
