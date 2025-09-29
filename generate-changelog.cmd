@echo off
REM ===== CHANGE-LOG GENERATOR FOR WINDOWS =====

echo.
echo Changed files (not yet staged):
git status --short
echo.

echo Diffstat (lines added/deleted):
git diff --stat
echo.

echo Staged changes:
git diff --cached --stat
echo.

set /p showdiff=Show full diff (y/n)? 
if /I "%showdiff%"=="y" (
    git diff
)

REM Step 5: Prepare a CHANGELOG.txt template
echo Generating CHANGELOG.txt template...
(
    echo Change-log:
    echo - Summarize your changes per file below.
    echo - Example:
    echo   - main.py: Fixed retry and fine-tune logic for partial handling.
    echo   - controller_utils.py: Improved docstrings and clarified fine-tune chain.
    echo   - db_models.py: Added comments to job attempt fields (not used in current logic).
    echo.
    echo Files changed:
    git diff --name-only
    echo.
    echo Lines added/deleted:
    git diff --numstat
    echo.
    echo ^# Write your summary below this line:
) > CHANGELOG.txt

echo CHANGELOG.txt generated. Edit this file and use it for your commit message!
pause