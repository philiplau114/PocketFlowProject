# PocketFlow System Architecture

## 🏗️ High-Level Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    PocketFlow Platform                   │
                    └─────────────────────────────────────────────────────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                    ┌─────────▼──────────┐ ┌───▼───┐ ┌──────────▼──────────┐
                    │      Frontend      │ │  API  │ │    Monitoring       │
                    │   (Streamlit)      │ │       │ │   (Dashboards)      │
                    └────────────────────┘ └───────┘ └─────────────────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                    ┌─────────▼──────────┐ ┌───▼───┐ ┌──────────▼──────────┐
                    │    Controller      │ │ Redis │ │     Supervisor      │
                    │  (Job Manager)     │ │Queue  │ │  (Health Monitor)   │
                    └─────────┬──────────┘ └───┬───┘ └──────────┬──────────┘
                              │                │                │
                              └────────────────┼────────────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │       MySQL         │
                                    │     Database        │
                                    └──────────┬──────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              │                │                │
                    ┌─────────▼──────────┐ ┌───▼───┐ ┌──────────▼──────────┐
                    │     Worker 1       │ │  ...  │ │     Worker N        │
                    │  (UiPath Exec)     │ │       │ │   (UiPath Exec)     │
                    └─────────┬──────────┘ └───────┘ └──────────┬──────────┘
                              │                                 │
                              └─────────────────┬───────────────┘
                                                │
                                    ┌──────────▼──────────┐
                                    │      UiPath         │
                                    │    Workflows        │
                                    └──────────┬──────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │    MetaTrader 4     │
                                    │   (Trading Engine)  │
                                    └─────────────────────┘
```

## 🔄 Data Flow Architecture

```
[.set File] ──┐
              │
[Watch Dir] ──┼──► [Controller] ──► [Job Creation] ──► [Task Generation]
              │                                              │
[User Input] ──┘                                             │
                                                              ▼
[Results] ◄──── [UiPath] ◄──── [Worker] ◄──── [Redis Queue] ◄─┘
    │              │              │               │
    ▼              │              │               │
[Database] ◄───────┴──────────────┴───────────────┘
    │
    ▼
[Dashboards] ──► [Notifications]
```

## 🔧 Component Architecture

### Controller Service
```
┌─────────────────────────────────────────────────────────┐
│                    Controller                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │File Watcher │  │Job Manager  │  │Task Manager │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│           │              │              │              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │Set Parser   │  │Priority Calc│  │Queue Manager│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                   Database Layer                        │
└─────────────────────────────────────────────────────────┘
```

### Worker Service
```
┌─────────────────────────────────────────────────────────┐
│                     Worker                              │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │Task Puller  │  │UiPath Exec  │  │Result Sync  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│           │              │              │              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │Heartbeat    │  │Process Mon  │  │Error Handler│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                   UiPath Interface                      │
└─────────────────────────────────────────────────────────┘
```

### Supervisor Service
```
┌─────────────────────────────────────────────────────────┐
│                   Supervisor                            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │Health Check │  │Task Monitor │  │Worker Watch │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│           │              │              │              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │Auto Recovery│  │Alert System │  │Queue Sync   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                 Notification Layer                      │
└─────────────────────────────────────────────────────────┘
```

## 💾 Database Schema Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ controller_jobs │────│controller_tasks │────│controller_      │
│                 │    │                 │    │attempts         │
│ • id (PK)       │    │ • id (PK)       │    │                 │
│ • user_id       │    │ • job_id (FK)   │    │ • id (PK)       │
│ • job_type      │    │ • parent_task   │    │ • task_id (FK)  │
│ • symbol        │    │ • step_number   │    │ • attempt_no    │
│ • timeframe     │    │ • step_name     │    │ • status        │
│ • ea_name       │    │ • status        │    │ • started_at    │
│ • status        │    │ • priority      │    │ • finished_at   │
│ • created_at    │    │ • assigned_wkr  │    │ • error_msg     │
│ • updated_at    │    │ • created_at    │    │ • result_json   │
└─────────────────┘    │ • updated_at    │    └─────────────────┘
                       └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   test_metrics  │
                       │                 │
                       │ • id (PK)       │
                       │ • task_id (FK)  │
                       │ • metric_name   │
                       │ • metric_value  │
                       │ • created_at    │
                       └─────────────────┘
```

