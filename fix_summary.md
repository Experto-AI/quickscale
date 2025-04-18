QuickScale Log Analyzer Improvements Summary

## Issues Identified

- False positives in migration logs (migrations with 'error' in name)
- Database shutdown logs incorrectly flagged as errors
- Django development server warnings treated as issues
- Static file 404 errors during initial startup flagged as warnings

## Changes Made

1. Enhanced _is_false_positive method to detect more expected messages
2. Added migration-specific analysis to identify real errors vs. false positives
3. Improved regular expressions for pattern matching to reduce false matches
4. Added better context in CLI output to explain why certain messages are normal
5. Added more detailed logging about false positive filtering

## Testing Recommendations

- Run 'quickscale build' command on new projects to verify improvements
- Verify that actual errors are still being properly captured and displayed
- Check log output formatting and context lines
