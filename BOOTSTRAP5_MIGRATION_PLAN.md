# Bootstrap 5 Migration & Redesign Plan

## Overview
Migrating APS 2026 from Bootstrap 3.3.7 to Bootstrap 5.3.x with a modern redesign approach.

## Migration Strategy

### Phase 1: Core Infrastructure (Week 1)
1. **Update base.html**
   - Replace Bootstrap 3 CDN with Bootstrap 5
   - Remove jQuery dependency (Bootstrap 5 doesn't require it)
   - Update meta viewport tag for better mobile support
   - Implement new Bootstrap 5 utilities

2. **Grid System Migration**
   - `col-md-*` → `col-md-*` (no change in class name)
   - `col-xs-*` → `col-*` (xs is now default)
   - Add new spacing utilities (g-*, gap-*)
   - Replace `panel` with `card` component

3. **Navigation Updates**
   - Migrate navbar to Bootstrap 5 structure
   - Update dropdown attributes: `data-toggle` → `data-bs-toggle`
   - Implement new navbar-expand-* breakpoints
   - Remove jQuery-dependent dropdown code

### Phase 2: Component Migration (Week 1-2)
1. **Forms**
   - Update form controls (minimal changes needed)
   - Add new form validation styles
   - Implement floating labels where appropriate

2. **Utilities**
   - `img-responsive` → `img-fluid`
   - `text-left/right` → `text-start/end`
   - `pull-left/right` → `float-start/end`
   - Update visibility classes to new display utilities

3. **Custom Components**
   - Tabs: Update data attributes and JavaScript
   - Remove panel styling, implement cards
   - Update responsive utilities

### Phase 3: Design Modernization (Week 2-3)
1. **Typography & Spacing**
   - Implement Bootstrap 5's improved spacing scale
   - Use CSS custom properties for theming
   - Add modern font stack

2. **Layout Innovations**
   - Replace rigid grid with CSS Grid for complex layouts
   - Implement asymmetric layouts for visual interest
   - Add scroll-triggered animations

3. **Component Redesign**
   - Modern card-based layouts for news/research
   - Masonry-style grid for proceedings
   - Interactive filtering without page reload
   - Subtle micro-interactions

## Technical Changes

### Before (Bootstrap 3)
```html
<div class="col-xs-12 col-md-6">
<img class="img-responsive">
<div class="panel">
<div data-toggle="dropdown">
```

### After (Bootstrap 5)
```html
<div class="col-12 col-md-6">
<img class="img-fluid">
<div class="card">
<div data-bs-toggle="dropdown">
```

## Design Direction

### Moving Away From
- Rigid newspaper columns
- Dense text layouts
- Traditional navigation patterns
- Static content presentation

### Moving Towards
- Dynamic card-based layouts
- Generous whitespace
- Asymmetric grids
- Smooth animations and transitions
- Modern academic/research aesthetic

## Priority Templates
1. base.html (foundation)
2. home_page.html (first impression)
3. news_research_index_page.html (showcase new design)
4. people_index_page.html (complex grid usage)
5. navbar.html (critical navigation)

## Risk Mitigation
- Create component library page for testing
- Maintain backward compatibility during transition
- Test on multiple devices/browsers
- Keep rollback branch available

## Success Metrics
- Page load speed improvement (no jQuery)
- Mobile usability scores
- Consistent responsive behavior
- Modern visual appeal