## 🔄 State Management

### Task Status Flow
```
[NEW] ──► [QUEUED] ──► [WORKER_IN_PROGRESS] ──┬──► [WORKER_COMPLETED]
                                              │
                                              └──► [WORKER_FAILED]
                                                          │
                                              ┌───────────┴───────────┐
                                              │                       │
                                         [RETRYING]              [FAILED]
                                              │                       │
                                         [QUEUED]                    END
                                              │
                            [FINE_TUNING] ◄───┴───► [COMPLETED_SUCCESS]
                                  │                       │
                            [QUEUED] ──► ... ──► [COMPLETED_PARTIAL]
```

### Job Status Flow
```
[NEW] ──► [QUEUED] ──► [IN_PROGRESS] ──┬──► [COMPLETED_SUCCESS]
                                       │
                                       ├──► [COMPLETED_PARTIAL]
                                       │
                                       └──► [FAILED]
```

## 🚀 Deployment Architecture

### Single Machine Deployment
```
┌─────────────────────────────────────────────────────┐
│                  Single Server                      │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Controller  │  │ Supervisor  │  │  Worker 1   │ │
│  │   Process   │  │   Process   │  │   Process   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   MySQL     │  │    Redis    │  │  Streamlit  │ │
│  │  Database   │  │    Queue    │  │ Dashboard   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐                   │
│  │   UiPath    │  │    MT4      │                   │
│  │  Workflows  │  │  Terminal   │                   │
│  └─────────────┘  └─────────────┘                   │
└─────────────────────────────────────────────────────┘
```

### Distributed Deployment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Control Node   │    │  Database Node  │    │  Worker Node 1  │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│  • Controller   │    │  • MySQL        │    │  • Worker       │
│  • Supervisor   │    │  • Redis        │    │  • UiPath       │
│  • Dashboard    │    │  • Backups      │    │  • MT4          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐    ┌─────────────────┐
                    │  Worker Node 2  │    │  Worker Node N  │
                    ├─────────────────┤    ├─────────────────┤
                    │  • Worker       │    │  • Worker       │
                    │  • UiPath       │    │  • UiPath       │
                    │  • MT4          │    │  • MT4          │
                    └─────────────────┘    └─────────────────┘
```

## 🔒 Security Architecture

### Network Security
```
[Internet] ──► [Firewall] ──► [Load Balancer] ──► [Application Layer]
                   │
                   └──► [DMZ] ──► [Web Dashboard]
                        │
                        └──► [Internal Network] ──► [Database/Redis]
```

### Data Security
- **Encryption**: All sensitive data encrypted at rest and in transit
- **Authentication**: Role-based access control for admin functions
- **Isolation**: Separated network segments for different components
- **Monitoring**: Comprehensive audit logging and monitoring

## 📊 Monitoring Architecture

### Metrics Collection
```
[Application] ──► [Logs] ──► [Log Aggregation] ──► [Dashboard]
      │
      └──► [Metrics] ──► [Time Series DB] ──► [Alerts]
      │
      └──► [Health Checks] ──► [Monitoring] ──► [Notifications]
```

### Alert Flow
```
[System Event] ──► [Alert Rules] ──► [Notification Gateway] ──┬──► [Email]
                                                              │
                                                              ├──► [Telegram]
                                                              │
                                                              └──► [Dashboard]
```

This architecture ensures scalability, reliability, and maintainability of the PocketFlow Trading Optimization Platform.