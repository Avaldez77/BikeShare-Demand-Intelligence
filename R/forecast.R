required_columns <- c(
  "service_date", "season", "hour", "weekday", "workingday", "count"
)

safe_metrics <- function(actual, prediction) {
  errors <- actual - prediction
  denominator <- sum(abs(actual))
  if (!is.finite(denominator) || denominator <= 0) {
    stop("WAPE requires a positive finite sum of absolute actual demand")
  }
  c(
    mae = mean(abs(errors)),
    rmse = sqrt(mean(errors^2)),
    wape = sum(abs(errors)) / denominator
  )
}

run_forecast <- function(input_path, output_dir, holdout_days = 28) {
  if (!file.exists(input_path)) {
    stop(sprintf("Validated hourly input does not exist: %s", input_path))
  }
  if (length(holdout_days) != 1 || is.na(holdout_days) ||
      !is.finite(holdout_days) || holdout_days < 7 ||
      holdout_days != as.integer(holdout_days)) {
    stop("holdout_days must be a finite integer of at least 7")
  }
  data <- read.csv(input_path, stringsAsFactors = FALSE)
  missing <- setdiff(required_columns, names(data))
  if (length(missing) > 0) {
    stop(sprintf("Hourly input is missing columns: %s", paste(missing, collapse = ", ")))
  }
  data$service_date <- as.Date(data$service_date)
  numeric_columns <- c("season", "hour", "weekday", "workingday", "count")
  if (anyNA(data[, c("service_date", numeric_columns)]) ||
      any(!is.finite(as.matrix(data[, numeric_columns]))) ||
      any(data$count < 0) || any(data$hour < 0 | data$hour > 23)) {
    stop("Hourly input contains invalid dates, missing features, or invalid demand values")
  }
  if (anyDuplicated(data[c("service_date", "hour")])) {
    stop("Hourly input has duplicate date/hour observations")
  }
  data <- data[order(data$service_date, data$hour), ]
  split_date <- max(data$service_date) - (holdout_days - 1)
  training <- data[data$service_date < split_date, ]
  testing <- data[data$service_date >= split_date, ]
  if (nrow(training) < 1000 || nrow(testing) == 0) {
    stop("Insufficient rows for a meaningful chronological holdout")
  }

  model <- stats::lm(
    log1p(count) ~ factor(hour) + factor(weekday) + factor(season) + workingday,
    data = training
  )
  model_prediction <- pmax(0, expm1(stats::predict(model, newdata = testing)))

  training$hour_of_week <- training$weekday * 24 + training$hour
  testing$hour_of_week <- testing$weekday * 24 + testing$hour
  baseline <- aggregate(
    count ~ hour_of_week,
    data = training,
    FUN = mean
  )
  baseline_match <- match(testing$hour_of_week, baseline$hour_of_week)
  baseline_prediction <- baseline$count[baseline_match]
  if (anyNA(baseline_prediction)) {
    stop("Unable to form hour-of-week baseline for every holdout record")
  }

  model_metrics <- safe_metrics(testing$count, model_prediction)
  baseline_metrics <- safe_metrics(testing$count, baseline_prediction)
  predictions <- data.frame(
    service_date = testing$service_date,
    hour = testing$hour,
    weekday = testing$weekday,
    actual = testing$count,
    model_prediction = model_prediction,
    baseline_prediction = baseline_prediction
  )
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  utils::write.csv(
    predictions,
    file.path(output_dir, "forecast_predictions.csv"),
    row.names = FALSE,
    na = ""
  )
  scores <- data.frame(
    method = c("calendar_lm", "hour_of_week_baseline"),
    mae = c(model_metrics[["mae"]], baseline_metrics[["mae"]]),
    rmse = c(model_metrics[["rmse"]], baseline_metrics[["rmse"]]),
    wape = c(model_metrics[["wape"]], baseline_metrics[["wape"]]),
    train_rows = nrow(training),
    test_rows = nrow(testing),
    train_end = as.character(max(training$service_date)),
    holdout_start = as.character(min(testing$service_date)),
    holdout_end = as.character(max(testing$service_date))
  )
  utils::write.csv(
    scores,
    file.path(output_dir, "forecast_scores.csv"),
    row.names = FALSE
  )
  cat("Chronological holdout forecast metrics\n")
  print(scores, row.names = FALSE, digits = 3)
  invisible(scores)
}

arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) < 2 || length(arguments) > 3) {
  stop("Usage: Rscript R/forecast.R <hourly_demand.csv> <output_dir> [holdout_days]")
}
holdout_days <- if (length(arguments) == 3) as.integer(arguments[[3]]) else 28L
run_forecast(arguments[[1]], arguments[[2]], holdout_days)
