@echo off
mkdir tests\old 2>nul
move tests\test_document_processing.py tests\old\ 2>nul
move tests\test_performance.py tests\old\ 2>nul
move tests\test_security.py tests\old\ 2>nul
echo Old test files moved to tests\old\