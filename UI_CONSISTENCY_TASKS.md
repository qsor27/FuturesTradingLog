# UI Consistency Implementation Tasks

## Phase 1: Template Structure Standardization (HIGH PRIORITY)

### Task 1.1: Convert main.html to extend base.html
**Estimated Time:** 4 hours  
**Priority:** Critical  
**Files:** `templates/main.html`

**Steps:**
1. Remove standalone HTML structure (DOCTYPE, html, head tags)
2. Add `{% extends "base.html" %}` at the top
3. Move page title to `{% block title %}`
4. Move custom styles to `{% block extra_head %}`
5. Wrap page content in `{% block content %}`
6. Remove duplicate navigation elements
7. Test navigation functionality
8. Verify all import sections and filters work correctly

**Acceptance Criteria:**
- Page extends base.html correctly
- Navigation bar appears and functions
- All existing functionality preserved
- No styling regressions

### Task 1.2: Convert positions/dashboard.html to extend base.html
**Estimated Time:** 4 hours  
**Priority:** Critical  
**Files:** `templates/positions/dashboard.html`

**Steps:**
1. Remove standalone HTML structure
2. Add base template extension
3. Move custom position-specific styles to external CSS or component
4. Integrate with navigation system
5. Test all position dashboard functionality
6. Verify statistics grid and position tables

**Acceptance Criteria:**
- Consistent navigation with other pages
- All position data displays correctly
- P&L calculations and status indicators work
- Statistics cards maintain functionality

### Task 1.3: Create reusable component templates
**Estimated Time:** 6 hours  
**Priority:** High  
**Files:** 
- `templates/components/card.html`
- `templates/components/form_field.html` 
- `templates/components/table.html`
- `templates/components/button.html`

**Card Component (`templates/components/card.html`):**
```html
<div class="card{% if class %} {{ class }}{% endif %}">
  {% if title %}
  <div class="card-header">
    <h3>{{ title }}</h3>
    {% if subtitle %}<p class="card-subtitle">{{ subtitle }}</p>{% endif %}
  </div>
  {% endif %}
  <div class="card-body">
    {{ content }}
  </div>
</div>
```

**Form Field Component (`templates/components/form_field.html`):**
```html
<div class="form-field{% if required %} required{% endif %}{% if error %} error{% endif %}">
  <label for="{{ id }}">{{ label }}</label>
  <input type="{{ type|default('text') }}" 
         id="{{ id }}" 
         name="{{ name|default(id) }}" 
         value="{{ value }}" 
         {% if placeholder %}placeholder="{{ placeholder }}"{% endif %}
         {% if required %}required{% endif %}>
  {% if error %}<span class="error-message">{{ error }}</span>{% endif %}
</div>
```

**Acceptance Criteria:**
- Components render correctly in isolation
- Props/parameters work as expected
- Components integrate with existing pages
- Documentation for component usage

## Phase 2: CSS Architecture Cleanup (HIGH PRIORITY)

### Task 2.1: Expand and refactor styles.css
**Estimated Time:** 8 hours  
**Priority:** Critical  
**Files:** `static/css/styles.css`

**Steps:**
1. Add complete CSS variable system from spec
2. Create component-specific CSS classes
3. Add utility classes for common patterns
4. Implement responsive breakpoints
5. Add form styling system
6. Create button variant classes
7. Standardize table styling
8. Add loading state styles

**Key CSS Additions:**
```css
/* Component Classes */
.card { /* Standard card styling */ }
.form-field { /* Form field container */ }
.btn-primary, .btn-secondary, .btn-tertiary { /* Button variants */ }
.table-standard { /* Consistent table styling */ }
.loading { /* Loading indicator */ }

/* Utility Classes */
.text-center, .text-left, .text-right { /* Text alignment */ }
.mb-1, .mb-2, .mb-3, .mb-4 { /* Margin bottom utilities */ }
.p-1, .p-2, .p-3, .p-4 { /* Padding utilities */ }
```

**Acceptance Criteria:**
- All CSS variables defined and used consistently
- Component classes available for all major UI elements
- Utility classes for common spacing/alignment needs
- No duplicate style definitions
- Responsive design considerations included

### Task 2.2: Remove inline styles from all templates
**Estimated Time:** 6 hours  
**Priority:** High  
**Files:** All template files with inline styles

**Steps:**
1. Audit all templates for `<style>` blocks
2. Extract styles to external CSS or component-specific files
3. Replace inline styles with CSS classes
4. Update base.html to remove embedded styles
5. Test all pages for visual consistency

**Templates to Update:**
- `templates/base.html` (remove large style block)
- `templates/main.html` (convert inline styles)
- `templates/positions/dashboard.html` (extract position styles)
- `templates/chart.html` (convert to dark theme)
- Any other templates with inline styles

**Acceptance Criteria:**
- Zero inline `<style>` blocks in templates
- All styling via external CSS classes
- Visual appearance unchanged
- Improved maintainability

### Task 2.3: Standardize chart.html dark theme
**Estimated Time:** 3 hours  
**Priority:** Medium  
**Files:** `templates/chart.html`

**Steps:**
1. Replace light theme colors with dark theme variables
2. Update chart controls styling
3. Ensure chart background matches application theme
4. Test chart functionality with new styling
5. Verify chart legend and controls visibility

**Style Updates:**
- Background: #fff → var(--bg-primary)
- Controls bg: #f8f9fa → var(--bg-secondary)  
- Borders: #ddd → var(--border-primary)
- Text: default → var(--text-primary)

**Acceptance Criteria:**
- Chart page uses consistent dark theme
- All chart controls remain functional
- Chart data visualization not impacted
- Consistent with other pages

