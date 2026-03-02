# EnChemCP Pipeline Architecture

The EnChemCP pipeline is a 7-phase automated data processing system designed to extract, process, aggregate, and report financial and project data.

## Pipeline Phases

1. **Scraping**: (Currently inactive/placeholders) Intended to pull data from external systems.
2. **Data Processing**: Cleaning and transforming raw data. Implements business logic for code mapping.
3. **Aggregation**: Multi-dimensional summing of financial figures (Revenue, Profit, Cost).
4. **Analyzing**: Comparative analysis (e.g., against thresholds or previous versions).
5. **Report Writing**: Generating Excel reports with specialized sheets (Monthly, Weekly, Version Comparison).
6. **History**: Tracking execution history and persisting processed data.
7. **Notification**: Mock email notification system.

## Key Components

- **Processor (`processor.py`)**: Handles SOLD code logic, PM mappings, and project code grouping.
- **Aggregator (`aggregator.py`)**: A multi-dimensional engine for period-based and group-based totals.
- **Analyzer (`analyzer.py`)**: Calculates differences and identifies threshold violations.
- **History Tracker (`history_tracker.py`)**: Manages the versioning and local storage of results.
- **Report Writer (`report_writer.py`)**: Orchestrates the creation of Excel workbooks.
