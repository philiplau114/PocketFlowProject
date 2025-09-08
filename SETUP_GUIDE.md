# PocketFlow Setup Guide

This guide provides step-by-step instructions for setting up the PocketFlow Trading Optimization Platform.

## 🔧 Prerequisites

### Required Software
1. **Python 3.8+**
   ```bash
   python --version  # Should be 3.8 or higher
   ```

2. **MySQL 8.0+**
   - Install MySQL Server
   - Create a database for PocketFlow
   ```sql
   CREATE DATABASE pocketflow_db;
   CREATE USER 'pocketflow_user'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON pocketflow_db.* TO 'pocketflow_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. **Redis 6.0+**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   
   # Windows (using Chocolatey)
   choco install redis-64
   
   # macOS (using Homebrew)
   brew install redis
   ```

4. **UiPath Studio/Robot**
   - Download and install UiPath Studio
   - Ensure UiRobot.exe is accessible from command line

5. **MetaTrader 4**
   - Install MT4 terminal
   - Configure with your broker settings

## 📦 Installation Steps

### 1. Clone Repository
```bash
git clone https://github.com/philiplau114/PocketFlowProject.git
cd PocketFlowProject
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your specific configurations
# Use your preferred text editor
nano .env  # or vim .env or code .env
```

#### Key Configuration Items:
- **Database URL**: Update MySQL connection details
- **Redis**: Configure Redis host and port
- **File Paths**: Set up input/output directories
- **UiPath**: Configure UiPath CLI and workflow paths
- **Notifications**: Set up email and Telegram credentials

### 5. Database Setup
```bash
# Run database migrations/setup
python -c "from db.db_models import Base; from sqlalchemy import create_engine; engine = create_engine('your_database_url'); Base.metadata.create_all(engine)"
```

### 6. Create Required Directories
```bash
# Create necessary directories
mkdir -p logs
mkdir -p set_file_library/01_user_inputs
mkdir -p set_file_library/99_processed
mkdir -p output_json
```

## 🚀 Running the System

### Method 1: Manual Startup (Development)
Open 4 separate terminal windows and run:

```bash
# Terminal 1 - Controller
python -m controller.main

# Terminal 2 - Supervisor  
python -m supervisor.supervisor

# Terminal 3 - Worker
python -m worker.main

# Terminal 4 - Dashboard (optional)
streamlit run streamlit/controller_dashboard.py
```

### Method 2: Using Batch Files (Windows)
```cmd
# Start all services
start_controller.cmd
start_supervisor.cmd
start_worker.cmd
start_controller_dashboard.cmd
```

## 🔍 Verification

### 1. Check Service Status
- Controller should start monitoring the watch folder
- Worker should connect to Redis and wait for tasks
- Supervisor should begin health monitoring
- Dashboards should be accessible via web browser

### 2. Test Job Submission
1. Place a `.set` file in `set_file_library/01_user_inputs/`
2. Monitor controller logs for job creation
3. Check dashboard for task progress

### 3. Database Verification
```sql
-- Check if tables were created
SHOW TABLES;

-- Check for job records
SELECT * FROM controller_jobs LIMIT 5;

-- Check for task records  
SELECT * FROM controller_tasks LIMIT 5;
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Database Connection Errors
- Verify MySQL is running: `sudo systemctl status mysql`
- Check credentials in `.env` file
- Ensure database exists and user has permissions

#### 2. Redis Connection Errors
- Verify Redis is running: `redis-cli ping`
- Check Redis host/port in configuration
- Ensure Redis is accepting connections

#### 3. UiPath Integration Issues
- Verify UiPath CLI path is correct
- Check UiPath license and robot configuration
- Ensure workflow file exists and is accessible

#### 4. File Permission Issues
- Check read/write permissions on watch folders
- Ensure log directory is writable
- Verify UiPath has access to MT4 directories

### Log Files
Check the following log locations for detailed error information:
- `logs/controller.log`
- `logs/worker.log`
- `logs/supervisor.log`

### Getting Help
1. Check the logs for detailed error messages
2. Verify all prerequisites are correctly installed
3. Ensure environment variables are properly configured
4. Review the [PROJECT_CHECKLIST.md](PROJECT_CHECKLIST.md) for deployment verification steps

## 🔒 Security Considerations

1. **Database Security**
   - Use strong passwords for database users
   - Restrict database access to localhost if possible
   - Enable SSL connections for production

2. **Environment Variables**
   - Never commit `.env` files to version control
   - Use strong passwords for all services
   - Rotate credentials regularly

3. **File System Security**
   - Set appropriate file permissions on directories
   - Ensure log files don't contain sensitive information
   - Secure UiPath workflow files

## 📈 Performance Tuning

1. **Database Optimization**
   - Add indexes for frequently queried columns
   - Configure MySQL for optimal performance
   - Monitor database performance metrics

2. **Redis Configuration**
   - Tune Redis memory settings
   - Configure persistence options
   - Monitor Redis performance

3. **Worker Scaling**
   - Add additional worker nodes for increased throughput
   - Balance workers across multiple machines
   - Monitor resource utilization

---

For more detailed information, refer to the main [README.md](README.md) and [PROJECT_CHECKLIST.md](PROJECT_CHECKLIST.md) files.