### Task 2.4: Fix upload.html Bootstrap/Tailwind conflicts
**Estimated Time:** 2 hours  
**Priority:** Medium  
**Files:** `templates/upload.html`

**Steps:**
1. Remove Bootstrap/Tailwind classes
2. Replace with custom CSS classes using design system
3. Ensure upload functionality remains intact
4. Test file upload and auto-import features
5. Verify responsive behavior

**Acceptance Criteria:**
- No Bootstrap/Tailwind class conflicts
- Upload form styling consistent with other pages
- All upload functionality preserved
- Mobile responsive design

## Phase 3: Component Implementation (MEDIUM PRIORITY)

### Task 3.1: Enhance navigation system
**Estimated Time:** 4 hours  
**Priority:** Medium  
**Files:** `templates/base.html`

**Steps:**
1. Add active page detection logic
2. Implement active state styling
3. Add breadcrumb support (optional)
4. Ensure navigation is responsive
5. Add accessibility attributes

**Implementation:**
```python
# In route handlers, pass current page info
@app.route('/positions')
def positions():
    return render_template('positions/dashboard.html', 
                         current_page='positions')
```

```html
<!-- In base.html navigation -->
<a href="{{ url_for('positions.positions_dashboard') }}" 
   class="nav-link{% if current_page == 'positions' %} active{% endif %}">
   Positions
</a>
```

**Acceptance Criteria:**
- Current page highlighted in navigation
- Navigation works on all screen sizes
- Accessibility compliance (ARIA labels)
- Breadcrumbs implemented where beneficial

### Task 3.2: Standardize form styling across application
**Estimated Time:** 5 hours  
**Priority:** Medium  
**Files:** All templates with forms

**Steps:**
1. Identify all forms in the application
2. Apply consistent form field styling
3. Implement error state styling
4. Add validation feedback styling
5. Ensure accessibility compliance
6. Test form submissions

**Forms to Update:**
- Upload forms in `upload.html`
- Filter forms in trade pages
- Settings forms in `settings.html`
- Any other forms throughout the application

**Acceptance Criteria:**
- All forms use consistent styling
- Error states clearly visible
- Validation messages properly styled
- Form accessibility improved

### Task 3.3: Implement consistent table styling
**Estimated Time:** 4 hours  
**Priority:** Medium  
**Files:** All templates with tables

**Steps:**
1. Create standard table CSS class
2. Apply to all data tables
3. Implement hover states
4. Add responsive table behavior
5. Ensure sorting/filtering UI consistency

**Tables to Update:**
- Trade tables in main pages
- Position tables in dashboard
- Settings tables
- Statistics tables

**Acceptance Criteria:**
- All tables use consistent styling
- Responsive behavior on small screens
- Hover states and interactions work
- Sorting/filtering UI consistent

## Phase 4: Advanced UI Features (LOW PRIORITY)

### Task 4.1: Implement loading states
**Estimated Time:** 3 hours  
**Priority:** Low  
**Files:** Various templates and JavaScript files

**Steps:**
1. Create loading indicator CSS
2. Add skeleton screens for data loading
3. Implement in key areas (charts, tables, forms)
4. Test loading state behavior

**Acceptance Criteria:**
- Professional loading indicators
- Skeleton screens for data-heavy pages
- Smooth transitions between states

### Task 4.2: Mobile responsive improvements
**Estimated Time:** 6 hours  
**Priority:** Low  
**Files:** CSS and template files

**Steps:**
1. Audit mobile experience
2. Implement responsive navigation
3. Optimize table display for mobile
4. Test on various screen sizes
5. Fix any mobile-specific issues

**Acceptance Criteria:**
- Application usable on mobile devices
- Navigation works on small screens
- Tables and forms mobile-friendly
- No horizontal scrolling issues

### Task 4.3: Accessibility enhancements
**Estimated Time:** 4 hours  
**Priority:** Low  
**Files:** All template files

**Steps:**
1. Add proper ARIA labels
2. Ensure keyboard navigation
3. Improve color contrast where needed
4. Add skip navigation links
5. Test with screen readers

**Acceptance Criteria:**
- WCAG 2.1 AA compliance
- Keyboard navigation throughout
- Screen reader compatibility
- Color contrast ratios met

## Implementation Guidelines

### Development Workflow
1. Create feature branch for each task
2. Implement changes incrementally  
3. Test thoroughly before merging
4. Update documentation as needed
5. Get code review before deployment

### Testing Strategy
1. Visual regression testing
2. Functional testing for each page
3. Cross-browser compatibility testing
4. Mobile device testing
5. Accessibility testing

### Quality Gates
- [ ] No broken functionality
- [ ] Visual consistency maintained
- [ ] No new accessibility issues
- [ ] Performance not degraded
- [ ] Code review completed

## Dependencies and Risks

### Task Dependencies
- Task 1.1 and 1.2 must complete before Task 2.2
- Task 2.1 should complete before most Phase 3 tasks
- Component creation (1.3) can run parallel with CSS work

### Risk Mitigation
- **Breaking changes:** Implement incrementally with feature flags
- **Timeline overrun:** Prioritize Phase 1 and 2 tasks
- **Cross-browser issues:** Test early and often
- **Mobile problems:** Use progressive enhancement

## Success Criteria

### Completion Metrics
- [ ] 100% of pages extend base.html
- [ ] Zero inline style blocks in templates  
- [ ] All components use design system classes
- [ ] Navigation active states implemented
- [ ] Mobile responsive design functional
- [ ] Accessibility improvements completed

### Quality Metrics
- Visual consistency score: 95%+
- Page load performance: <2s average
- Accessibility score: AA compliance
- Cross-browser compatibility: 100%
- Mobile usability: All core functions accessible