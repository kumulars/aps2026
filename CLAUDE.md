# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ACTIVE PROJECT: Bootstrap 5 Migration & Redesign
**Branch:** `bootstrap5-redesign`  
**Status:** Check MIGRATION_STATUS.md for current progress  
**Started:** 2025-01-19

### Migration Resources
- `BOOTSTRAP5_MIGRATION_PLAN.md` - Full migration strategy
- `MIGRATION_STATUS.md` - Current progress and next steps
- `DESIGN_DECISIONS.md` - Design choices and rationale (if exists)

### Session Continuity
When starting a new session on this branch:
1. Read MIGRATION_STATUS.md first
2. Check git status for uncommitted changes
3. Review the last few commits for context
4. Continue from "Next Steps" in status file

## Project Overview

This is a Django 5.1.9 + Wagtail 6.4.1 CMS project for the American Peptide Society (APS) 2026 website. The project combines Wagtail's page-based CMS with custom Django views for specialized content like news articles, obituaries, and researcher profiles.

## Development Setup

### Virtual Environment
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Database Operations
```bash
python manage.py migrate
python manage.py collectstatic
python manage.py runserver
```

### Settings
- Development: `aps2026_site.settings.dev` (default)
- Production: `aps2026_site.settings.production`

## Key Architecture

### Apps Structure
- `aps2026_site/` - Django project settings and base templates
- `home/` - Main Wagtail app containing all page models and custom views
- `search/` - Search functionality

### Page Models (home/models.py)
- `HomePage` - Site homepage with slider and highlight panels
- `PeopleIndexPage` - Directory of researchers and staff
- `NewsResearchIndexPage` - News and research articles listing
- `ProceedingsIndexPage` - Conference proceedings archive
- `NewsPage` - Individual news article pages

### Content Models
- `NewsResearchItem` - News articles with categories and research areas
- `Person` - Researcher profiles with affiliations and specialties
- `Obituary` - Memorial content with custom slug routing
- `Committee` - Committee structure and memberships
- `HighlightPanel` - Homepage feature content

### Custom Views (home/views.py)
The project uses a hybrid approach:
- Wagtail pages for most content (`serve` methods)
- Custom Django views for detail pages: `news_detail`, `obituary_detail`, `highlight_detail`
- Custom URL patterns in `home/urls.py` for non-Wagtail routes

## Data Import System

### Custom Management Commands
```bash
python manage.py import_peptidelinks  # Import researchers from peptidelinks.net
python manage.py update_researcher_locations  # Update location data
python manage.py debug_parser  # Debug data parsing issues
```

### Import Files
- CSV files stored in `import_files/` directory
- Models include import tracking fields (`imported_from`, `import_date`)

## URL Structure

### Admin Access
- Wagtail Admin: `/admin/`
- Django Admin: `/django-admin/`

### Custom Routes
- News detail: `/news/<slug>/`
- Obituary detail: `/obituaries/<slug>/`
- Highlight detail: `/highlight/<slug>/`
- Search: `/search/`

## Templates Organization

### Base Templates
- `aps2026_site/templates/base.html` - Main layout
- `home/templates/home/` - Page-specific templates
- `home/templates/components/` - Reusable components

### Key Template Features
- Responsive design with Bootstrap
- Image handling via Wagtail image API
- Category filtering for news/research items
- Slider functionality for homepage

## Static Files & Media

### Static Files
- `aps2026_site/static/` - Project-level assets
- `home/static/` - App-specific assets
- CSS customizations in `custom.css`

### Media Handling
- User uploads stored in `media/` directory
- Wagtail image renditions managed automatically

## Development Notes

### No Testing Framework
Currently no test files exist. When adding tests, consider:
- Django's TestCase for model testing
- Wagtail's WagtailPageTests for page functionality
- Test custom views and import commands

### No Code Quality Tools
Project lacks linting/formatting configuration. Consider adding:
- Black for code formatting
- isort for import sorting
- flake8 for linting

## FUTURE DEVELOPMENT PRIORITIES (ON HOLD)

### SEO Optimization Module
**Status:** Planned - Comprehensive SEO strategy designed
- Enhanced meta tag management for all page models
- Structured data (Schema.org) implementation for scientific content
- Advanced keyword optimization for peptide research terms
- Google Search Console integration
- Content optimization tools and SEO audit commands
- Authority building through scientific community link building
- Expected results: 100% increase in organic traffic within 6 months

### Voting/Elections Module
**Status:** Planned - Democratic governance platform
- Secure electronic voting system for APS elections
- Member authentication and eligibility verification
- Multiple election types: Board elections, policy votes, award selections
- Real-time vote counting and result visualization
- Complete audit trail and transparency features
- Mobile-optimized voting experience
- Blockchain-inspired security for election integrity

**Note:** Both modules have detailed specifications available. Priority should be given to SEO implementation first for member growth, followed by voting system for governance needs.

### Database Considerations
- Development uses SQLite
- Production settings support PostgreSQL/MySQL
- Migrations tracked in `home/migrations/`

## Deployment

### Docker
- `Dockerfile` present with Python 3.12 and Gunicorn
- Production settings in `aps2026_site/settings/production.py`
- Static files served via `collectstatic`

### Key Production Settings
- `DEBUG = False`
- Separate database configuration
- Static/media file handling
- Security settings (CSRF, HTTPS)