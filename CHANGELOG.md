# Changelog

All notable changes to the PolyOne bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Configuration validation on startup
- Comprehensive error messages with actionable guidance
- Type hints throughout codebase for better maintainability
- Enhanced docstrings for all major functions
- Quick start guide with troubleshooting section
- Complete commands reference documentation
- Changelog for tracking changes
- Transaction count tracking for accurate daily metrics calculation
- Biggest transaction tracking for daily summary reports
- `transaction_count_history` and `biggest_transaction_history` state fields

### Changed
- Admin role is now configurable via environment variable or bot command
- All print statements replaced with proper logging
- Improved error messages for better debugging
- Enhanced configuration validation with warnings and errors
- Daily summary metrics now use all transactions (via transaction count) instead of only top transactions
- Average Transaction Size (24h) now calculated from total daily volume / daily transaction count
- Biggest Transfer Today now tracked from all transactions in past 24h, not just top leaderboard entries

### Fixed
- Code review and cleanup after crash recovery
- Improved error handling in various functions
- Better type safety with proper type hints
- Daily metrics (Biggest Transfer Today and Average Transaction Size) now accurately reflect all transactions, not just top 10

## [Recent Updates]

### Code Quality Improvements
- Added type hints to 15+ functions
- Added/improved docstrings for 10+ functions
- Improved error messages in 5+ locations
- Standardized logging throughout codebase

### Documentation Enhancements
- Expanded troubleshooting section with detailed solutions
- Created comprehensive commands reference
- Added examples for common use cases
- Improved quick start guide

### Configuration
- Admin role configurable via `ADMIN_ROLE_NAME` env var
- Admin role can be changed via `/bot_setup` command
- Configuration validation on startup prevents common issues

### Logging
- All print statements replaced with logger calls
- Structured logging with file rotation
- Separate error log file for easier debugging
- Log levels configurable via `LOG_LEVEL` env var

## [Previous Features]

### Core Features
- XP system with tiered daily caps
- Tweet submission and automatic grading
- Metrics quiz with AI-generated questions
- Prediction game (volume and top 10)
- Daily leaderboard and summaries
- Volume channel counter
- Top 10 transaction alerts
- Milestone celebrations

### Admin Features
- XP management (give, remove, bulk grants)
- Component toggling
- Channel configuration
- Historical data migration
- Ungraded tweet processing

### Integrations
- Google Sheets for data storage
- Twitter/X API for tweet fetching
- OpenAI API for tweet grading and quiz generation
- Polymer Analytics API for metrics
- DeFiLlama API for chain metadata

---

## Version History

### v1.0.0 (Initial Release)
- Basic XP tracking
- Tweet submission system
- Google Sheets integration
- Discord slash commands
- Admin commands

### v1.1.0
- Added prediction game
- Metrics quiz feature
- Daily caps system
- Volume channel counter

### v1.2.0
- Component toggling
- Enhanced error handling
- Improved logging
- Configuration validation

### v1.3.0 (Current)
- Code quality improvements
- Enhanced documentation
- Configurable admin role
- Standardized logging

---

## Migration Notes

### Upgrading to v1.3.0

**Breaking Changes:**
- None

**New Requirements:**
- Python 3.8+ (no change)
- All existing environment variables still supported

**Configuration Changes:**
- New optional env var: `ADMIN_ROLE_NAME` (defaults to "manager perms")
- Admin role can now be changed via `/bot_setup` command

**Action Required:**
- Review and update admin role name if needed
- Check logs for any new warnings during startup
- Verify configuration validation passes

---

## Future Plans

### Planned Features
- [ ] Web dashboard for analytics
- [ ] Additional quiz types
- [ ] Enhanced prediction game features
- [ ] API endpoints for external integrations
- [ ] Automated testing suite
- [ ] Performance optimizations

### Known Issues
- None currently documented

---

## Contributing

When adding new features or fixing bugs, please:
1. Update this changelog
2. Add appropriate type hints
3. Include docstrings
4. Update relevant documentation
5. Test thoroughly

---

## Support

For issues or questions:
- Check `POLYONE_BOT_DOCUMENTATION.md` for setup guide
- Review `COMMANDS_REFERENCE.md` for command usage
- Check logs in `logs/` directory
- Use `/bot_component_status` to verify bot health





