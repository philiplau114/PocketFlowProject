@echo off
REM start_batch_orchestrator.cmd
REM Change to portfolio_analysis directory and run the batch orchestrator

cd /d "%~dp0portfolio_analysis"
python batch_orchestrator.py
