# Futures Trading Log Application

## Project Overview
This Flask-based application is designed to help futures traders track, analyze, and manage their trading performance. By importing execution reports from Ninja Trader, the application provides comprehensive insights into trading activities, performance metrics, and historical trade data.

## Key Features
- Import and process Ninja Trader Execution Reports
- Web-based trade log management
- Detailed trade statistics and analysis
- User-friendly interface for tracking trading performance

## Prerequisites
- Python 3.8+
- Ninja Trader (for generating execution reports)
- Git (optional, for cloning the repository)

## Setup and Installation

### 1. Clone the Repository
```bash
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Ninja Trader Execution Report Processing Workflow

### Step 1: Export Execution Report from Ninja Trader
1. Open Ninja Trader
2. Navigate to "Statements" or "Reports" section
3. Select "Execution Report"
4. Choose your desired date range
5. Export the report as a CSV file

### Step 2: Prepare Execution Report
- Save the exported CSV file in the project's root directory
- Ensure the file name is clear and descriptive
- Recommended: Use format like `ExecutionReport_YYYYMMDD.csv`

### Step 3: Run Execution Report Processor
```bash
# Navigate to project directory
cd C:\path\to\FuturesTradingLog

# Activate virtual environment
venv\Scripts\activate

# Run the Execution Processor
python ExecutionProcessor.py
```

### Step 4: Import Trade Log to Application
1. Start the Flask Application
```bash
flask run
```

2. Open Web Browser
- Navigate to: `http://localhost:5000`
- Go to the "Import" section
- Select the generated `TradeLog.csv`
- Click "Import"

## Troubleshooting

### Common Issues
- Ensure CSV files are not open in other applications
- Check Python and pip versions
- Verify virtual environment is activated
- Confirm Ninja Trader export format matches expected input

### Compatibility
- Supports Ninja Trader 8.x Execution Reports
- CSV must contain standard trade execution columns

## Contributing
- Fork the repository
- Create a feature branch
- Submit pull requests

## License
[Specify your license, e.g., MIT]

## Contact
[Your contact information or support email]

## Disclaimer
This application is for personal trading analysis. Always verify your trade data and consult with financial professionals.
