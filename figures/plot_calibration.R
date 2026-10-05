# Calibration of Kalshi prices one day before close: realised frequency against
# forecast, by forecast bin. Reads data/derived/calibration_bins.csv.
source("figures/theme_ree.R")

cal <- read.csv("data/derived/calibration_bins.csv")
cal <- cal[cal$lead == 1, ]
cal$group <- ifelse(cal$re == 1, "Real estate", "Other economics")

p <- ggplot(cal, aes(x = forecast, y = realised, colour = group)) +
  geom_abline(slope = 1, intercept = 0, colour = "grey60", linetype = "dashed") +
  geom_line(linewidth = 0.8) +
  geom_point(aes(size = n)) +
  scale_colour_manual(values = c("Other economics" = ZISSOU[1], "Real estate" = ZISSOU[5]), name = NULL) +
  scale_size_continuous(range = c(1.5, 6), name = "Markets") +
  coord_equal(xlim = c(0, 1), ylim = c(0, 1)) +
  labs(x = "Price one day before close", y = "Share resolving yes") +
  theme_ree() + theme(legend.position = "right")
save_fig("figures/calibration_one_day.png", p, width = 7.5, height = 5.5)
