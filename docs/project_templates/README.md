# Project Templates Documentation

This directory contains documentation that is specific to generated QuickScale projects. These files serve as both:

1. **Master Documentation** - The authoritative source for project-specific documentation
2. **Template Source** - These files are copied to generated projects during `quickscale init`

## Documentation Files

### [service_development_guide.md](service_development_guide.md)
Comprehensive guide for developing AI services in QuickScale projects. Covers:
- Quick start examples
- Service architecture and patterns
- Credit system integration
- Testing and validation
- Best practices

### [auth_templates.md](auth_templates.md)
Complete reference for authentication templates and customization:
- Template directory structure
- Naming conventions
- Styling guidelines
- Customization examples

### [styling_guidelines.md](styling_guidelines.md)
UI/UX styling guidelines for consistent design across QuickScale projects:
- Form element styling
- Component patterns
- Color schemes and themes
- Responsive design patterns

### [template_customization_examples.md](template_customization_examples.md)
Practical examples of common template customizations:
- Environment variable usage
- Project name configuration
- Custom styling examples
- Advanced customizations

### [architectural_decisions.md](architectural_decisions.md)
Key architectural decisions and their rationale:
- Settings architecture
- Security configuration
- Feature organization
- Development workflows

## Maintenance

When updating these files:

1. **Edit the master files** in this directory (`docs/project_templates/`)
2. **Copy changes** to the template directory (`quickscale/project_templates/docs/`)
3. **Test project generation** to ensure documentation is properly included

### Copy Command

To sync changes from master to templates:

```bash
# From the quickscale root directory
cp docs/project_templates/*.md quickscale/project_templates/docs/
```

## Architecture Notes

This dual-location approach ensures:
- **Single Source of Truth**: Master documentation lives in `docs/project_templates/`
- **Project Generation**: Documentation is automatically included in generated projects
- **Maintainability**: Updates only need to be made in one place, then copied
- **Consistency**: All generated projects get the same, up-to-date documentation

## Related Documentation

- [Main QuickScale Documentation](../README.md)
- [Technical Documentation](../../TECHNICAL_DOCS.md)
- [Contributing Guidelines](../../CONTRIBUTING.md)
- [AI Assistant Guidelines](../contrib/)
